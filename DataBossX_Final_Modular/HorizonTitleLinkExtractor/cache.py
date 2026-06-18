"""
cache.py
========
Two cheap-but-high-impact features:

1. ResultCache - content-addressed cache of AI extractions keyed by a hash of
   (model + image bytes). Re-running a job (resume, second pass, tweaking
   spreadsheet logic) costs ZERO extra API calls for rows whose document image
   is unchanged. Cache lives in .cache/ (gitignored).

2. CostTracker - estimates token usage + USD per provider call and writes
   logs/cost.csv so the user can see exactly what a run cost, per row and total.

Both are intentionally dependency-free (stdlib json/hashlib).
"""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import os
import threading
from dataclasses import dataclass, field

log = logging.getLogger("horizon.cache")


def image_key(model: str, images: list[bytes]) -> str:
    h = hashlib.sha256()
    h.update(model.encode("utf-8"))
    for img in images:
        h.update(hashlib.sha256(img).digest())
    return h.hexdigest()


class ResultCache:
    def __init__(self, cache_dir: str = ".cache", enabled: bool = True):
        self.cache_dir = cache_dir
        self.enabled = enabled
        if enabled:
            os.makedirs(cache_dir, exist_ok=True)

    def _path(self, key: str) -> str:
        return os.path.join(self.cache_dir, f"{key}.json")

    def get(self, key: str) -> dict | None:
        if not self.enabled:
            return None
        path = self._path(key)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            return None

    def set(self, key: str, value: dict) -> None:
        if not self.enabled:
            return
        try:
            with open(self._path(key), "w", encoding="utf-8") as fh:
                json.dump(value, fh)
        except Exception as exc:
            log.warning("cache write failed: %s", exc)


# --- Cost estimation ---------------------------------------------------------
# Rough public per-million-token prices (USD). Used for *estimates only*; matched
# by substring so model version suffixes still resolve. Update freely.
_PRICES = {
    "gpt-5": (5.0, 15.0),
    "gpt-4o": (2.5, 10.0),
    "gemini-2.5-pro": (1.25, 5.0),
    "gemini": (1.0, 4.0),
    "claude-sonnet": (3.0, 15.0),
    "claude-opus": (15.0, 75.0),
    "claude": (3.0, 15.0),
}


def _price_for(model: str) -> tuple[float, float]:
    m = (model or "").lower()
    for key, price in _PRICES.items():
        if key in m:
            return price
    return (3.0, 12.0)  # conservative default


@dataclass
class CostTracker:
    rows: list[dict] = field(default_factory=list)
    total_usd: float = 0.0
    total_calls: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def record(self, model: str, in_tokens: int, out_tokens: int,
               row: object = "", cached: bool = False) -> float:
        in_price, out_price = _price_for(model)
        usd = 0.0 if cached else (
            in_tokens / 1_000_000 * in_price + out_tokens / 1_000_000 * out_price)
        with self._lock:
            self.total_usd += usd
            if not cached:
                self.total_calls += 1
            self.rows.append({
                "row": row, "model": model, "cached": cached,
                "in_tokens": in_tokens, "out_tokens": out_tokens,
                "usd": round(usd, 6),
            })
        return usd

    def write_csv(self, path: str) -> None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["row", "model", "cached", "in_tokens", "out_tokens", "usd"])
            for r in self.rows:
                w.writerow([r["row"], r["model"], r["cached"], r["in_tokens"],
                            r["out_tokens"], r["usd"]])
            w.writerow([])
            w.writerow(["TOTAL_CALLS", self.total_calls, "", "", "",
                        round(self.total_usd, 4)])
