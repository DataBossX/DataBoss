"""Hash and CRC-check ZIP packages without opening client cell values."""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def zip_members(path: Path) -> list[dict[str, object]]:
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise zipfile.BadZipFile(f"CRC failed on {bad}")
        return [
            {"name": info.filename, "bytes": info.file_size, "crc": info.CRC}
            for info in archive.infolist()
            if not info.is_dir()
        ]


def inspect_package(path: Path) -> dict[str, object]:
    path = Path(path)
    members = zip_members(path)
    return {
        "path": str(path),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "member_count": len(members),
        "members": members,
        "crc_pass": True,
    }
