"""Offline mock vision provider.

Lets the full index pipeline run with NO API key — for wiring tests and as a
deterministic stand-in. It does NOT read handwriting; it returns clearly-marked
synthetic rows. Never use it for real title work. Enable with CTA_MODEL_ORDER=mock.
"""
from __future__ import annotations

from .base import ModelResult, VisionProvider

# A few real Bk/Pg values that exist in the Section 31 Runsheet, so the diff
# demonstrates both "present" and "missing" branches during a dry run.
_SEED = [("FR1", "470"), ("D6", "206"), ("ZZ9", "999")]


class MockProvider(VisionProvider):
    name = "mock"

    def is_configured(self) -> bool:
        return True

    def extract_json(self, image_paths: list[str], instruction: str) -> ModelResult:
        # Derive a stable page number from the filename for determinism.
        import re
        m = re.search(r"(\d+)", image_paths[0].rsplit("/", 1)[-1]) if image_paths else None
        pg = int(m.group(1)) if m else 0
        bk, pgno = _SEED[pg % len(_SEED)]
        rows = [{
            "grantor": f"MOCK Grantor {pg}", "grantee": f"MOCK Grantee {pg}",
            "instrument_kind": "O/L" if pg % 2 else "MD",
            "book": bk, "page": pgno,
            "date_filed": "1955-01-01", "legal_note": "MOCK",
            "remarks": "SYNTHETIC — mock provider", "confidence": 0.10,
        }]
        return ModelResult(rows=rows, page_confidence=0.10)
