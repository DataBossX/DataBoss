"""Optional Anthropic provider. Imported lazily; only used if ANTHROPIC_API_KEY set."""
from __future__ import annotations
import os


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, model: str | None = None):
        self.model = model or os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")

    def complete(self, prompt: str, *, system: str = "", max_tokens: int = 1024) -> str:
        import anthropic  # imported lazily
        client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
        resp = client.messages.create(
            model=self.model, max_tokens=max_tokens, system=system or "",
            messages=[{"role": "user", "content": prompt}])
        return "".join(getattr(b, "text", "") for b in resp.content)
