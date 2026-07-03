"""ExtractorAgent — untrusted county text -> strict JSON fields.

Contract matches prompts/extractor_user.md. Untrusted input is always wrapped
via guardrails before it reaches an LLM. When no live LLM is available, a
deterministic regex heuristic produces the same JSON shape so the pipeline runs
end to end offline.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Optional

from agents.base import BaseAgent
from tools import guardrails
from tools.llm import LLMClient

ROOT = Path(__file__).resolve().parent.parent
PROMPT = ROOT / "prompts" / "extractor_user.md"

_INSTRUMENTS = [
    "Special Warranty Deed", "Warranty Deed", "Quitclaim Deed", "Mineral Deed",
    "Oil & Gas Lease", "Oil and Gas Lease", "Assignment", "Lease", "Deed",
]
_SEC_RE = re.compile(
    r"Sec(?:tion)?\.?\s*(\d+)[\s,]+T(?:ownship)?\.?\s*(\d+\s*[NS])[\s,]+R(?:ange)?\.?\s*(\d+\s*[EW])",
    re.IGNORECASE,
)
_DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_DOCNO_RE = re.compile(r"Doc(?:ument)?\s*(?:No\.?|#)\s*[:#]?\s*([A-Za-z0-9\-]+)", re.IGNORECASE)


class ExtractorAgent(BaseAgent):
    def __init__(self, model: str = "anthropic:claude-3-5-sonnet", llm: Optional[LLMClient] = None, **kw):
        super().__init__("extractor", **kw)
        self.model = model
        self.llm = llm or LLMClient(model)
        self.prompt = PROMPT.read_text(encoding="utf-8") if PROMPT.exists() else ""

    def run(self, text: str, source_url: Optional[str] = None) -> Dict[str, Any]:
        flags = guardrails.scan_for_injection(text)
        self.log_action("extract_start", chars=len(text), injection_flags=len(flags), live=self.llm.is_live)
        wrapped = guardrails.wrap_untrusted(text, source="county_document")

        if self.llm.is_live:
            raw = self.llm.complete(self.prompt, wrapped)
            data = self._parse_json(raw)
        else:
            data = self._offline_extract(text)

        if source_url and not data.get("source_url"):
            data["source_url"] = source_url
        self.log_action("extract_done", legal_short=data.get("legal_short"))
        return data

    @staticmethod
    def _parse_json(raw: str) -> Dict[str, Any]:
        start, end = raw.find("{"), raw.rfind("}")
        if start == -1 or end == -1:
            raise ValueError("LLM returned no JSON object")
        return json.loads(raw[start : end + 1])

    def _offline_extract(self, text: str) -> Dict[str, Any]:
        instrument = next((i for i in _INSTRUMENTS if i.lower() in text.lower()), None)

        legal_short = None
        m = _SEC_RE.search(text)
        if m:
            sec, twp, rng = (g.replace(" ", "") for g in m.groups())
            legal_short = f"Sec {sec} T{twp} R{rng}"

        date_m = _DATE_RE.search(text)
        recording_date = date_m.group(1) if date_m else None

        docno_m = _DOCNO_RE.search(text)
        doc_no = docno_m.group(1) if docno_m else None

        grantor = self._field(text, r"Grantor")
        grantee_raw = self._field(text, r"Grantee")
        grantee = self._split_names(grantee_raw) if grantee_raw else []

        # Fall back to "Parties: A and B" -> grantor A, grantee [B].
        if not grantor:
            pm = re.search(r"Parties?\s*[:]\s*(.+)", text, re.IGNORECASE)
            if pm:
                parts = re.split(r"\s+and\s+|,", pm.group(1))
                parts = [p.strip() for p in parts if p.strip()]
                if parts:
                    grantor = parts[0]
                if len(parts) > 1 and not grantee:
                    grantee = parts[1:]

        return {
            "doc_no": doc_no,
            "instrument": instrument,
            "recording_date": recording_date,
            "grantor": grantor,
            "grantee": grantee,
            "legal_short": legal_short,
            "addresses": [],
            "source_url": None,
        }

    @staticmethod
    def _field(text: str, label: str) -> Optional[str]:
        m = re.search(rf"{label}s?\s*[:]\s*(.+)", text, re.IGNORECASE)
        return m.group(1).strip() if m else None

    @staticmethod
    def _split_names(raw: str) -> list[str]:
        parts = re.split(r"\s+and\s+|;|,", raw)
        return [p.strip() for p in parts if p.strip()]
