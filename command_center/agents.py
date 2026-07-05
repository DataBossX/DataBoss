"""The CrewAI agent swarm — Ingestion, Title Auditor, Mathematician.

This mirrors the architecture in the prompt (three agents, a Title Auditor that
may delegate to a Mathematician, a self-healing verification loop) but with two
deliberate hardening changes:

1. **The Mathematician is backed by exact-fraction tools**, not free-form LLM
   arithmetic. It calls :data:`command_center.tools.VERIFY_CHAIN_TOOL`, which
   runs the deterministic engine. This is the single most important correctness
   decision in the system: an LLM that "computes" 5/128 + 1/16 will eventually
   fabricate a balance, and a fabricated title balance is worse than no answer.

2. **It degrades gracefully.** ``crewai`` and an LLM API key are optional. When
   either is missing, :func:`build_crew` returns ``None`` and the caller
   (:mod:`command_center.tasks`) runs the deterministic engine directly — the
   full pipeline still produces the report, minus the LLM narration.

``build_crew`` accepts an ``llm`` so the operator can point at OpenAI, a local
Ollama endpoint, or any LiteLLM-supported model without editing this file.
"""

from __future__ import annotations

import os
from typing import Optional

from . import tools

try:
    from crewai import Agent, Crew, Process, Task  # type: ignore

    CREWAI_AVAILABLE = True
except Exception:  # pragma: no cover - exercised where crewai is absent
    Agent = Crew = Process = Task = None  # type: ignore
    CREWAI_AVAILABLE = False


def llm_configured() -> bool:
    """True if an LLM endpoint looks usable (an OpenAI-style key is present)."""
    return bool(
        os.environ.get("OPENAI_API_KEY")
        or os.environ.get("OPENAI_API_BASE")
        or os.environ.get("OLLAMA_BASE_URL")
        or os.environ.get("LITELLM_MODEL")
    )


def swarm_available() -> bool:
    """True only when the LLM narration layer can actually run."""
    return CREWAI_AVAILABLE and llm_configured()


def build_agents(section: str = "31-12N-24W", llm=None):
    """Construct the three agents. Raises if CrewAI is not installed."""
    if not CREWAI_AVAILABLE:  # pragma: no cover
        raise RuntimeError(
            "crewai is not installed; run in deterministic mode "
            "(command_center.tasks.run_pipeline) instead."
        )

    verify_tool = tools.VERIFY_CHAIN_TOOL
    write_tool = tools.WRITE_REPORT_TOOL

    ingestion_agent = Agent(
        role="Data Extraction Specialist",
        goal=(
            "Extract unstructured runsheet notes and map assignments (ASSN) to "
            "specific tracts and OGL instrument numbers for Section " + section + "."
        ),
        backstory=(
            "Expert petroleum data analyst. You translate messy human notes into "
            "pristine, structured records keyed on the instrument number. You never "
            "invent a field — a value absent from the files stays blank and flagged."
        ),
        verbose=True,
        allow_delegation=False,
        llm=llm,
    )

    auditor_agent = Agent(
        role="Senior Title Landman",
        goal=(
            "Chain out the working interest for Section " + section + ". Strictly "
            "enforce that a party can only convey what it owns. Carry instrument "
            "numbers down the chain. When a gap exists, make a documented assumption "
            "from the runsheet, flag it ASSUMED, and deduct the interest."
        ),
        backstory=(
            "You are a forensic title expert. You never hallucinate conveyances. You "
            "resolve gaps only from what the runsheet notes actually say, and every "
            "assumption you make is flagged for the examiner, never buried."
        ),
        tools=[t for t in (verify_tool,) if t is not None],
        verbose=True,
        allow_delegation=True,  # may delegate verification to the Mathematician
        llm=llm,
    )

    math_agent = Agent(
        role="Acreage & Interest Verifier",
        goal=(
            "Verify fractional interests with exact math. Ensure the sum of all "
            "chained working interests for each tract equals exactly the full 8/8 "
            "estate and the tract's gross acreage. Report the exact delta on any "
            "mismatch and return it to the Title Landman."
        ),
        backstory=(
            "You are a ruthless auditor who computes with exact fractions, never "
            "floats or estimates. You always call your verification tool rather than "
            "doing arithmetic in your head. If the working-interest sum does not tie "
            "to the tract total, you reject the chain and hand the delta back to the "
            "Title Landman to find the missing conveyance."
        ),
        tools=[t for t in (verify_tool, write_tool) if t is not None],
        verbose=True,
        allow_delegation=False,
        llm=llm,
    )

    return ingestion_agent, auditor_agent, math_agent


def build_crew(section: str = "31-12N-24W", workbook: Optional[str] = None, llm=None):
    """Assemble the self-healing crew, or ``None`` if the swarm can't run.

    The task graph encodes the loop: ingest → chain → verify, with the verify
    task free to send work back to the auditor (``context`` + the auditor's
    ``allow_delegation``). The deterministic engine remains the source of truth
    for every number; the crew produces the human-facing narrative around it.
    """
    if not swarm_available():
        return None

    from .tasks import build_task_graph  # local import avoids a cycle

    ingestion_agent, auditor_agent, math_agent = build_agents(section, llm=llm)
    task_ingest, task_chain, task_verify = build_task_graph(
        section, workbook, ingestion_agent, auditor_agent, math_agent
    )
    return Crew(
        agents=[ingestion_agent, auditor_agent, math_agent],
        tasks=[task_ingest, task_chain, task_verify],
        process=Process.sequential,  # switch to Process.hierarchical for an AI manager
        verbose=True,
    )
