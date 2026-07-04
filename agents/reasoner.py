"""ReasonerAgent — chronological extracted docs -> ownership decision.

Contract matches prompts/reasoner_user.md. The offline path is a faithful
implementation of the rules in that prompt, so decisions are deterministic and
auditable without an LLM.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from agents.base import BaseAgent
from tools.llm import LLMClient

ROOT = Path(__file__).resolve().parent.parent
PROMPT = ROOT / "prompts" / "reasoner_user.md"

VALID_STATUS = {
    "Current owner of record",
    "Assigned out",
    "Leased HBP",
    "Unknown—needs manual",
}


class ReasonerAgent(BaseAgent):
    def __init__(self, model: str = "openai:gpt-4o", llm: Optional[LLMClient] = None, **kw):
        super().__init__("reasoner", **kw)
        self.model = model
        self.llm = llm or LLMClient(model)
        self.prompt = PROMPT.read_text(encoding="utf-8") if PROMPT.exists() else ""

    def run(self, docs: List[Dict[str, Any]], owner: str, section: str = "Sec 1") -> Dict[str, Any]:
        self.log_action("reason_start", n_docs=len(docs), owner=owner, section=section, live=self.llm.is_live)
        if self.llm.is_live:
            user = json.dumps({"owner": owner, "section": section, "docs": docs})
            decision = self._parse_json(self.llm.complete(self.prompt, user))
        else:
            decision = self._offline_reason(docs, owner, section)
        self.log_action("reason_done", status=decision.get("status"), confidence=decision.get("confidence"))
        return decision

    @staticmethod
    def _parse_json(raw: str) -> Dict[str, Any]:
        start, end = raw.find("{"), raw.rfind("}")
        return json.loads(raw[start : end + 1])

    def _offline_reason(self, docs: List[Dict[str, Any]], owner: str, section: str) -> Dict[str, Any]:
        # Prefer the canonical rule engine in automation/status_logic.py so the
        # ownership rules live in exactly one place (it also sorts by recording
        # date). Fall back to the local implementation if it can't be imported.
        try:
            from automation.status_logic import decide_status_rule_based

            decision = decide_status_rule_based(owner, docs)
            if decision.get("status") in VALID_STATUS:
                return decision
        except Exception:  # noqa: BLE001 - any import/runtime issue -> fallback
            pass
        return self._fallback_reason(docs, owner, section)

    def _fallback_reason(self, docs: List[Dict[str, Any]], owner: str, section: str) -> Dict[str, Any]:
        owner_l = owner.lower()

        def in_section(d: Dict[str, Any]) -> bool:
            return section.lower() in (d.get("legal_short") or "").lower()

        def is_grantee(d: Dict[str, Any]) -> bool:
            return any(owner_l in str(g).lower() for g in (d.get("grantee") or []))

        def is_grantor(d: Dict[str, Any]) -> bool:
            return owner_l in str(d.get("grantor") or "").lower()

        relevant = [d for d in docs if in_section(d)]
        if not relevant:
            return self._decision(
                "Unknown—needs manual", 0.6,
                f"No instruments found for {owner} in {section}; manual review required.",
            )

        last = relevant[-1]
        inst = (last.get("instrument") or "").lower()

        if is_grantor(last) and ("assign" in inst or "deed" in inst):
            return self._decision(
                "Assigned out", 0.85,
                f"Latest {section} instrument ({last.get('instrument')}) shows {owner} "
                f"as grantor conveying out; interest assigned out.",
            )
        if is_grantee(last) and ("deed" in inst or "assign" in inst):
            return self._decision(
                "Current owner of record", 0.85,
                f"Latest {section} instrument ({last.get('instrument')}) names {owner} "
                f"as grantee with no later conveyance out; current owner of record.",
            )
        if "lease" in inst and is_grantor(last):
            return self._decision(
                "Leased HBP", 0.7,
                f"Latest {section} instrument is an oil & gas lease with {owner} as "
                f"lessor and no later deed out; leased, presumed held by production.",
            )
        return self._decision(
            "Unknown—needs manual", 0.6,
            f"{section} chain for {owner} is ambiguous; manual review required.",
        )

    @staticmethod
    def _decision(status: str, confidence: float, explanation: str) -> Dict[str, Any]:
        assert status in VALID_STATUS
        return {"status": status, "confidence": confidence, "explanation": explanation}
