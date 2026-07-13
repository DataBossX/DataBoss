"""Content-addressed local filesystem vault.

Bytes are hashed with SHA-256 and stored at
``root/sha256/<first_2_hex_chars>/<full_hex_hash>``. Writes are idempotent
(existing content is never overwritten) and original source files passed to
``put_file`` are never modified, moved, or deleted.
"""

from __future__ import annotations

import hashlib
import shutil
import tempfile
from pathlib import Path


class Vault:
    """A content-addressed, append-only local filesystem vault."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, sha256_hex: str) -> Path:
        """Return the on-disk path for a given SHA-256 hex digest."""
        sha256_hex = sha256_hex.lower()
        prefix = sha256_hex[:2]
        return self.root / "sha256" / prefix / sha256_hex

    def has(self, sha256_hex: str) -> bool:
        """Return True if content for this hash is already stored."""
        return self.path_for(sha256_hex).is_file()

    def put(self, data: bytes, artifact_type: str = "") -> str:
        """Hash ``data`` with SHA-256 and store it; return the hex digest.

        If content for the resulting hash already exists, the existing
        file is left untouched (idempotent write). ``artifact_type`` is
        accepted for interface symmetry/future metadata but is not encoded
        in the storage path -- content addressing is by hash alone.
        """
        digest = hashlib.sha256(data).hexdigest()
        dest = self.path_for(digest)
        if dest.is_file():
            return digest

        dest.parent.mkdir(parents=True, exist_ok=True)
        # Write to a temp file in the same directory, then atomically
        # rename into place, so concurrent/partial writes never corrupt
        # the vault.
        fd, tmp_name = tempfile.mkstemp(dir=str(dest.parent), prefix=".tmp-")
        try:
            with open(fd, "wb") as tmp_file:
                tmp_file.write(data)
            Path(tmp_name).replace(dest)
        except BaseException:
            Path(tmp_name).unlink(missing_ok=True)
            raise
        return digest

    def get(self, sha256_hex: str) -> bytes:
        """Return the stored bytes for a hash, or raise KeyError if absent."""
        path = self.path_for(sha256_hex)
        if not path.is_file():
            raise KeyError(f"no vault entry for hash {sha256_hex!r}")
        return path.read_bytes()

    def put_file(self, src: Path, artifact_type: str = "") -> str:
        """Copy ``src`` into the vault by content hash; never modifies ``src``.

        Returns the hex digest. The copy is streamed (not read fully into
        memory) so large files are handled efficiently.
        """
        src = Path(src)
        hasher = hashlib.sha256()
        with open(src, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                hasher.update(chunk)
        digest = hasher.hexdigest()
        dest = self.path_for(digest)
        if dest.is_file():
            return digest

        dest.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=str(dest.parent), prefix=".tmp-")
        try:
            import os

            os.close(fd)
            # shutil.copyfile never touches the source file's metadata or
            # removes it -- it only reads from src and writes to the tmp
            # destination.
            shutil.copyfile(src, tmp_name)
            Path(tmp_name).replace(dest)
        except BaseException:
            Path(tmp_name).unlink(missing_ok=True)
            raise
        return digest

    def verify(self, sha256_hex: str) -> bool:
        """Re-hash the stored bytes for ``sha256_hex`` and confirm a match."""
        path = self.path_for(sha256_hex)
        if not path.is_file():
            return False
        hasher = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                hasher.update(chunk)
        return hasher.hexdigest() == sha256_hex.lower()
