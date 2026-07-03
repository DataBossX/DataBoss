"""LLM client abstraction.

Uses litellm when it is importable AND the relevant provider key is present in
the environment; otherwise reports itself as not-live so agents fall back to
their deterministic offline logic. This keeps the whole pipeline runnable and
testable with zero network access and zero secrets.

Model strings follow the config convention 'provider:model', e.g.
'anthropic:claude-3-5-sonnet' or 'openai:gpt-4o'.
"""
from __future__ import annotations

import os
from typing import Optional

_PROVIDER_KEY = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
}


def _split_model(model: str) -> tuple[str, str]:
    if ":" in model:
        provider, name = model.split(":", 1)
        return provider.strip().lower(), name.strip()
    return "", model.strip()


def provider_key_present(model: str) -> bool:
    provider, _ = _split_model(model)
    env_name = _PROVIDER_KEY.get(provider)
    return bool(env_name and os.environ.get(env_name))


class LLMClient:
    def __init__(self, model: str = "anthropic:claude-3-5-sonnet") -> None:
        self.model = model
        self._litellm = self._try_import_litellm()

    @staticmethod
    def _try_import_litellm():
        try:
            import litellm  # type: ignore

            return litellm
        except Exception:
            return None

    @property
    def is_live(self) -> bool:
        """True only if a real backend AND the provider key are both available."""
        return self._litellm is not None and provider_key_present(self.model)

    def complete(self, system: str, user: str, model: Optional[str] = None) -> str:
        """Return the model's text completion. Raises if not live."""
        if not self.is_live:
            raise RuntimeError(
                "No live LLM backend (litellm missing or provider key unset). "
                "Agents should use their offline path when is_live is False."
            )
        model = model or self.model
        provider, name = _split_model(model)
        # litellm expects e.g. 'anthropic/claude-3-5-sonnet'
        litellm_model = f"{provider}/{name}" if provider else name
        resp = self._litellm.completion(
            model=litellm_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp["choices"][0]["message"]["content"]
