"""Content-addressed cache for retrieved source documents/metadata.

All downloaded documents and metadata are written under the run's ``sources/``
folder, hashed, and never overwritten.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.run_manager import sha256_bytes, sha256_file


class SourceCache:
    def __init__(self, sources_dir: str | Path):
        self.dir = Path(sources_dir)
        self.dir.mkdir(parents=True, exist_ok=True)

    def _unique(self, name: str) -> Path:
        path = self.dir / name
        if not path.exists():
            return path
        stem, suffix = Path(name).stem, Path(name).suffix
        n = 1
        while (self.dir / f"{stem}_{n:03d}{suffix}").exists():
            n += 1
        return self.dir / f"{stem}_{n:03d}{suffix}"

    def store_bytes(self, name: str, data: bytes) -> tuple[Path, str]:
        path = self._unique(name)
        path.write_bytes(data)
        return path, sha256_bytes(data)

    def store_metadata(self, reference_key: str, meta: dict[str, Any]) -> tuple[Path, str]:
        safe = reference_key.replace("/", "_").replace("\\", "_").replace(" ", "_")
        payload = json.dumps(meta, indent=2, sort_keys=True).encode("utf-8")
        return self.store_bytes(f"meta_{safe}.json", payload)

    def find_local(self, reference_key: str) -> Path | None:
        """Look for a previously cached document matching a reference key."""
        safe = reference_key.replace("/", "_").replace("\\", "_").replace(" ", "_")
        for p in self.dir.glob(f"*{safe}*"):
            if p.is_file():
                return p
        return None
