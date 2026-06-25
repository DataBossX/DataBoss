"""Offline provider — deterministic, no network, no keys. Used as the always-
available fallback. It does not hallucinate title conclusions; it returns
structured 'needs review' responses so the pipeline degrades safely."""
from __future__ import annotations


class OfflineProvider:
    name = "offline"

    def complete(self, prompt: str, *, system: str = "", max_tokens: int = 1024) -> str:
        return ("[offline] No model provider configured. This field requires a "
                "model or human review — not fabricated. Configure an API key in "
                ".env to enable model-assisted extraction.")
