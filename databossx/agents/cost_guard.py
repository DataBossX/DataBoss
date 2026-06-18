"""Cost guard for DataBossX.

Before any paid API call, estimate calls/cost and refuse if over budget.
Prefers local/mock providers for drafts, classification and tests.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..core import paths

# Rough per-call cost estimates (USD). Conservative placeholders; tune per provider.
COST_PER_CALL = {
    "mock": 0.0,
    "local": 0.0,
    "gemini-ocr": 0.01,
    "claude": 0.03,
    "openai": 0.03,
}


@dataclass
class CostEstimate:
    provider: str
    calls: int
    per_call: float
    total: float
    budget: float
    within_budget: bool


def estimate(provider: str, calls: int, budget: float = 1.0) -> CostEstimate:
    per = COST_PER_CALL.get(provider, 0.05)
    total = round(per * calls, 4)
    return CostEstimate(provider, calls, per, total, budget, total <= budget)


def render_report(est: CostEstimate, ts: str) -> str:
    verdict = "✅ WITHIN BUDGET" if est.within_budget else "🛑 OVER BUDGET — STOP"
    return "\n".join([
        f"# Cost Guard — {ts}",
        "",
        f"- Provider: `{est.provider}`",
        f"- Estimated calls: {est.calls}",
        f"- Per-call estimate: ${est.per_call:.4f}",
        f"- Total estimate: **${est.total:.4f}**",
        f"- Budget: ${est.budget:.2f}",
        "",
        f"**{verdict}**",
        "",
        "Policy: prefer local/mock for drafts, classification and tests; use paid",
        "models only for OCR, critical refactor, final review, complex debugging.",
        "",
    ])


def run(provider: str, calls: int, budget: float = 1.0, ts: str | None = None) -> tuple[CostEstimate, "object"]:
    paths.ensure_dirs()
    ts = ts or paths.timestamp()
    est = estimate(provider, calls, budget)
    out = paths.REPORTS / f"cost_guard_{ts}.md"
    out.write_text(render_report(est, ts))
    return est, out
