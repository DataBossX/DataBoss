"""
cache.py
========
Two small, dependency-free helpers:

1. AIResultCache - an on-disk cache of AI extraction results keyed by a hash of
   the captured document image(s) + model name. Re-running the tool (or hitting
   the same document twice) then skips paying for the AI call again.

   IMPORTANT: only the *extracted JSON text* is cached - never the document
   images themselves. This respects the "do not save county images" rule.

2. UsageTracker - counts AI calls / cache hits / tokens per model so the run
   summary can report effort and (optionally) help the user reason about cost.

The cache lives in `cache_dir` (default ".cache"), which is git-ignored and is
NOT wiped by the per-row temp cleanup.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
from typing import Dict, List, Optional

log = logging.getLogger("horizon.cache")


def image_signature(images_png: List[bytes], model: str) -> str:
    """Stable hash of the image bytes + model name."""
    h = hashlib.sha256()
    h.update(model.encode("utf-8"))
    for img in images_png:
        h.update(b"\x00")
        h.update(hashlib.sha256(img).digest())
    return h.hexdigest()


class AIResultCache:
    def __init__(self, cache_dir: str, enabled: bool = True):
        self.enabled = enabled
        self.dir = cache_dir
        if self.enabled:
            os.makedirs(self.dir, exist_ok=True)

    def _path(self, key: str) -> str:
        return os.path.join(self.dir, f"{key}.json")

    def get(self, key: str) -> Optional[dict]:
        if not self.enabled:
            return None
        path = self._path(key)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception as exc:
            log.debug("cache read failed (%s): %s", key, exc)
            return None

    def put(self, key: str, value: dict) -> None:
        if not self.enabled:
            return
        try:
            with open(self._path(key), "w", encoding="utf-8") as fh:
                json.dump(value, fh)
        except Exception as exc:
            log.debug("cache write failed (%s): %s", key, exc)


class UsageTracker:
    """Thread-safe counters for AI effort across a run."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.calls: Dict[str, int] = {}
        self.cache_hits: Dict[str, int] = {}
        self.input_tokens: Dict[str, int] = {}
        self.output_tokens: Dict[str, int] = {}

    def record_call(self, model: str, in_tok: int = 0, out_tok: int = 0) -> None:
        with self._lock:
            self.calls[model] = self.calls.get(model, 0) + 1
            self.input_tokens[model] = self.input_tokens.get(model, 0) + (in_tok or 0)
            self.output_tokens[model] = self.output_tokens.get(model, 0) + (out_tok or 0)

    def record_cache_hit(self, model: str) -> None:
        with self._lock:
            self.cache_hits[model] = self.cache_hits.get(model, 0) + 1

    def summary(self) -> Dict[str, int]:
        with self._lock:
            return {
                "ai_calls_total": sum(self.calls.values()),
                "ai_cache_hits_total": sum(self.cache_hits.values()),
                "ai_input_tokens_total": sum(self.input_tokens.values()),
                "ai_output_tokens_total": sum(self.output_tokens.values()),
            }

    def detail_lines(self) -> List[str]:
        with self._lock:
            models = sorted(set(self.calls) | set(self.cache_hits))
            lines = []
            for m in models:
                lines.append(
                    f"    {m}: calls={self.calls.get(m,0)} "
                    f"cache_hits={self.cache_hits.get(m,0)} "
                    f"in_tok={self.input_tokens.get(m,0)} "
                    f"out_tok={self.output_tokens.get(m,0)}"
                )
            return lines
