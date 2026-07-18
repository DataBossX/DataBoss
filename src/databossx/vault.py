from __future__ import annotations

import hashlib
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from .config import KernelConfig


class VaultError(RuntimeError):
    pass


@dataclass(frozen=True)
class VaultReceipt:
    sha256: str
    size_bytes: int
    relative_path: str
    destination: Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class Vault:
    def __init__(self, config: KernelConfig) -> None:
        self.config = config

    def put_file(self, source: Path) -> VaultReceipt:
        source = source.resolve(strict=True)
        if not source.is_file() or source.is_symlink():
            raise VaultError(f"Not an ingestible regular file: {source}")
        before = source.stat()
        if before.st_size > self.config.max_file_bytes:
            raise VaultError(
                f"File exceeds {self.config.max_file_bytes} byte safety limit"
            )

        temporary_dir = self.config.vault_root / "tmp"
        temporary_dir.mkdir(parents=True, exist_ok=True)
        temporary = temporary_dir / f"{uuid4().hex}.part"
        digest = hashlib.sha256()
        size = 0
        try:
            with source.open("rb") as reader, temporary.open("xb") as writer:
                for chunk in iter(lambda: reader.read(1024 * 1024), b""):
                    digest.update(chunk)
                    writer.write(chunk)
                    size += len(chunk)
                writer.flush()
                os.fsync(writer.fileno())
            after = source.stat()
            identity_changed = (
                before.st_size != after.st_size
                or before.st_mtime_ns != after.st_mtime_ns
                or (before.st_ino and after.st_ino and before.st_ino != after.st_ino)
            )
            if identity_changed:
                raise VaultError(f"Source changed while being copied: {source}")

            checksum = digest.hexdigest()
            relative = Path("sha256") / checksum[:2] / checksum
            destination = self.config.vault_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                if destination.stat().st_size != size or sha256_file(destination) != checksum:
                    raise VaultError(f"Existing vault object failed verification: {checksum}")
                temporary.unlink()
            else:
                os.replace(temporary, destination)
                try:
                    destination.chmod(0o444)
                except OSError:
                    pass
            if sha256_file(destination) != checksum:
                raise VaultError(f"Vault write verification failed: {checksum}")
            return VaultReceipt(checksum, size, relative.as_posix(), destination)
        finally:
            temporary.unlink(missing_ok=True)

    def object_path(self, checksum: str) -> Path:
        if len(checksum) != 64 or any(c not in "0123456789abcdef" for c in checksum):
            raise VaultError("Invalid SHA-256 identifier")
        path = self.config.vault_root / "sha256" / checksum[:2] / checksum
        if not path.is_file() or sha256_file(path) != checksum:
            raise VaultError(f"Vault object is missing or corrupt: {checksum}")
        return path

    def materialize(self, checksum: str, destination: Path) -> Path:
        source = self.object_path(checksum)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            raise VaultError(f"Refusing to overwrite materialized file: {destination}")
        shutil.copy2(source, destination)
        destination.chmod(destination.stat().st_mode | 0o200)
        if sha256_file(destination) != checksum:
            destination.unlink(missing_ok=True)
            raise VaultError("Materialized copy failed hash verification")
        return destination
