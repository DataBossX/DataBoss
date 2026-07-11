"""Evidence ledger (Move #4) with source-authority ranking (Move #21) and
multi-axis confidence (Move #22).

No ownership, lease, well, or working-interest conclusion may exist without
evidence entries behind it. Conclusions referencing zero evidence are
rejected. Confidence is per-axis, never one vague percentage.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

from .util import stable_id, utcnow_iso

# Move #21 — lower rank = more authoritative. Never treat sources as equal.
AUTHORITY = {
    1: "recorded_instrument_image",
    2: "official_index",            # county or federal index
    3: "court_or_agency_order",
    4: "client_controlling_data",
    5: "prior_verified_report",
    6: "tax_record",
    7: "ai_extraction",
    8: "unverified_note",
}

CONFIDENCE_AXES = ("extraction", "identity_match", "legal_description", "calculation")

VERIFICATION_STATUSES = ("unverified", "ai_verified", "human_verified", "rejected")


@dataclass
class EvidenceEntry:
    source_document: str                 # asset_id or explicit citation
    authority_rank: int                  # key into AUTHORITY
    extracted_text: str = ""
    book_page: str = ""                  # e.g. "1014/75"
    instrument_number: str = ""
    image_reference: str = ""            # e.g. "Img 4893" or page number
    legal_description: str = ""
    effective_date: str = ""
    confidence: dict = field(default_factory=dict)   # axis -> 0.0..1.0
    verification_status: str = "unverified"
    explanation: str = ""
    evidence_id: str = ""
    recorded_at: str = field(default_factory=utcnow_iso)

    def __post_init__(self):
        if self.authority_rank not in AUTHORITY:
            raise ValueError(f"unknown authority rank {self.authority_rank}; "
                             f"valid: {sorted(AUTHORITY)}")
        if self.verification_status not in VERIFICATION_STATUSES:
            raise ValueError(f"unknown verification status {self.verification_status!r}")
        for axis, value in self.confidence.items():
            if axis not in CONFIDENCE_AXES:
                raise ValueError(f"unknown confidence axis {axis!r}; valid: {CONFIDENCE_AXES}")
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"confidence {axis}={value} outside 0..1")
        if not self.evidence_id:
            self.evidence_id = stable_id(
                "EVD", self.source_document, self.book_page,
                self.instrument_number, self.extracted_text)


@dataclass
class Conclusion:
    """A title conclusion (ownership, lease, WI…) that cites its evidence."""
    statement: str
    evidence_ids: list = field(default_factory=list)
    kind: str = "ownership"              # ownership | lease | well | working_interest | other
    verification_status: str = "unverified"
    explanation: str = ""
    conclusion_id: str = ""
    recorded_at: str = field(default_factory=utcnow_iso)


class EvidenceLedger:
    """Append-only JSONL store; one file per project keeps diffs reviewable."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.entries: dict[str, EvidenceEntry] = {}
        self.conclusions: dict[str, Conclusion] = {}
        if self.path.exists():
            self._load()

    def _load(self) -> None:
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            kind = rec.pop("_type")
            if kind == "evidence":
                e = EvidenceEntry(**rec)
                self.entries[e.evidence_id] = e
            elif kind == "conclusion":
                c = Conclusion(**rec)
                self.conclusions[c.conclusion_id] = c

    def _append(self, kind: str, obj) -> None:
        rec = {"_type": kind, **asdict(obj)}
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # -- API -----------------------------------------------------------------

    def add_evidence(self, entry: EvidenceEntry) -> str:
        self.entries[entry.evidence_id] = entry
        self._append("evidence", entry)
        return entry.evidence_id

    def add_conclusion(self, conclusion: Conclusion) -> str:
        """Rejects conclusions with no evidence or with unknown evidence IDs."""
        if not conclusion.evidence_ids:
            raise ValueError("conclusion rejected: no supporting evidence "
                             f"({conclusion.statement!r})")
        missing = [e for e in conclusion.evidence_ids if e not in self.entries]
        if missing:
            raise ValueError(f"conclusion rejected: unknown evidence ids {missing}")
        if not conclusion.conclusion_id:
            conclusion.conclusion_id = stable_id(
                "CNC", conclusion.statement, *sorted(conclusion.evidence_ids))
        self.conclusions[conclusion.conclusion_id] = conclusion
        self._append("conclusion", conclusion)
        return conclusion.conclusion_id

    def best_authority(self, conclusion_id: str) -> int:
        """The strongest (lowest) authority rank backing a conclusion."""
        c = self.conclusions[conclusion_id]
        return min(self.entries[e].authority_rank for e in c.evidence_ids)

    def provenance(self, conclusion_id: str) -> dict:
        """Move #25 — everything behind a conclusion, ready for display."""
        c = self.conclusions[conclusion_id]
        return {
            "statement": c.statement,
            "kind": c.kind,
            "verification_status": c.verification_status,
            "explanation": c.explanation,
            "evidence": [asdict(self.entries[e]) for e in c.evidence_ids],
        }

    def unverified_conclusions(self) -> list[Conclusion]:
        return [c for c in self.conclusions.values()
                if c.verification_status not in ("human_verified",)]
