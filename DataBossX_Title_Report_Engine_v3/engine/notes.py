"""Task 12 -- landman note helpers.

Notes are attached to chain events and owners by the chain engine as it runs
(that is where the reasoning lives). This module only provides small, reusable
note-composition helpers so the phrasing stays consistent and never turns into
generic filler.
"""

from __future__ import annotations

from typing import Iterable


def compose(*parts: str) -> str:
    return " ".join(p.strip() for p in parts if p and p.strip())


def assumption(text: str) -> str:
    text = text.strip()
    return text if text.startswith("ASSUMPTION:") else f"ASSUMPTION: {text}"


def needs_verification(text: str) -> str:
    text = text.strip()
    return text if text.startswith("Needs Verification:") else f"Needs Verification: {text}"


# Canonical phrasings reused across the workbook (kept short, reviewer-useful).
ASSN_LEASEHOLD = "ASSN transfers leasehold only; mineral ownership unchanged."
OGL_CARRY = ("OGL carried from lessor row per Tract 1 pattern; matched to OGL schedule "
             "by lessor/date/legal.")
ALL_RTI = ("Grantor conveyed all right, title and interest; conveyance limited to grantor's "
           "calculated remaining interest.")


def dedupe(notes: Iterable[str]) -> str:
    seen, out = set(), []
    for n in notes:
        n = (n or "").strip()
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return " ".join(out)
