"""Small fail-closed security primitives for local title evidence."""

from __future__ import annotations

import os
import re
import unicodedata
import zipfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import BinaryIO, Iterable


class EvidenceStatus(str, Enum):
    VERIFIED = "VERIFIED"
    DIRECTLY_OBSERVED = "DIRECTLY_OBSERVED"
    EXTRACTED_UNVERIFIED = "EXTRACTED_UNVERIFIED"
    INFERRED = "INFERRED"
    ASSUMED = "ASSUMED"
    ESTIMATED = "ESTIMATED"
    CONFLICTED = "CONFLICTED"
    MISSING = "MISSING"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    REJECTED = "REJECTED"


class SecurityError(ValueError):
    """An input failed a local trust-boundary check."""


def resolve_allowed_path(
    path: str | os.PathLike[str],
    allowed_roots: Iterable[str | os.PathLike[str]],
    *,
    must_exist: bool = True,
) -> Path:
    """Resolve a path only when its real target is under an allowed real root.

    Both the candidate and roots are resolved, so ``..`` traversal and symlink
    escapes are rejected. For a not-yet-created target, its nearest existing
    parent is resolved before the lexical suffix is appended.
    """

    roots = tuple(Path(root).expanduser().resolve(strict=True) for root in allowed_roots)
    if not roots:
        raise SecurityError("at least one allowed root is required")
    candidate = Path(path).expanduser()
    if must_exist:
        try:
            resolved = candidate.resolve(strict=True)
        except (FileNotFoundError, RuntimeError, OSError) as exc:
            raise SecurityError(f"path cannot be safely resolved: {candidate}") from exc
    else:
        existing = candidate
        suffix: list[str] = []
        while not existing.exists():
            if existing.parent == existing:
                raise SecurityError(f"path has no resolvable parent: {candidate}")
            suffix.append(existing.name)
            existing = existing.parent
        try:
            resolved = existing.resolve(strict=True).joinpath(*reversed(suffix))
        except (RuntimeError, OSError) as exc:
            raise SecurityError(f"path cannot be safely resolved: {candidate}") from exc
    if not any(resolved == root or resolved.is_relative_to(root) for root in roots):
        raise SecurityError(f"path escapes allowed roots: {candidate}")
    return resolved


_WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}


def sanitize_filename(name: str, *, replacement: str = "_", max_length: int = 180) -> str:
    """Return a portable basename, never a path."""

    if not name or "\x00" in name:
        raise SecurityError("filename is empty or contains NUL")
    if len(replacement) != 1 or replacement in '<>:"/\\|?*\x00':
        raise SecurityError("replacement must be one portable filename character")
    if max_length < 1:
        raise SecurityError("max_length must be positive")
    normalized = unicodedata.normalize("NFKC", name)
    basename = re.split(r"[/\\]", normalized)[-1]
    basename = re.sub(r"[\x00-\x1f\x7f<>:\"/\\|?*]+", replacement, basename)
    basename = re.sub(re.escape(replacement) + r"{2,}", replacement, basename)
    basename = basename.strip(" .")
    if not basename or basename in {".", ".."}:
        raise SecurityError("filename has no safe characters")
    stem, dot, suffix = basename.partition(".")
    if stem.upper() in _WINDOWS_RESERVED:
        stem = f"_{stem}"
        basename = stem + (dot + suffix if dot else "")
    if len(basename) > max_length:
        extension = Path(basename).suffix[:20]
        basename = basename[: max(1, max_length - len(extension))].rstrip(" .") + extension
    return basename


@dataclass(frozen=True)
class ZipLimits:
    max_entries: int = 2_000
    max_entry_uncompressed_bytes: int = 100 * 1024 * 1024
    max_total_uncompressed_bytes: int = 500 * 1024 * 1024
    max_compression_ratio: float = 200.0

    def __post_init__(self) -> None:
        if (
            self.max_entries <= 0
            or self.max_entry_uncompressed_bytes <= 0
            or self.max_total_uncompressed_bytes <= 0
            or self.max_compression_ratio <= 0
        ):
            raise ValueError("ZIP limits must be positive")


@dataclass(frozen=True)
class ZipValidation:
    entries: int
    compressed_bytes: int
    uncompressed_bytes: int
    names: tuple[str, ...]


def _safe_zip_name(name: str) -> bool:
    if not name or "\x00" in name or "\\" in name:
        return False
    path = PurePosixPath(name)
    return not path.is_absolute() and ".." not in path.parts and not re.match(
        r"^[A-Za-z]:", name
    )


def validate_zip(
    archive: str | os.PathLike[str] | BinaryIO,
    *,
    limits: ZipLimits | None = None,
) -> ZipValidation:
    """Validate ZIP metadata without extracting or trusting member names."""

    limits = limits or ZipLimits()
    try:
        with zipfile.ZipFile(archive) as handle:
            entries = handle.infolist()
            if len(entries) > limits.max_entries:
                raise SecurityError("ZIP entry limit exceeded")
            total_compressed = 0
            total_uncompressed = 0
            names: list[str] = []
            for info in entries:
                if not _safe_zip_name(info.filename):
                    raise SecurityError(f"unsafe ZIP member path: {info.filename!r}")
                unix_mode = (info.external_attr >> 16) & 0xFFFF
                if (unix_mode & 0o170000) == 0o120000:
                    raise SecurityError(f"ZIP symbolic link rejected: {info.filename!r}")
                if info.flag_bits & 0x1:
                    raise SecurityError(f"encrypted ZIP member rejected: {info.filename!r}")
                if info.file_size > limits.max_entry_uncompressed_bytes:
                    raise SecurityError(f"ZIP member size limit exceeded: {info.filename!r}")
                if info.compress_size:
                    ratio = info.file_size / info.compress_size
                elif info.file_size:
                    ratio = float("inf")
                else:
                    ratio = 1.0
                if ratio > limits.max_compression_ratio:
                    raise SecurityError(f"ZIP compression ratio limit exceeded: {info.filename!r}")
                total_compressed += info.compress_size
                total_uncompressed += info.file_size
                if total_uncompressed > limits.max_total_uncompressed_bytes:
                    raise SecurityError("ZIP total uncompressed size limit exceeded")
                names.append(info.filename)
            return ZipValidation(
                entries=len(entries),
                compressed_bytes=total_compressed,
                uncompressed_bytes=total_uncompressed,
                names=tuple(names),
            )
    except zipfile.BadZipFile as exc:
        raise SecurityError("invalid or corrupt ZIP archive") from exc


_MAGIC: tuple[tuple[str, bytes, int], ...] = (
    ("pdf", b"%PDF-", 0),
    ("png", b"\x89PNG\r\n\x1a\n", 0),
    ("jpeg", b"\xff\xd8\xff", 0),
    ("tiff", b"II*\x00", 0),
    ("tiff", b"MM\x00*", 0),
    ("gif", b"GIF87a", 0),
    ("gif", b"GIF89a", 0),
    ("bmp", b"BM", 0),
    ("xls", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", 0),
    ("zip", b"PK\x03\x04", 0),
    ("zip", b"PK\x05\x06", 0),
)
_EXTENSION_FORMATS = {
    ".pdf": {"pdf"},
    ".png": {"png"},
    ".jpg": {"jpeg"},
    ".jpeg": {"jpeg"},
    ".tif": {"tiff"},
    ".tiff": {"tiff"},
    ".gif": {"gif"},
    ".bmp": {"bmp"},
    ".webp": {"webp"},
    ".xls": {"xls"},
    ".zip": {"zip"},
    ".docx": {"docx"},
    ".xlsx": {"xlsx"},
    ".xlsm": {"xlsm"},
    ".txt": {"text"},
    ".text": {"text"},
    ".md": {"text"},
    ".log": {"text"},
    ".csv": {"text"},
    ".tsv": {"text"},
}


@dataclass(frozen=True)
class SignatureVerification:
    detected_format: str | None
    expected_formats: tuple[str, ...]
    valid: bool
    reason: str


def detect_signature(path: str | os.PathLike[str]) -> str | None:
    """Detect a small supported set by magic bytes and OOXML structure."""

    file_path = Path(path)
    with file_path.open("rb") as handle:
        prefix = handle.read(4096)
    if prefix.startswith(b"RIFF") and prefix[8:12] == b"WEBP":
        return "webp"
    detected = next(
        (kind for kind, signature, offset in _MAGIC if prefix[offset:].startswith(signature)),
        None,
    )
    if detected is None and prefix and b"\x00" not in prefix:
        try:
            prefix.decode("utf-8")
        except UnicodeDecodeError:
            pass
        else:
            return "text"
    if detected != "zip":
        return detected
    validation = validate_zip(file_path)
    names = set(validation.names)
    if "[Content_Types].xml" not in names:
        return "zip"
    if "word/document.xml" in names:
        return "docx"
    if "xl/workbook.xml" in names:
        return "xlsm" if "xl/vbaProject.bin" in names else "xlsx"
    return "zip"


def verify_signature(
    path: str | os.PathLike[str],
    *,
    expected_format: str | None = None,
) -> SignatureVerification:
    """Compare detected content to an explicit format or the file extension."""

    file_path = Path(path)
    expected = (
        {expected_format.lower().lstrip(".")}
        if expected_format
        else _EXTENSION_FORMATS.get(file_path.suffix.lower(), set())
    )
    if not expected:
        return SignatureVerification(None, (), False, "unsupported expected format")
    try:
        detected = detect_signature(file_path)
    except (OSError, SecurityError) as exc:
        return SignatureVerification(None, tuple(sorted(expected)), False, str(exc))
    valid = detected in expected
    return SignatureVerification(
        detected,
        tuple(sorted(expected)),
        valid,
        "signature matches" if valid else f"detected {detected or 'unknown'}",
    )
