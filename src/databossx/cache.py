"""Content-addressed cache for derived work.

Cache keys bind recipe version, sorted input hashes, and canonical parameters.
A hit skips recomputation; a parameter or input change is a miss.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .receipts import sha256_canonical


def make_cache_key(
    recipe_version: str,
    input_hashes: list[str] | tuple[str, ...],
    params: Mapping[str, Any] | None = None,
) -> str:
    return sha256_canonical(
        {
            "inputs": sorted(input_hashes),
            "params": params or {},
            "recipe": recipe_version,
        }
    )


@dataclass(frozen=True)
class CachedWork:
    cache_key: str
    recipe_version: str
    input_manifest_hash: str
    output_hash: str
    payload: dict[str, Any]


class DerivedWorkCache:
    """Filesystem cache keyed by bound input hashes."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, cache_key: str) -> Path:
        return self.root / cache_key[:2] / f"{cache_key}.json"

    def get(self, cache_key: str) -> CachedWork | None:
        path = self.path_for(cache_key)
        if not path.is_file():
            return None
        raw = json.loads(path.read_text(encoding="utf-8"))
        if raw.get("cache_key") != cache_key:
            return None
        return CachedWork(
            cache_key=cache_key,
            recipe_version=raw["recipe_version"],
            input_manifest_hash=raw["input_manifest_hash"],
            output_hash=raw["output_hash"],
            payload=raw["payload"],
        )

    def put(
        self,
        *,
        recipe_version: str,
        input_hashes: list[str] | tuple[str, ...],
        payload: Mapping[str, Any],
        params: Mapping[str, Any] | None = None,
        output_hash: str | None = None,
    ) -> CachedWork:
        cache_key = make_cache_key(recipe_version, input_hashes, params)
        input_manifest_hash = sha256_canonical(sorted(input_hashes))
        stored_hash = output_hash or sha256_canonical(payload)
        record = {
            "cache_key": cache_key,
            "input_manifest_hash": input_manifest_hash,
            "output_hash": stored_hash,
            "payload": dict(payload),
            "recipe_version": recipe_version,
        }
        destination = self.path_for(cache_key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(destination)
        return CachedWork(
            cache_key=cache_key,
            recipe_version=recipe_version,
            input_manifest_hash=input_manifest_hash,
            output_hash=stored_hash,
            payload=dict(payload),
        )
