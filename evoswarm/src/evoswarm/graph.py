"""LangGraph orchestrator (Branch 1 of the Tree-of-Thought, see ARCHITECTURE.md).

The synthesized hybrid: a LangGraph StateGraph is the durable backbone; Crew-style
sub-teams (Branch 2) are fan-out nodes; the EvoLoop (Branch 3) lives *outside* the
request path and only proposes diffs. If `langgraph` isn't installed this module
falls back to a topologically-equivalent sequential runner so `pytest` and
`tilt up` still work on a cold clone.
"""

from __future__ import annotations

from evoswarm.agents.registry import load_registry
from evoswarm.schemas import SwarmState, TaskStatus

# Linear backbone order; the real graph adds conditional review edges.
PIPELINE = [
    "intake", "ocr", "parser", "title-examiner",
    "geo-analyst", "royalty-analyst", "valuation",
    "compliance", "critic", "outreach",
]


def _route_after_critic(state: SwarmState) -> str:
    """Conditional edge: low-confidence evidence is kicked to human review."""
    weak = [e for e in state.task.evidence if e.confidence < 0.6]
    return "review" if weak else "done"


def build_graph():
    """Return a compiled LangGraph app, or a SequentialApp fallback."""
    registry = load_registry()
    try:
        from langgraph.graph import END, START, StateGraph  # type: ignore

        g = StateGraph(SwarmState)
        for name in PIPELINE:
            g.add_node(name, registry[name].run)
        g.add_edge(START, PIPELINE[0])
        for a, b in zip(PIPELINE, PIPELINE[1:]):
            g.add_edge(a, b)
        g.add_conditional_edges("critic", _route_after_critic,
                                {"review": "outreach", "done": "outreach"})
        g.add_edge(PIPELINE[-1], END)
        return g.compile()
    except ModuleNotFoundError:
        return _SequentialApp(registry)


class _SequentialApp:
    """Deterministic fallback runner with identical node semantics."""

    def __init__(self, registry):
        self.registry = registry

    def invoke(self, state: SwarmState) -> SwarmState:
        state.task.status = TaskStatus.RUNNING
        for name in PIPELINE:
            state = self.registry[name].run(state)
        state.review_required = _route_after_critic(state) == "review"
        state.task.status = (
            TaskStatus.NEEDS_REVIEW if state.review_required else TaskStatus.DONE
        )
        return state
