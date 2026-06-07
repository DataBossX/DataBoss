"""document_classifier -- rule-based instrument classification.

Maps a raw document-type / description string onto a normalized class and a
title-relevance category. Deterministic and explainable (no black box).
"""
from __future__ import annotations

import re

# Order matters: more specific patterns first.
_RULES: list[tuple[str, str, str]] = [
    (r"wellbore assignment", "Wellbore Assignment", "Possible divestiture/exclusion"),
    (r"partial (release|assignment)", "Partial Assignment/Release", "Leasehold transfer"),
    (r"assignment", "Assignment", "Leasehold/interest transfer"),
    (r"oil(,| and| & ).*lease|oil and gas lease|\bogl\b|paid-up.*lease|form 88", "Oil & Gas Lease", "Leasehold creation"),
    (r"\blease\b", "Oil & Gas Lease", "Leasehold creation"),
    (r"mineral deed", "Mineral Deed", "Mineral conveyance"),
    (r"warranty deed", "Warranty Deed", "Surface/mineral conveyance"),
    (r"quit ?claim|qcd", "Quit Claim Deed", "Conveyance (quitclaim)"),
    (r"sheriff deed", "Sheriff Deed", "Conveyance (judicial)"),
    (r"\bdeed\b", "Deed", "Conveyance"),
    (r"merger", "Merger", "Corporate succession"),
    (r"conveyance", "Conveyance", "Conveyance"),
    (r"agreement", "Agreement", "Contractual / possible non-title"),
    (r"affidavit of pooling|pooling", "Pooling/Affidavit", "Pooling/HBP support"),
    (r"unitization|unit", "Unitization", "Unit/HBP support"),
    (r"affidavit", "Affidavit", "Notice/support"),
    (r"memorandum", "Memorandum", "Notice/support"),
    (r"release", "Release", "Lease release/termination"),
    (r"amendment", "Amendment", "Encumbrance/amendment"),
    (r"mortgage|deed of trust|lien|keybank", "Mortgage/Lien", "Encumbrance"),
    (r"judgment|lis pendens|execution|order|transfer|rel judg", "Judicial/Financial", "Lien/judgment (likely non-mineral)"),
    (r"probate|estate|will|guardian", "Probate", "Devolution of title"),
]


def classify(doc_type: str, extra: str = "") -> tuple[str, str]:
    """Return (normalized_class, title_relevance_category)."""
    text = f"{doc_type or ''} {extra or ''}".lower()
    for pattern, cls, category in _RULES:
        if re.search(pattern, text):
            return cls, category
    return ("Unclassified", "Needs Review")
