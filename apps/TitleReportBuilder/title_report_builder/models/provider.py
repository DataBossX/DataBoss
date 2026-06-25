"""Provider interface + router. Picks a provider by task complexity and which
API keys exist. Never fails just because no key is configured — falls back to
the offline (deterministic) provider. Secrets are read from env, never logged.
"""
from __future__ import annotations
import os
from typing import Protocol


class Provider(Protocol):
    name: str

    def complete(self, prompt: str, *, system: str = "", max_tokens: int = 1024) -> str:
        ...


def available_providers() -> list[str]:
    out = ["offline"]
    if os.getenv("ANTHROPIC_API_KEY"):
        out.append("anthropic")
    if os.getenv("OPENAI_API_KEY"):
        out.append("openai")
    if os.getenv("LMSTUDIO_BASE_URL"):
        out.append("lmstudio")
    return out


def route(task: str = "default", *, complexity: str = "medium") -> "Provider":
    """Return the best available provider. Order of preference is configurable
    via env TRB_MODEL_ORDER (comma-sep), else a sensible default by complexity."""
    avail = available_providers()
    order = os.getenv("TRB_MODEL_ORDER")
    if order:
        pref = [p.strip() for p in order.split(",")]
    elif complexity == "high":
        pref = ["anthropic", "openai", "lmstudio", "offline"]
    else:
        pref = ["openai", "anthropic", "lmstudio", "offline"]
    for p in pref:
        if p in avail:
            return _make(p)
    return _make("offline")


def _make(name: str) -> "Provider":
    if name == "offline":
        from .offline import OfflineProvider
        return OfflineProvider()
    if name == "openai":
        from .openai_provider import OpenAIProvider
        return OpenAIProvider()
    if name == "anthropic":
        try:
            from .anthropic_provider import AnthropicProvider
            return AnthropicProvider()
        except Exception:
            from .offline import OfflineProvider
            return OfflineProvider()
    from .offline import OfflineProvider
    return OfflineProvider()
