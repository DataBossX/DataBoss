"""CrewAI agent definitions and the LLM factory.

Three agents mirror the spec:

* ``IngestionAgent``  -- extracts runsheet rows, notes, legals, OGL references,
  parties, book/page and tract mapping into JSON.
* ``TitleAuditorAgent`` -- chains title by tract, applies ASSN logic, deducts
  ownership, carries OGL numbers, and returns *final* owners only.
* ``MathematicianAgent`` -- verifies final tract totals, detects deltas, rejects
  bad chains, and returns precise correction feedback.

The deterministic engine (:mod:`chaining`, :mod:`verifier`) always runs; the
LLM agents *assist* -- they refine the chain when the deterministic pass cannot
balance a tract. Everything here is therefore lazy: importing this module never
requires ``crewai`` or a live model, so the app degrades gracefully to the
deterministic path when no LLM is configured.

Security: API keys are read from the environment and never logged or echoed.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional


class LLMNotConfiguredError(RuntimeError):
    """Raised when no usable model can be resolved from the environment."""


def crewai_available() -> bool:
    """True if the ``crewai`` package can be imported."""
    try:
        import crewai  # noqa: F401
    except Exception:
        return False
    return True


def _ollama_reachable(base_url: str, timeout: float = 1.5) -> bool:
    """Best-effort probe of a local Ollama-compatible endpoint."""
    try:
        import urllib.request

        req = urllib.request.Request(base_url.rstrip("/") + "/api/tags")
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            return resp.status == 200
    except Exception:
        return False


def describe_model_config() -> str:
    """Return a human-readable, secret-free summary of the model in use."""
    if os.getenv("OPENAI_API_KEY"):
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        return f"OpenAI model '{model}' (key present, not shown)"
    base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    if _ollama_reachable(base):
        model = os.getenv("OLLAMA_MODEL", "llama3.1")
        return f"Ollama model '{model}' at {base}"
    return "No LLM configured (deterministic-only mode)"


def get_llm() -> Any:
    """Resolve an LLM from the environment.

    Priority: ``OPENAI_API_KEY`` -> OpenAI; else a reachable Ollama endpoint;
    else raise :class:`LLMNotConfiguredError` with a clear message. The API key
    itself is never included in any message or log.
    """
    if os.getenv("OPENAI_API_KEY"):
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as exc:  # pragma: no cover
            raise LLMNotConfiguredError(
                "OPENAI_API_KEY is set but 'langchain-openai' is not installed. "
                "Run: pip install langchain-openai"
            ) from exc
        return ChatOpenAI(model=model, temperature=0)

    base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    if _ollama_reachable(base):
        model = os.getenv("OLLAMA_MODEL", "llama3.1")
        try:
            # crewai bundles litellm; "ollama/<model>" routes to a local server.
            from crewai import LLM

            return LLM(model=f"ollama/{model}", base_url=base)
        except Exception as exc:  # pragma: no cover
            raise LLMNotConfiguredError(
                f"Ollama endpoint reachable at {base} but could not initialize "
                f"the crewai LLM wrapper: {exc}"
            ) from exc

    raise LLMNotConfiguredError(
        "No language model is configured. Set OPENAI_API_KEY in .env to use "
        "OpenAI, or run a local Ollama server (set OLLAMA_BASE_URL). The "
        "pipeline can still run in deterministic-only mode without an LLM."
    )


def try_get_llm() -> Optional[Any]:
    """Return an LLM if one is configured, else ``None`` (no exception)."""
    try:
        return get_llm()
    except LLMNotConfiguredError:
        return None


# --- Agent factory --------------------------------------------------------

_INGESTION_BACKSTORY = (
    "A meticulous Oklahoma land-data technician. You transcribe a runsheet into "
    "clean structured JSON without ever losing a note, legal, party, book/page, "
    "or OGL reference. You NEVER place an assignment book/page into an OGL field "
    "-- OGL fields hold OGL numbers only."
)

_AUDITOR_BACKSTORY = (
    "A senior Oklahoma landman who chains title tract by tract exactly like the "
    "Tract 1 pattern. You deduct ownership as it is conveyed, never let an owner "
    "convey more than they own, never allow negative ownership, carry OGL numbers "
    "down beside leased owners, normalize assignment conveyances to 'ASSN', and "
    "return ONLY the final owners after chaining. Runsheet notes and legals are "
    "controlling unless obviously wrong; any assumption you make is stated "
    "explicitly and flagged for review."
)

_MATH_BACKSTORY = (
    "A forensic acreage auditor who never trusts an LLM's arithmetic. You take "
    "the deterministic Python (Decimal) verification as ground truth, report the "
    "exact delta when a tract fails to total to its acreage, and hand back "
    "precise, actionable correction feedback -- never a silent force-balance."
)


def build_agents(llm: Optional[Any] = None) -> Dict[str, Any]:
    """Construct the three CrewAI agents.

    Requires ``crewai`` and a resolvable LLM. Raises a clear error otherwise so
    callers can fall back to the deterministic path.
    """
    if not crewai_available():
        raise LLMNotConfiguredError(
            "The 'crewai' package is not installed; cannot build agents. "
            "Run: pip install crewai crewai-tools"
        )
    from crewai import Agent

    if llm is None:
        llm = get_llm()

    ingestion = Agent(
        role="IngestionAgent",
        goal=(
            "Extract runsheet rows, notes, legals, OGL references, parties, "
            "book/page and tract mapping into strict JSON, keeping OGL numbers "
            "only in OGL fields."
        ),
        backstory=_INGESTION_BACKSTORY,
        llm=llm,
        allow_delegation=False,
        verbose=False,
    )
    auditor = Agent(
        role="TitleAuditorAgent",
        goal=(
            "Chain title by tract, apply ASSN logic, deduct ownership, carry OGL "
            "numbers beside leased owners, and return final owners only -- with "
            "every tract totaling exactly to its acreage or a noted assumption."
        ),
        backstory=_AUDITOR_BACKSTORY,
        llm=llm,
        allow_delegation=False,
        verbose=False,
    )
    mathematician = Agent(
        role="MathematicianAgent",
        goal=(
            "Confirm final tract totals against the deterministic Decimal "
            "verifier, surface exact deltas, reject bad chains, and return "
            "precise correction feedback."
        ),
        backstory=_MATH_BACKSTORY,
        llm=llm,
        allow_delegation=False,
        verbose=False,
    )
    return {
        "ingestion": ingestion,
        "auditor": auditor,
        "mathematician": mathematician,
    }
