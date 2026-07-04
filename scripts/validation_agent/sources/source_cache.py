"""Content-addressed cache for retrieved source documents/metadata.

Files are stored under the run's ``sources/`` folder, hashed, and never
overwritten (a second write of the same content is a no-op; different content
gets a new numbered name).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class SourceCache:
    def __init__(self, cache_dir: Path):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def store_bytes(self, name: str, data: bytes) -> Dict[str, Any]:
        digest = _sha256_bytes(data)
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in name)
        target = self.cache_dir / f"{digest[:12]}_{safe}"
        if not target.exists():
            target.write_bytes(data)
        return {"path": str(target), "sha256": digest, "bytes": len(data)}

    def store_metadata(self, ref: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        blob = json.dumps(metadata, sort_keys=True, default=str).encode("utf-8")
        return self.store_bytes(f"meta_{ref}.json", blob)
