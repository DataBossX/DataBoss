"""Path-safety and time-of-check/time-of-use hardened hashing.

Intake must never follow a symlink, junction, or other reparse point, and must
never read a file whose resolved location escapes an authorized root. Hashing
opens one stable handle and verifies the file's identity metadata before and
after reading so a swap-under-us cannot slip an unverified file past intake.
"""

from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path
from typing import Sequence

_FILE_ATTRIBUTE_REPARSE_POINT = 0x400


class PathSecurityError(ValueError):
    """Raised when a path violates intake path-safety guarantees."""


class HashIntegrityError(RuntimeError):
    """Raised when a file changes identity while being hashed (TOCTOU)."""


def _is_reparse_point(lstat_result: os.stat_result) -> bool:
    if stat.S_ISLNK(lstat_result.st_mode):
        return True
    attributes = getattr(lstat_result, "st_file_attributes", 0)
    if attributes and (attributes & _FILE_ATTRIBUTE_REPARSE_POINT):
        return True
    reparse_tag = getattr(lstat_result, "st_reparse_tag", 0)
    return bool(reparse_tag)


def _reject_reparse_components(path: Path) -> None:
    """Reject a reparse point at the target or any ancestor up to the anchor."""
    current = path
    seen: set[Path] = set()
    while True:
        if current in seen:
            break
        seen.add(current)
        try:
            info = os.lstat(current)
        except FileNotFoundError:
            break
        except OSError as exc:
            raise PathSecurityError(f"cannot inspect path component {current}: {exc}") from exc
        if _is_reparse_point(info):
            raise PathSecurityError(f"refusing to traverse reparse point/symlink: {current}")
        parent = current.parent
        if parent == current:
            break
        current = parent


def _normalized_roots(authorized_roots: Sequence[str | os.PathLike[str]] | None) -> list[Path]:
    roots: list[Path] = []
    for root in authorized_roots or ():
        resolved = Path(root).expanduser().resolve(strict=False)
        _reject_reparse_components(resolved)
        roots.append(resolved)
    return roots


def _within_any_root(resolved: Path, roots: Sequence[Path]) -> bool:
    for root in roots:
        try:
            resolved.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def safe_resolve_file(
    path: str | os.PathLike[str],
    *,
    authorized_roots: Sequence[str | os.PathLike[str]] | None = None,
) -> Path:
    """Resolve ``path`` to a real regular file, enforcing path safety.

    - Rejects symlinks/junctions/reparse points at the target or any ancestor.
    - Requires the fully resolved path to be a regular file.
    - When ``authorized_roots`` is provided, requires the resolved path to live
      inside one of them; otherwise raises (fail closed).
    """
    raw = Path(path).expanduser()
    # Reject reparse points on the pre-resolution path (before symlinks collapse).
    if raw.exists() or raw.is_symlink():
        _reject_reparse_components(raw if raw.is_absolute() else raw.resolve(strict=False))

    resolved = raw.resolve(strict=True)
    _reject_reparse_components(resolved)

    info = os.stat(resolved)
    if not stat.S_ISREG(info.st_mode):
        raise PathSecurityError(f"intake target is not a regular file: {resolved}")

    roots = _normalized_roots(authorized_roots)
    if roots and not _within_any_root(resolved, roots):
        raise PathSecurityError(
            f"resolved path {resolved} is outside every authorized root: "
            f"{', '.join(str(r) for r in roots)}"
        )
    return resolved


def _identity(info: os.stat_result) -> tuple:
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)


def hash_file_stable(
    path: str | os.PathLike[str],
    *,
    authorized_roots: Sequence[str | os.PathLike[str]] | None = None,
    chunk_size: int = 1024 * 1024,
) -> tuple[str, int]:
    """Return ``(sha256_hex, size_bytes)`` read through one stable handle.

    Metadata identity is captured before and after reading and the handle is
    re-stat'd at the end; any change aborts with :class:`HashIntegrityError`.
    """
    resolved = safe_resolve_file(path, authorized_roots=authorized_roots)

    # O_NOFOLLOW where available prevents following a symlink at open() time.
    open_flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(resolved, open_flags)
    try:
        before = os.fstat(fd)
        if _is_reparse_point(before):
            raise PathSecurityError(f"open resolved to a reparse point: {resolved}")
        if not stat.S_ISREG(before.st_mode):
            raise PathSecurityError(f"open target is not a regular file: {resolved}")

        digest = hashlib.sha256()
        total = 0
        with os.fdopen(fd, "rb", closefd=False) as stream:
            for chunk in iter(lambda: stream.read(chunk_size), b""):
                digest.update(chunk)
                total += len(chunk)

        after = os.fstat(fd)
        if _identity(before) != _identity(after):
            raise HashIntegrityError(
                f"file identity changed while hashing (TOCTOU): {resolved}"
            )
        if total != after.st_size:
            raise HashIntegrityError(
                f"read {total} bytes but size is {after.st_size}: {resolved}"
            )
        return digest.hexdigest(), total
    finally:
        os.close(fd)
