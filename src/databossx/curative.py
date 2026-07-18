"""Curative recommendations.

A defect report tells an examiner *what* is wrong; a curative worklist tells them
*what to do about it*. This maps each defect category (and a few specific detail
patterns) to a concrete, plain-language curative action. These are standard
title-curative steps, not legal advice or a conclusion -- the human examiner
still decides and signs off.
"""

from __future__ import annotations

from typing import Dict, List

_BY_CATEGORY: Dict[str, str] = {
    "examiner-review":
        "Pull the recording and re-examine the instrument; confirm the parties, "
        "interest conveyed, and legal description against the record.",
    "chain-break":
        "Locate the instrument (or its recording data) that links this document "
        "across the OGL register and the runsheet. If none exists, document the "
        "gap and obtain the missing conveyance.",
    "ownership-8/8":
        "Reconcile the mineral estate to a full 8/8: find the instrument(s) that "
        "convey the missing or excess undivided interest, or confirm and record "
        "an outstanding unleased interest.",
    "ownership-review":
        "Verify the owner's mineral interest, royalty, and lessee against the "
        "source instrument, and supply the value the calculator could not parse.",
    "missing-evidence":
        "Obtain a legible copy or run OCR on the source document so its text can "
        "be examined, then re-run once the evidence is readable.",
}

_DEFAULT = ("Examiner review required; verify the item against the source record "
            "before release.")


def recommend(category: str, detail: str = "") -> str:
    """Return a curative action for a defect category (+ optional detail)."""
    low = (detail or "").lower()
    if "over-conveyance" in low or "only held" in low:
        return ("Over-conveyance: the grantor purported to convey more than the "
                "record shows they held. Confirm the grantor's actual interest "
                "and whether a prior conveyance or reservation is missing from "
                "the chain before relying on any downstream interest.")
    if "grantor" in low and "prior grantee" in low:
        return ("Chain-of-title break: this grantor is not the prior grantee. "
                "Locate the intervening conveyance that vests title in this "
                "grantor, or document the missing link.")
    return _BY_CATEGORY.get(category, _DEFAULT)


def enrich_defects(defects: List[Dict[str, object]]) -> None:
    """Add a ``curative`` recommendation to each defect in place (idempotent)."""
    for d in defects:
        if not d.get("curative"):
            d["curative"] = recommend(str(d.get("category", "")),
                                      str(d.get("detail", "")))
