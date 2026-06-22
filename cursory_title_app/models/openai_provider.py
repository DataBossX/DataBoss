"""OpenAI GPT-4o vision provider (fallback / swappable)."""
from __future__ import annotations

import os

from .base import ModelResult, VisionProvider
from .claude_provider import _parse_json
from .. import config


class OpenAIProvider(VisionProvider):
    name = "openai"

    def __init__(self):
        self._client = None

    def is_configured(self) -> bool:
        return bool(os.getenv("OPENAI_API_KEY"))

    def _client_or_raise(self):
        if self._client is None:
            from openai import OpenAI  # lazy import
            key = os.getenv("OPENAI_API_KEY")
            if not key:
                raise RuntimeError("OPENAI_API_KEY not configured.")
            self._client = OpenAI(api_key=key)
        return self._client

    def extract_json(self, image_paths: list[str], instruction: str) -> ModelResult:
        client = self._client_or_raise()
        content = [{"type": "text", "text": instruction}]
        for p in image_paths[:5]:
            b64, mime = self._b64(p)
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{b64}", "detail": "high"},
            })
        resp = client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=[{"role": "user", "content": content}],
            max_tokens=4096,
            response_format={"type": "json_object"},
        )
        return ModelResult(_parse_json(resp.choices[0].message.content))
