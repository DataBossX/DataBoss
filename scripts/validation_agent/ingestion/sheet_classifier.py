"""Sheet classification via name + header keyword scoring and fuzzy matching.

Low-confidence classifications are flagged for escalation. The classifier never
guesses silently: an ambiguous sheet is labelled ``unknown`` with its best
guess and confidence recorded so a human can decide.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from rapidfuzz import fuzz

from .workbook_ingestor import SheetView, WorkbookStructure

# Category -> keyword weights. Matched against sheet name + header tokens.
CATEGORY_KEYWORDS: Dict[str, Dict[str, float]] = {
    "tracts": {"tract": 3.0, "tracts": 3.0, "acreage": 1.5, "legal description": 1.5,
               "gross acres": 1.5, "net acres": 1.5, "str": 1.0, "section": 1.0},
    "ogl_register": {"ogl": 3.0, "oil and gas lease": 3.0, "lease register": 3.0,
                     "lessor": 1.5, "lessee": 1.5, "lease": 1.0, "royalty": 1.0,
                     "book": 0.5, "page": 0.5},
    "runsheet": {"runsheet": 3.0, "run sheet": 3.0, "chain": 2.0, "grantor": 1.5,
                 "grantee": 1.5, "instrument": 1.0, "book": 0.5, "page": 0.5,
                 "recording": 1.0, "conveyance": 1.0},
    "working_interest": {"working interest": 3.0, "wi": 2.0, "nri": 1.5, "net revenue": 1.5,
                         "assignment": 1.5, "wellbore": 1.0, "depth": 1.0},
    "wells": {"well": 3.0, "wells": 3.0, "api": 1.5, "spud": 1.0, "hbp": 2.0,
              "production": 1.5, "status": 0.5, "completion": 1.0},
    "exception_curative": {"exception": 3.0, "curative": 3.0, "requirement": 1.5,
                           "defect": 1.5, "objection": 1.0},
    "qa": {"qa": 3.0, "quality": 2.0, "review": 1.0, "checklist": 1.5, "qc": 2.0},
    "sources": {"source": 3.0, "sources": 3.0, "document": 1.5, "reference": 1.0,
                "citation": 1.5, "exhibit": 1.0},
}

# Confidence below this routes the sheet to escalation.
LOW_CONFIDENCE_THRESHOLD = 0.35
# A best score below this (absolute) is treated as too weak to trust, even if
# it dominates the (near-zero) field — e.g. a lone fuzzy match.
MIN_ABSOLUTE_SCORE = 2.0


@dataclass
class SheetClassification:
    sheet_name: str
    index: int
    category: str
    confidence: float
    scores: Dict[str, float]
    escalate: bool
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sheet_name": self.sheet_name,
            "index": self.index,
            "category": self.category,
            "confidence": round(self.confidence, 4),
            "scores": {k: round(v, 4) for k, v in self.scores.items()},
            "escalate": self.escalate,
            "reason": self.reason,
        }


@dataclass
class ClassificationReport:
    classifications: List[SheetClassification] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "classifications": [c.to_dict() for c in self.classifications],
            "counts": self.category_counts(),
        }

    def category_counts(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for c in self.classifications:
            counts[c.category] = counts.get(c.category, 0) + 1
        return counts

    def by_category(self, category: str) -> List[SheetClassification]:
        return [c for c in self.classifications if c.category == category]

    def tract_sheets(self) -> List[SheetClassification]:
        return self.by_category("tracts")

    def has_low_confidence(self) -> bool:
        return any(c.escalate for c in self.classifications)


def _score_sheet(sheet: SheetView) -> Dict[str, float]:
    name = (sheet.name or "").lower()
    header_text = " ".join(h.lower() for h in sheet.headers)
    haystack = f"{name} {header_text}"
    scores: Dict[str, float] = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        total = 0.0
        for kw, weight in keywords.items():
            if kw in haystack:
                total += weight
            elif len(kw) >= 4:
                # fuzzy partial credit against name (catches abbreviations/typos).
                # Restricted to longer keywords and a high ratio so incidental
                # tokens (e.g. the default "Sheet1") don't earn spurious credit.
                ratio = fuzz.ratio(kw, name) / 100.0
                if ratio >= 0.9:
                    total += weight * 0.5
        scores[category] = total
    return scores


def classify_sheet(sheet: SheetView) -> SheetClassification:
    scores = _score_sheet(sheet)
    best_category = max(scores, key=lambda k: scores[k])
    best_score = scores[best_category]
    total = sum(scores.values())
    confidence = (best_score / total) if total > 0 else 0.0

    if best_score < MIN_ABSOLUTE_SCORE or confidence < LOW_CONFIDENCE_THRESHOLD:
        return SheetClassification(
            sheet_name=sheet.name,
            index=sheet.index,
            category="unknown",
            confidence=round(confidence, 4),
            scores=scores,
            escalate=True,
            reason=(
                "low classification confidence; best guess "
                f"'{best_category}' scored {best_score:.2f} "
                f"(confidence {confidence:.2f} < {LOW_CONFIDENCE_THRESHOLD})"
            ),
        )
    return SheetClassification(
        sheet_name=sheet.name,
        index=sheet.index,
        category=best_category,
        confidence=round(confidence, 4),
        scores=scores,
        escalate=False,
        reason=f"classified as '{best_category}' with confidence {confidence:.2f}",
    )


def classify_workbook(structure: WorkbookStructure) -> ClassificationReport:
    report = ClassificationReport()
    for sheet in structure.sheets:
        report.classifications.append(classify_sheet(sheet))
    return report
