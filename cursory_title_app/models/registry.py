"""Provider registry with priority order, retry, and fallback.

Order comes from config.MODEL_PROVIDER_ORDER. The first configured provider is
tried with retries; on hard failure the next configured provider is tried.
If a provider returns low confidence, that is NOT an error — the caller decides
(via the confidence threshold) whether to route to manual review. We never
silently substitute guesses.
"""
from __future__ import annotations

from tenacity import retry, stop_after_attempt, wait_exponential

from .base import ModelResult, VisionProvider
from .claude_provider import ClaudeProvider
from .openai_provider import OpenAIProvider
from .mock_provider import MockProvider
from .. import config

_REGISTRY: dict[str, type[VisionProvider]] = {
    "claude": ClaudeProvider,
    "openai": OpenAIProvider,
    "mock": MockProvider,
}


def available_providers() -> list[VisionProvider]:
    out = []
    for name in config.MODEL_PROVIDER_ORDER:
        cls = _REGISTRY.get(name)
        if cls is None:
            continue
        inst = cls()
        if inst.is_configured():
            out.append(inst)
    return out


@retry(stop=stop_after_attempt(3),
       wait=wait_exponential(multiplier=2, min=2, max=16))
def _extract_with(provider: VisionProvider, image_paths, instruction) -> ModelResult:
    return provider.extract_json(image_paths, instruction)


def extract_json(image_paths: list[str], instruction: str) -> ModelResult:
    """Try each configured provider in order. Raises only if ALL fail."""
    providers = available_providers()
    if not providers:
        raise RuntimeError(
            "No vision provider configured. Set ANTHROPIC_API_KEY or OPENAI_API_KEY "
            "in your .env (see CTA_MODEL_ORDER)."
        )
    last_err: Exception | None = None
    for provider in providers:
        try:
            result = _extract_with(provider, image_paths, instruction)
            result["_provider"] = provider.name
            return result
        except Exception as e:  # transport/auth/parse failure -> try next
            last_err = e
            continue
    raise RuntimeError(f"All vision providers failed. Last error: {last_err!r}")
