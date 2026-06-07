"""Optional LLM client used by the multi-AI tournament.

Disabled by default. It only activates when (a) the config requests it and
(b) an API key is present in the environment. Credentials are NEVER read from
config files or hard-coded -- only from os.environ (populated from .env).

If no key/SDK is available, callers fall back to the deterministic heuristic
passes, so the pipeline still runs.
"""
from __future__ import annotations

import json
import os
from typing import Optional

from .utils import LOG

DEFAULT_MODEL = os.getenv("TRF_LLM_MODEL", "claude-opus-4-8")


def llm_available() -> bool:
    if not any(os.getenv(k) for k in
               ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "LITELLM_API_KEY")):
        return False
    try:
        import litellm  # noqa: F401
        return True
    except Exception:
        return False


def complete_json(system: str, user: str,
                  model: Optional[str] = None) -> Optional[dict]:
    """Return a parsed JSON object from the model, or None on any failure.

    Best-effort and side-effect free: failures are logged and swallowed so a
    flaky/absent LLM never breaks the deterministic pipeline.
    """
    if not llm_available():
        return None
    try:
        import litellm

        resp = litellm.completion(
            model=model or DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0,
            max_tokens=1500,
        )
        content = resp["choices"][0]["message"]["content"]
        return _loads_loose(content)
    except Exception as exc:  # pragma: no cover - network dependent
        LOG.warning("LLM call failed, falling back to heuristics: %s", exc)
        return None


def _loads_loose(content: str) -> Optional[dict]:
    content = (content or "").strip()
    if content.startswith("```"):
        content = content.strip("`")
        if content.lower().startswith("json"):
            content = content[4:]
    try:
        return json.loads(content)
    except Exception:
        start, end = content.find("{"), content.rfind("}")
        if 0 <= start < end:
            try:
                return json.loads(content[start:end + 1])
            except Exception:
                return None
    return None
