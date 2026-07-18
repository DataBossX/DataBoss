from __future__ import annotations

import hashlib
import os
import shutil
from dataclasses import dataclass
from pathlib import Path


def sha256_file(path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        while True:
            chunk = fh.read(chunk_size)
            if not chunk:
                break
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


def copy_file_to_vault(source_path: str | Path, vault_root: str | Path) -> StoredAsset:
    source = Path(source_path)
    digest = sha256_file(source)
    destination = vault_path(vault_root, digest)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        temp_path = destination.with_suffix(".tmp")
        with source.open("rb") as src, temp_path.open("wb") as dst:
            shutil.copyfileobj(src, dst)
        os.replace(temp_path, destination)
    return StoredAsset(
        sha256=digest,
        byte_size=source.stat().st_size,
        vault_path=destination,
    )
