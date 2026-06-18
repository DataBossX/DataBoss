"""LLM analysis with reliability hardening.

Provider SDKs are imported lazily so the backend runs even when a given SDK is
not installed (the provider simply reports as unavailable). Each analysis call
is bounded by a timeout and retried with exponential backoff; a provider that
keeps failing degrades gracefully rather than taking the request down.
"""

import asyncio
import random
from typing import Any

from loguru import logger

import config

# Cache lazily-created provider clients: name -> client (or False if unavailable)
_clients: dict[str, Any] = {}

PROMPTS = {
    "legal_summary": (
        "Analyze this legal document and extract key information:\n\n"
        "Document: {text}\n\n"
        "Please provide:\n1. Document type\n2. Key parties involved\n"
        "3. Important dates\n4. Main legal points\n5. Summary"
    ),
    "general_summary": "Provide a concise summary of this document:\n\n{text}",
    "field_extraction": (
        "Extract structured data from this document:\n\n{text}\n\nReturn as JSON with relevant fields."
    ),
}


class LLMError(Exception):
    """Raised when an LLM analysis cannot be completed."""


def _openai_client():
    if "openai" not in _clients:
        client = None
        if config.OPENAI_API_KEY:
            try:
                import openai

                client = openai.OpenAI(api_key=config.OPENAI_API_KEY)
            except ImportError:
                logger.warning("openai SDK not installed; OpenAI disabled")
        _clients["openai"] = client
    return _clients["openai"]


def _anthropic_client():
    if "anthropic" not in _clients:
        client = None
        if config.ANTHROPIC_API_KEY:
            try:
                import anthropic

                client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
            except ImportError:
                logger.warning("anthropic SDK not installed; Anthropic disabled")
        _clients["anthropic"] = client
    return _clients["anthropic"]


def _gemini_module():
    if "gemini" not in _clients:
        module = None
        if config.GEMINI_API_KEY:
            try:
                import google.generativeai as genai

                genai.configure(api_key=config.GEMINI_API_KEY)
                module = genai
            except ImportError:
                logger.warning("google-generativeai not installed; Gemini disabled")
        _clients["gemini"] = module
    return _clients["gemini"]


def available_models() -> list[str]:
    models = []
    if _openai_client():
        models.append("gpt-4")
    if _anthropic_client():
        models.append("claude")
    if _gemini_module():
        models.append("gemini")
    return models


def provider_status() -> dict[str, str]:
    return {
        "openai": "available" if _openai_client() else "unavailable",
        "anthropic": "available" if _anthropic_client() else "unavailable",
        "gemini": "available" if _gemini_module() else "unavailable",
    }


def _call_sync(model_name: str, prompt: str) -> str:
    """Blocking provider call (run in a thread by ``analyze``)."""
    if model_name == "gpt-4":
        client = _openai_client()
        if not client:
            raise LLMError("OpenAI is not available")
        resp = client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=config.LLM_MAX_TOKENS,
        )
        return resp.choices[0].message.content

    if model_name == "claude":
        client = _anthropic_client()
        if not client:
            raise LLMError("Anthropic is not available")
        resp = client.messages.create(
            model=config.ANTHROPIC_MODEL,
            max_tokens=config.LLM_MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text

    if model_name == "gemini":
        genai = _gemini_module()
        if not genai:
            raise LLMError("Gemini is not available")
        model = genai.GenerativeModel(config.GEMINI_MODEL)
        return model.generate_content(prompt).text

    raise LLMError(f"Unknown model: {model_name}")


async def analyze(text: str, model_name: str, prompt_type: str) -> dict[str, Any]:
    """Run an LLM analysis with timeout + retry. Raises LLMError on failure."""
    prompt = PROMPTS.get(prompt_type, PROMPTS["general_summary"]).format(text=text)
    loop = asyncio.get_event_loop()
    start = loop.time()

    last_exc: Exception | None = None
    for attempt in range(config.LLM_MAX_RETRIES + 1):
        try:
            result = await asyncio.wait_for(
                loop.run_in_executor(None, _call_sync, model_name, prompt),
                timeout=config.LLM_TIMEOUT_SECONDS,
            )
            return {
                "analysis": result,
                "processing_time": loop.time() - start,
                "model_used": model_name,
                "prompt_type": prompt_type,
                "attempts": attempt + 1,
            }
        except TimeoutError:
            last_exc = LLMError(f"{model_name} timed out after {config.LLM_TIMEOUT_SECONDS}s")
            logger.warning(f"LLM {model_name} timeout (attempt {attempt + 1})")
        except Exception as exc:  # provider/network error
            last_exc = exc
            logger.warning(f"LLM {model_name} error (attempt {attempt + 1}): {exc}")

        if attempt < config.LLM_MAX_RETRIES:
            backoff = min(2**attempt + random.uniform(0, 0.5), 10)
            await asyncio.sleep(backoff)

    raise LLMError(f"LLM analysis with {model_name} failed: {last_exc}")
