"""CrewAI-compatible tools that expose the deterministic engine to the swarm.

The agents in :mod:`command_center.agents` are LLM-driven and must **never** do
interest arithmetic themselves — an LLM cannot be trusted to add 1/3 + 5/128. So
every quantitative step is delegated to one of these tools, each of which calls
the exact-fraction :mod:`command_center.engine`. The agents narrate and route;
the tools compute.

The module is import-safe with or without ``crewai`` installed. When CrewAI is
present the functions are also exposed as ``BaseTool`` instances (``*_TOOL``);
when it is not, the plain callables still work, so the deterministic pipeline in
:mod:`command_center.tasks` runs regardless.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from horizon.interest import format_acres, format_fraction

from .engine import SelfHealingEngine, Telemetry, TelemetrySink
from .xlsx_writer import write_highlighted_report

try:  # optional dependency — only needed for the LLM narration layer
    from crewai.tools import BaseTool  # type: ignore

    CREWAI_AVAILABLE = True
except Exception:  # pragma: no cover - exercised only where crewai is absent
    BaseTool = object  # type: ignore
    CREWAI_AVAILABLE = False


# --------------------------------------------------------------------------- #
# Plain callables (the real work)
# --------------------------------------------------------------------------- #
def run_engine(
    workbook: str,
    section: str = "31-12N-24W",
    max_loops: int = 5,
    sink: Optional[TelemetrySink] = None,
) -> SelfHealingEngine:
    """Run the self-healing loop and return the *engine* (holds the result)."""
    engine = SelfHealingEngine(section=section, max_loops=max_loops, telemetry=Telemetry(sink))
    engine.run(Path(workbook))
    return engine


def verify_chain_tool(workbook: str, section: str = "31-12N-24W") -> str:
    """Chain + verify every tract; return a compact per-tract verdict string.

    This is the Mathematician's tool: it reports, for each tract, whether the sum
    of working interests ties to the full 8/8 estate / gross acreage, and the
    exact delta when it does not.
    """
    engine = SelfHealingEngine(section=section)
    result = engine.run(Path(workbook))
    lines = [f"Section {result.section}: {result.tracts_balanced}/{len(result.balances)} "
             f"tract(s) tie to 8/8; converged={result.converged} in {result.loops_run} loop(s)."]
    for b in result.balances:
        net = format_acres(b.net_acres_sum) if b.net_acres_sum is not None else "?"
        gross = format_acres(b.gross_acres) if b.gross_acres is not None else "?"
        lines.append(
            f"  {b.tract_legal or b.tract}: status={b.status} "
            f"Σwi={format_fraction(b.outstanding_sum)} delta={format_fraction(b.delta)} "
            f"net={net}/{gross}ac"
            + (f" | ASSUMED: {'; '.join(b.assumptions)}" if b.assumptions else "")
            + (f" | REVIEW: {'; '.join(b.reasons)}" if b.reasons else "")
        )
    return "\n".join(lines)


def write_report_tool(
    workbook: str,
    out_path: str,
    section: str = "31-12N-24W",
    template: Optional[str] = None,
) -> str:
    """Run the loop and write the perfected, yellow-highlighted report to Excel."""
    engine = SelfHealingEngine(section=section)
    result = engine.run(Path(workbook))
    written = write_highlighted_report(
        result.report,
        Path(out_path),
        result.assumed_cells,
        template=Path(template) if template else None,
    )
    return (
        f"Wrote {written} — {len(result.report.rows)} rows, "
        f"{len(result.assumed_cells)} ASSUMED cells highlighted yellow, "
        f"{result.tracts_escalated} tract(s) flagged for examiner review."
    )


# --------------------------------------------------------------------------- #
# CrewAI BaseTool wrappers (only defined when crewai is importable)
# --------------------------------------------------------------------------- #
if CREWAI_AVAILABLE:  # pragma: no cover - requires crewai installed

    class VerifyChainTool(BaseTool):  # type: ignore[misc]
        name: str = "verify_working_interest"
        description: str = (
            "Chain out working interest for the section and verify each tract's "
            "interest sum against the full 8/8 estate and gross acreage using "
            "exact fraction math. Input: the path to the OGL+runsheet workbook. "
            "Returns a per-tract verdict with the exact delta for any tract that "
            "does not tie out."
        )

        def _run(self, workbook: str) -> str:
            return verify_chain_tool(workbook)

    class WriteReportTool(BaseTool):  # type: ignore[misc]
        name: str = "write_highlighted_report"
        description: str = (
            "Write the perfected cursory title report to Excel, highlighting "
            "ASSUMED data points in yellow. Input: 'workbook_path|out_path'."
        )

        def _run(self, args: str) -> str:
            workbook, _, out_path = args.partition("|")
            return write_report_tool(workbook.strip(), out_path.strip() or "REPORT_v001.xlsx")

    VERIFY_CHAIN_TOOL = VerifyChainTool()
    WRITE_REPORT_TOOL = WriteReportTool()
else:
    VERIFY_CHAIN_TOOL = None
    WRITE_REPORT_TOOL = None
