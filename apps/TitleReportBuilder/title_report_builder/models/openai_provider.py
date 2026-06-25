"""Optional OpenAI provider. Imported lazily; only used if OPENAI_API_KEY set."""
from __future__ import annotations
import os


class OpenAIProvider:
    name = "openai"

    def __init__(self, model: str | None = None):
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    def complete(self, prompt: str, *, system: str = "", max_tokens: int = 1024) -> str:
        from openai import OpenAI  # imported lazily
        client = OpenAI()  # reads OPENAI_API_KEY from env
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.append({"role": "user", "content": prompt})
        resp = client.chat.completions.create(
            model=self.model, messages=msgs, max_tokens=max_tokens, temperature=0)
        return resp.choices[0].message.content or ""
