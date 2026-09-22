"""Split a client Document Type that illegally embeds legal/depth/scope narrative.

The controlling Penterra output standard requires Document Type to be a clean
instrument/action name. Source-supported qualifications belong in Legal.
"""

from __future__ import annotations


def split_document_type(value: str) -> tuple[str, str]:
    """Return (clean_type, qualification).

    Only the first ``" - "`` separator is used. No parties, dates, or legal
    locations are inferred. Empty input stays empty.
    """
    text = (value or "").strip()
    if not text:
        return "", ""
    if " - " not in text:
        return text, ""
    clean, qual = text.split(" - ", 1)
    return clean.strip(), qual.strip()


def merge_legal(legal: str, qualification: str) -> str:
    """Append a qualification to Legal if it is not already present."""
    legal = (legal or "").rstrip(" ;")
    qualification = (qualification or "").strip()
    if not qualification:
        return legal
    if qualification in legal:
        return legal
    return f"{legal}; {qualification}" if legal else qualification
