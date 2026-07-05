"""Execution logic: the task graph for the crew, and the pipeline driver.

Two things live here:

* :func:`build_task_graph` — the three CrewAI tasks (ingest → chain → verify)
  that encode the self-healing loop. The verify task is wired to send work back
  to the auditor when a tract does not tie out.
* :func:`run_pipeline` — the single entry point the Streamlit app and the CLI
  call. It always runs the deterministic engine (the source of truth), streams
  telemetry, writes the highlighted report, and — only when the LLM swarm is
  actually available — additionally runs the crew to produce a narrative.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from . import agents as agents_mod
from .engine import EngineResult, SelfHealingEngine, Telemetry, TelemetryEvent, TelemetrySink
from .xlsx_writer import write_highlighted_report


# --------------------------------------------------------------------------- #
# CrewAI task graph (only meaningful when crewai is importable)
# --------------------------------------------------------------------------- #
def build_task_graph(section, workbook, ingestion_agent, auditor_agent, math_agent):
    """Build the (ingest, chain, verify) CrewAI tasks encoding the loop."""
    from crewai import Task  # type: ignore

    wb = workbook or "the section workbook"

    task_ingest = Task(
        description=(
            f"Read {wb}. Extract every OGL conveyance row and every runsheet note "
            f"for Section {section}, mapping each note to its instrument number and "
            f"tract. Do not invent any field; leave unknowns blank."
        ),
        expected_output=(
            "A structured list of conveyances (instrument, grantor, grantee, "
            "conveyed interest, legal description, gross acres) and the runsheet "
            "notes keyed by instrument number."
        ),
        agent=ingestion_agent,
    )

    task_chain = Task(
        description=(
            f"Chain out the working interest for every tract in Section {section}, "
            f"walking each tract from the full 8/8 estate and enforcing "
            f"retained = grantor - conveyed. Carry instrument numbers down the chain. "
            f"Where a conveyed interest is undetermined, resolve it ONLY from the "
            f"runsheet note for that instrument and flag the value ASSUMED."
        ),
        expected_output=(
            "A chained title for each tract with per-instrument conveyed and "
            "retained interests, and every assumption explicitly flagged ASSUMED."
        ),
        agent=auditor_agent,
        context=[task_ingest],
    )

    task_verify = Task(
        description=(
            "Take the chained title from the Auditor. Using the exact-math "
            "verification tool (never mental arithmetic), calculate each tract's "
            "net acres and the sum of its working interests. If a tract's sum does "
            "not equal the full 8/8 estate / gross acreage, explain the exact delta "
            "and return the tract to the Title Landman to find the missing "
            "conveyance. Escalate any over-conveyance or unresolved gap as "
            "'Needs Examiner Review'."
        ),
        expected_output=(
            "A verified per-tract payload of final owners and their fractional "
            "interests, mathematically balanced to the tract total, with any "
            "unbalanced tract clearly flagged and explained."
        ),
        agent=math_agent,
        context=[task_chain],
    )

    return task_ingest, task_chain, task_verify


# --------------------------------------------------------------------------- #
# Pipeline driver
# --------------------------------------------------------------------------- #
@dataclass
class PipelineOutcome:
    """What :func:`run_pipeline` returns to the UI/CLI."""

    result: EngineResult
    report_path: Optional[Path]
    mode: str  # "deterministic" | "swarm+deterministic"
    narrative: Optional[str] = None

    @property
    def events(self) -> List[TelemetryEvent]:
        return self.result.events


def run_pipeline(
    workbook: str | Path,
    section: str = "31-12N-24W",
    out_path: Optional[str | Path] = None,
    template: Optional[str | Path] = None,
    max_loops: int = 5,
    use_swarm: str = "auto",  # "auto" | "off" | "force"
    sink: Optional[TelemetrySink] = None,
    llm=None,
) -> PipelineOutcome:
    """Run the whole command-center pipeline over one section workbook.

    ``use_swarm`` controls the optional LLM narration layer:
      * ``"off"``   — deterministic only (default behaviour anywhere without a key);
      * ``"auto"``  — add the CrewAI narrative iff crewai + an API key are present;
      * ``"force"`` — require the swarm; raise if it cannot run.

    The deterministic engine always runs and is always authoritative. The report
    is written from the engine's result, not from any LLM output.
    """
    workbook = Path(workbook)
    tel = Telemetry(sink)

    swarm_on = _resolve_swarm(use_swarm, tel)

    # 1) Deterministic self-healing loop — the source of truth.
    engine = SelfHealingEngine(section=section, max_loops=max_loops, telemetry=tel)
    result = engine.run(workbook)

    # 2) Write the highlighted report.
    report_path: Optional[Path] = None
    if out_path is not None:
        report_path = write_highlighted_report(
            result.report,
            Path(out_path),
            result.assumed_cells,
            template=Path(template) if template else None,
        )
        tel.emit(
            "SYSTEM",
            "success",
            f"Report written to {report_path.name} "
            f"({len(result.assumed_cells)} ASSUMED cells highlighted yellow).",
        )

    # 3) Optional LLM narrative (never authoritative).
    narrative = None
    mode = "deterministic"
    if swarm_on:
        narrative = _run_swarm_narrative(section, workbook, tel, llm)
        mode = "swarm+deterministic"

    # keep result.events in sync with everything emitted through this pipeline
    result.events = list(tel.events)
    return PipelineOutcome(result=result, report_path=report_path, mode=mode, narrative=narrative)


def _resolve_swarm(use_swarm: str, tel: Telemetry) -> bool:
    if use_swarm == "off":
        return False
    available = agents_mod.swarm_available()
    if use_swarm == "force":
        if not available:
            raise RuntimeError(
                "use_swarm='force' but the CrewAI swarm is unavailable "
                f"(crewai_installed={agents_mod.CREWAI_AVAILABLE}, "
                f"llm_configured={agents_mod.llm_configured()})."
            )
        return True
    # auto
    if not available:
        tel.emit(
            "SYSTEM",
            "info",
            "LLM swarm unavailable (crewai/API key not present) — running in "
            "deterministic mode. The exact-fraction engine produces the full report.",
        )
    return available


def _run_swarm_narrative(section, workbook, tel: Telemetry, llm) -> Optional[str]:
    """Run the CrewAI crew for a human-facing narrative. Never sets the numbers."""
    try:  # pragma: no cover - requires crewai + a live LLM
        tel.emit("SYSTEM", "action", "Engaging CrewAI swarm for narrative synthesis…")
        crew = agents_mod.build_crew(section=section, workbook=str(workbook), llm=llm)
        if crew is None:
            return None
        output = crew.kickoff()
        text = str(output)
        tel.emit("SYSTEM", "success", "Swarm narrative complete.")
        return text
    except Exception as exc:  # pragma: no cover
        tel.emit("SYSTEM", "warn", f"Swarm narration failed ({exc}); deterministic report stands.")
        return None
