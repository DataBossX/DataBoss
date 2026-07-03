"""SheetClassifier -- categorize each tab into the fixed taxonomy of sheets.

Section 3 requires categorizing tabs exactly into: tracts, OGL registers,
runsheets, working-interest, wells, exception/curative, QA, and sources.

Classification is deterministic and evidence-based: it scores the tab name and
header row against keyword sets and picks the strongest match.  It never
guesses a legal fact -- it only labels the structural role of a sheet.
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass

from .workbook_ingestor import RawSheet


class SheetCategory(enum.Enum):
    TRACT = "tract"
    OGL_REGISTER = "ogl_register"
    RUNSHEET = "runsheet"
    WORKING_INTEREST = "working_interest"
    WELLS = "wells"
    EXCEPTION_CURATIVE = "exception_curative"
    QA = "qa"
    SOURCES = "sources"
    UNKNOWN = "unknown"


# Keyword sets scored against the (lowercased) tab name and headers.
_KEYWORDS: dict[SheetCategory, tuple[str, ...]] = {
    SheetCategory.TRACT: ("tract", "parcel", "tract summary", "netacres", "net acres"),
    SheetCategory.OGL_REGISTER: ("ogl", "oil and gas lease", "lease register",
                                 "lease schedule", "leases"),
    SheetCategory.RUNSHEET: ("runsheet", "run sheet", "chain of title",
                             "grantor", "grantee", "conveyance"),
    SheetCategory.WORKING_INTEREST: ("working interest", "wi ", "w.i.", "wi_",
                                     "net revenue", "nri", "assignment"),
    SheetCategory.WELLS: ("well", "spud", "completion", "hbp", "production",
                          "held by production"),
    SheetCategory.EXCEPTION_CURATIVE: ("exception", "curative", "requirement",
                                       "defect", "title requirement"),
    SheetCategory.QA: ("qa", "qc", "quality", "review", "checklist"),
    SheetCategory.SOURCES: ("source", "instrument", "book/page", "book page",
                            "inst #", "instrument number", "reference"),
}

# A tract tab is frequently literally named after a tract number ("Tract 1",
# "T-01", "31-12N-24W").  Recognise those name shapes explicitly.
_TRACT_NAME_RE = re.compile(r"^\s*(tract|t)[\s\-_]*\d+", re.IGNORECASE)
_LEGAL_DESC_RE = re.compile(r"\b\d{1,2}[- ]?\d{1,2}[nsew][- ]?\d{1,3}[nsew]\b",
                            re.IGNORECASE)


@dataclass
class Classification:
    sheet: str
    category: SheetCategory
    score: int
    signals: list[str]


class SheetClassifier:
    def classify(self, sheet: RawSheet) -> Classification:
        name = sheet.name.lower()
        header_blob = " ".join(h.lower() for h in sheet.headers)
        haystack = f"{name} || {header_blob}"

        scores: dict[SheetCategory, int] = {c: 0 for c in _KEYWORDS}
        signals: list[str] = []

        for category, keywords in _KEYWORDS.items():
            for kw in keywords:
                if kw in haystack:
                    weight = 2 if kw in name else 1
                    scores[category] += weight
                    signals.append(f"{category.value}:{kw}")

        # Name-shape heuristics for tract tabs.
        if _TRACT_NAME_RE.match(sheet.name) or _LEGAL_DESC_RE.search(sheet.name):
            scores[SheetCategory.TRACT] += 3
            signals.append("tract:name-shape")

        best = max(scores.items(), key=lambda kv: kv[1])
        category = best[0] if best[1] > 0 else SheetCategory.UNKNOWN
        return Classification(sheet=sheet.name, category=category,
                              score=best[1], signals=signals)

    def classify_all(self, sheets: list[RawSheet]) -> list[Classification]:
        return [self.classify(s) for s in sheets]
