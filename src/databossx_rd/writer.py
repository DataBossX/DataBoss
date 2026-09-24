"""Single-writer lock for the isolated R&D output root."""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

from .constants import DEFAULT_RUNTIME_RD, FORBIDDEN_PRODUCTION_PREFIXES, REPO_ROOT

try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]


class IsolationError(Exception):
    """Raised when a write would escape the isolated R&D root."""


class WriterConflict(Exception):
    """Raised when a second writer tries to mutate the same target."""


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except Exception:
        return False


def _atomic_write_json(path: Path, payload: Any) -> Path:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, path)
    return path


def assert_isolated_target(target: Path, allowed_roots: Optional[list[Path]] = None) -> Path:
    resolved = target.resolve()
    roots = [Path(root).resolve() for root in (allowed_roots or [DEFAULT_RUNTIME_RD])]
    if not any(_is_relative_to(resolved, root) for root in roots):
        raise IsolationError(f"write_outside_isolated_root:{resolved}")
    repo = REPO_ROOT.resolve()
    if _is_relative_to(resolved, repo):
        rel = resolved.relative_to(repo).as_posix()
        for prefix in FORBIDDEN_PRODUCTION_PREFIXES:
            if rel == prefix.rstrip("/") or rel.startswith(prefix):
                raise IsolationError(f"production_path_forbidden:{rel}")
    return resolved


class ExclusiveWriter:
    """One mutable target has one writer for the lifetime of the lock."""

    def __init__(
        self,
        target: Path,
        writer_id: str,
        allowed_roots: Optional[list[Path]] = None,
    ) -> None:
        self.target = assert_isolated_target(target, allowed_roots)
        self.writer_id = writer_id
        self.lock_path = self.target / ".writer.lock"
        self.meta_path = self.target / ".writer.json"
        self._handle: Any = None

    def _write_meta(self, active: bool) -> None:
        _atomic_write_json(
            self.meta_path,
            {
                "writer_id": self.writer_id,
                "active": active,
                "target": str(self.target),
                "acquired_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    def _open_lock(self) -> None:
        self._handle = os.open(self.lock_path, os.O_RDWR | os.O_CREAT, 0o644)
        if fcntl is None:
            return
        try:
            fcntl.flock(self._handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            os.close(self._handle)
            self._handle = None
            raise WriterConflict("target_locked_by_other_writer") from exc

    def acquire(self) -> Path:
        self.target.mkdir(parents=True, exist_ok=True)
        if self.meta_path.exists():
            try:
                existing = json.loads(self.meta_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise WriterConflict("writer_metadata_unreadable") from exc
            if existing.get("active") and existing.get("writer_id") != self.writer_id:
                raise WriterConflict(
                    f"target_has_other_writer:{existing.get('writer_id')}"
                )
        self._open_lock()
        self._write_meta(True)
        return self.target

    def release(self) -> None:
        if self.meta_path.exists():
            try:
                self._write_meta(False)
            except OSError:
                pass
        if self._handle is None:
            return
        if fcntl is not None:
            try:
                fcntl.flock(self._handle, fcntl.LOCK_UN)
            except OSError:
                pass
        os.close(self._handle)
        self._handle = None

    def write_json(self, relative: str, payload: dict[str, Any]) -> Path:
        if self._handle is None:
            raise WriterConflict("writer_not_acquired")
        dest = (self.target / relative).resolve()
        assert_isolated_target(dest, [self.target])
        dest.parent.mkdir(parents=True, exist_ok=True)
        return _atomic_write_json(dest, payload)


@contextmanager
def exclusive_writer(
    target: Path,
    writer_id: str,
    allowed_roots: Optional[list[Path]] = None,
) -> Iterator[ExclusiveWriter]:
    writer = ExclusiveWriter(target, writer_id, allowed_roots)
    writer.acquire()
    try:
        yield writer
    finally:
        writer.release()
