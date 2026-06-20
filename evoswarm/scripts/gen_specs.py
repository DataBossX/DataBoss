#!/usr/bin/env python3
"""Materialize the 12 agent YAML specs from one manifest (DRY source of truth).

Run: `python scripts/gen_specs.py` -> writes specs/<name>.agent.yaml, each of
which is validated by evoswarm.schemas.AgentSpec before being written.
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import yaml  # noqa: E402

from evoswarm.schemas import AgentRole, AgentSpec  # noqa: E402

OPUS = "claude-opus-4-8"
HAIKU = "claude-haiku-4-5-20251001"

# name, role, model, tools, sub_team, replicas
MANIFEST = [
    ("orchestrator", "orchestrator", OPUS, ["route", "spawn"], ["intake", "critic"], 1),
    ("intake", "intake", HAIKU, ["okcounty_search", "pull_list"], [], 2),
    ("ocr", "ocr", HAIKU, ["paddleocr", "pdf_split"], [], 4),
    ("parser", "parser", OPUS, ["llamaparse", "extract_fields"], [], 3),
    ("title-examiner", "title_examiner", OPUS, ["chain_of_title", "neo4j_query"], [], 2),
    ("geo-analyst", "geo_analyst", HAIKU, ["postgis_query", "plss_resolve"], [], 2),
    ("royalty-analyst", "royalty_analyst", OPUS, ["doi_royalty_calc"], [], 2),
    ("valuation", "valuation", OPUS, ["comps", "npv_model"], [], 1),
    ("outreach", "outreach", HAIKU, ["draft_offer", "gmail_draft"], [], 2),
    ("compliance", "compliance", OPUS, ["occ_rules", "audit_log"], [], 1),
    ("critic", "critic", OPUS, ["score_evidence", "flag_review"], [], 1),
    ("evolver", "evolver", OPUS, ["run_evals", "open_pr"], [], 1),
]


def build(name, role, model, tools, sub_team, replicas) -> dict:
    spec = AgentSpec(
        name=name, role=AgentRole(role), model=model,
        temperature=0.0 if role != "outreach" else 0.4,
        max_tokens=8192, tools=tools,
        system_prompt_ref=f"prompts/{name}.md",
        sub_team=sub_team, replicas=replicas,
        cost_ceiling_usd=Decimal("10.00") if model == OPUS else Decimal("2.00"),
    )
    return spec.model_dump(mode="json")


def main() -> None:
    out = ROOT / "specs"
    out.mkdir(exist_ok=True)
    for row in MANIFEST:
        data = build(*row)
        path = out / f"{row[0]}.agent.yaml"
        path.write_text(yaml.safe_dump(data, sort_keys=False))
        print(f"wrote {path.relative_to(ROOT)}")
    print(f"\n{len(MANIFEST)} specs generated + validated")


if __name__ == "__main__":
    main()
