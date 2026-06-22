"""Anthropic Claude vision provider. Best-in-class for messy handwriting."""
from __future__ import annotations

import json
import os
import re

from .base import ModelResult, VisionProvider
from .. import config


class ClaudeProvider(VisionProvider):
    name = "claude"

    def __init__(self):
        self._client = None

    def is_configured(self) -> bool:
        return bool(os.getenv("ANTHROPIC_API_KEY"))

    def _client_or_raise(self):
        if self._client is None:
            from anthropic import Anthropic  # lazy import
            key = os.getenv("ANTHROPIC_API_KEY")
            if not key:
                raise RuntimeError("ANTHROPIC_API_KEY not configured.")
            self._client = Anthropic(api_key=key)
        return self._client

    def extract_json(self, image_paths: list[str], instruction: str) -> ModelResult:
        client = self._client_or_raise()
        blocks = [{"type": "text", "text": instruction}]
        for p in image_paths[:5]:
            b64, mime = self._b64(p)
            blocks.append({
                "type": "image",
                "source": {"type": "base64", "media_type": mime, "data": b64},
            })
        msg = client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": blocks}],
        )
        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        return ModelResult(_parse_json(text))


def _parse_json(text: str) -> dict:
    text = text.strip()
    # Strip markdown fences if present.
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    if m:
        text = m.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # last resort: grab the outermost braces
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
        return {"raw_text": text, "confidence": 0.0, "needs_review": True}
