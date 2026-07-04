"""Content-addressed cache for retrieved source documents/metadata."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, Dict, Optional


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class SourceCache:
    def __init__(self, cache_dir: str | Path):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def put_file(self, src_path: str | Path, reference: str) -> Dict[str, Any]:
        src = Path(src_path)
        digest = sha256_file(src)
        dest = self.cache_dir / f"{digest[:16]}_{src.name}"
        if not dest.exists():
            shutil.copy2(src, dest)
        return {"reference": reference, "sha256": digest, "path": str(dest)}

    def put_metadata(self, reference: str, meta: Dict[str, Any]) -> Dict[str, Any]:
        text = json.dumps(meta, indent=2, default=str).encode("utf-8")
        digest = sha256_bytes(text)
        safe = reference.replace("/", "_").replace("\\", "_")
        dest = self.cache_dir / f"meta_{safe}_{digest[:12]}.json"
        if not dest.exists():
            dest.write_bytes(text)
        return {"reference": reference, "sha256": digest, "path": str(dest)}

    def find_local(self, reference: str, search_dirs) -> Optional[Dict[str, Any]]:
        """Look for a file whose name contains the (normalised) reference."""
        needle = reference.replace("/", "_").replace("-", "_").lower()
        for d in search_dirs:
            d = Path(d)
            if not d.exists():
                continue
            for p in d.rglob("*"):
                if p.is_file() and needle in p.name.replace("/", "_").replace("-", "_").lower():
                    return {"reference": reference, "sha256": sha256_file(p),
                            "path": str(p), "source": "local"}
        return None
