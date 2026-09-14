from __future__ import annotations

import hashlib
import os
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path


def _read_chunks(path: Path, chunk_size: int) -> Iterator[bytes]:
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            yield chunk


def sha256_file(path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    for chunk in _read_chunks(Path(path), chunk_size):
        digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def vault_path(vault_root: str | Path, digest: str) -> Path:
    root = Path(vault_root)
    return root / digest[:2] / digest


@dataclass(frozen=True)
class StoredAsset:
    sha256: str
    byte_size: int
    vault_path: Path


def copy_file_to_vault(
    source_path: str | Path,
    vault_root: str | Path,
    chunk_size: int = 1024 * 1024,
) -> StoredAsset:
    """Store a source file with a single sequential read.

    Bytes are hashed while they are copied to a unique temp file. If the
    content-addressed destination already exists, the temp file is discarded.
    """
    source = Path(source_path)
    root = Path(vault_root)
    tmp_dir = root / ".tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_dir / f"{os.getpid()}-{uuid.uuid4().hex}.part"
    digest = hashlib.sha256()
    byte_size = 0
    promoted = False
    try:
        with tmp_path.open("wb") as dst:
            for chunk in _read_chunks(source, chunk_size):
                digest.update(chunk)
                dst.write(chunk)
                byte_size += len(chunk)
        hexdigest = digest.hexdigest()
        destination = vault_path(root, hexdigest)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            os.replace(tmp_path, destination)
            promoted = True
    finally:
        if not promoted:
            tmp_path.unlink(missing_ok=True)
    return StoredAsset(
        sha256=hexdigest,
        byte_size=byte_size,
        vault_path=destination,
    )
