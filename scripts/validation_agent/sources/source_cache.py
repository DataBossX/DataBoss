"""Local source-document metadata cache.

Stores content-addressed metadata for documents discovered on disk so repeated
runs don't re-hash unchanged files. Never stores document *contents* — only
paths, hashes, and reference keys.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from core.hashing import sha256_file


@dataclass
class CachedSource:
    reference_key: str
    reference_type: str
    file_path: str
    sha256: str
    source: str = "local"

    def to_dict(self) -> Dict[str, str]:
        return asdict(self)


class SourceCache:
    def __init__(self, cache_path: Path) -> None:
        self.cache_path = Path(cache_path)
        self._entries: Dict[str, CachedSource] = {}
        self._load()

    def _load(self) -> None:
        if self.cache_path.exists():
            try:
                raw = json.loads(self.cache_path.read_text(encoding="utf-8"))
                for key, val in raw.items():
                    self._entries[key] = CachedSource(**val)
            except (json.JSONDecodeError, TypeError):
                self._entries = {}

    def _persist(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        body = {k: v.to_dict() for k, v in self._entries.items()}
        self.cache_path.write_text(
            json.dumps(body, indent=2, sort_keys=True), encoding="utf-8"
        )

    def get(self, reference_key: str) -> Optional[CachedSource]:
        return self._entries.get(reference_key)

    def add(self, reference_key: str, reference_type: str, file_path: Path,
            source: str = "local") -> CachedSource:
        entry = CachedSource(
            reference_key=reference_key,
            reference_type=reference_type,
            file_path=str(file_path),
            sha256=sha256_file(file_path),
            source=source,
        )
        self._entries[reference_key] = entry
        self._persist()
        return entry

    def all(self) -> List[CachedSource]:
        return list(self._entries.values())
