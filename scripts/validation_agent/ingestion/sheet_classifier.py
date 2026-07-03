"""Sheet classification with fuzzy confidence.

Classifies each worksheet into one of the known categories using sheet names,
header keywords, and fuzzy matching. Low-confidence classifications are flagged
for escalation rather than guessed.
"""

from __future__ import annotations

from dataclasses import dataclass

from rapidfuzz import fuzz

CATEGORIES = [
    "tracts",
    "ogl_register",
    "runsheets",
    "working_interest",
    "wells",
    "exception_curative",
    "qa",
    "sources",
    "unknown",
]

# Keyword signals per category (lower-cased, matched against name + headers).
_KEYWORDS: dict[str, list[str]] = {
    "tracts": ["tract", "parcel", "acreage", "legal description", "s/t/r",
               "section township range", "tracts"],
    "ogl_register": ["ogl", "oil and gas lease", "lease register", "og lease",
                     "lessor", "lessee", "royalty", "lease"],
    "runsheets": ["runsheet", "run sheet", "chain of title", "chain", "grantor",
                  "grantee", "instrument", "conveyance"],
    "working_interest": ["working interest", "wi", "net revenue interest",
                         "nri", "wi/depth", "working-interest", "wi assignment"],
    "wells": ["well", "api number", "spud", "hbp", "held by production",
              "completion", "wellbore"],
    "exception_curative": ["exception", "curative", "requirement", "defect",
                           "title requirement", "cure"],
    "qa": ["qa", "quality", "review", "checklist", "validation"],
    "sources": ["source", "document index", "book/page", "book page",
                "instrument index", "citations", "references"],
}

# Categories that require a firm classification (missing => fatal escalation).
CORE_CATEGORIES = {"tracts", "ogl_register", "working_interest"}

LOW_CONFIDENCE_THRESHOLD = 55.0


@dataclass
class SheetClassification:
    sheet_name: str
    category: str
    confidence: float
    signals: list[str]
    escalate: bool


def _score_category(text: str, keywords: list[str]) -> tuple[float, list[str]]:
    best = 0.0
    hits: list[str] = []
    for kw in keywords:
        if kw in text:
            best = max(best, 100.0)
            hits.append(kw)
            continue
        ratio = fuzz.partial_ratio(kw, text)
        if ratio >= 80:
            hits.append(f"{kw}~{ratio:.0f}")
        best = max(best, ratio)
    return best, hits


def classify_sheet(sheet_name: str, header_row: list[str]) -> SheetClassification:
    text = " ".join([sheet_name] + list(header_row)).lower()
    scores: dict[str, tuple[float, list[str]]] = {}
    for cat, kws in _KEYWORDS.items():
        scores[cat] = _score_category(text, kws)

    best_cat = max(scores, key=lambda c: scores[c][0])
    best_score, signals = scores[best_cat]

    if best_score < LOW_CONFIDENCE_THRESHOLD:
        return SheetClassification(
            sheet_name=sheet_name, category="unknown",
            confidence=round(best_score, 1), signals=signals, escalate=True,
        )
    # Firm classification, but note low-ish confidence as escalate flag.
    escalate = best_score < 70.0
    return SheetClassification(
        sheet_name=sheet_name, category=best_cat,
        confidence=round(best_score, 1), signals=signals, escalate=escalate,
    )


def classify_workbook(manifest) -> dict:
    """Classify all sheets in a manifest. Returns a summary dict."""
    classifications: list[SheetClassification] = []
    for s in manifest.sheets:
        classifications.append(classify_sheet(s.name, s.header_row))

    found_categories: dict[str, list[str]] = {}
    for c in classifications:
        found_categories.setdefault(c.category, []).append(c.sheet_name)

    missing_core = [c for c in CORE_CATEGORIES if c not in found_categories]

    return {
        "classifications": [c.__dict__ for c in classifications],
        "found_categories": found_categories,
        "missing_core": missing_core,
        "low_confidence": [
            c.sheet_name for c in classifications if c.escalate
        ],
    }
