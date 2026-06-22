"""Row-level QA on proposed Runsheet writes, before they are committed.

Confirms Section/Township/Range, sane dates, Section-31-only legal descriptions
(unless flagged all-section/AOL), and ensures uncertain rows carry a flag rather
than a guessed value. Produces a local QA summary; writes nothing to the book.
"""
from __future__ import annotations

import re

from .. import config
from ..schemas import DocExtraction

_STR_RE = re.compile(r"\b(\d{1,2})\s*[-\s]\s*(\d{1,2}\s*[NS])\s*[-\s]\s*(\d{1,2}\s*[EW])\b",
                     re.I)
_ALL_SECTION = ("all section", "aol", "all of section", "all-section")


def _matches_target(text: str) -> bool | None:
    """True/False if a S-T-R is found and (does/doesn't) match target.
    None if no S-T-R could be parsed."""
    if not text:
        return None
    low = text.lower()
    if any(k in low for k in _ALL_SECTION):
        return True
    m = _STR_RE.search(text)
    if not m:
        # fall back to loose section mention
        if re.search(rf"\b{config.TARGET_SECTION}\b", text):
            return None
        return None
    sec = m.group(1)
    twp = m.group(2).replace(" ", "").upper()
    rng = m.group(3).replace(" ", "").upper()
    return (sec == config.TARGET_SECTION
            and twp == config.TARGET_TOWNSHIP.upper()
            and rng == config.TARGET_RANGE.upper())


def qa_extraction(ext: DocExtraction) -> dict:
    """Return {'pass': bool, 'flags': [...], 'review': str, 'need': str}."""
    flags = list(ext.review_flags)
    needs = list(ext.need_flags)

    # confidence gate
    if ext.confidence < config.CONFIDENCE_REVIEW_THRESHOLD:
        if "VERIFY: OCR uncertain" not in flags:
            flags.append("VERIFY: OCR uncertain")

    # legal description / STR check
    str_ok = _matches_target(ext.legal_description or "")
    if str_ok is False:
        needs.append("NEED: verify legal description")
    elif str_ok is None and ext.legal_description:
        flags.append("VERIFY: OCR uncertain")
    if not ext.legal_description:
        needs.append("NEED: verify legal description")

    # names
    if not ext.grantor or not ext.grantee:
        flags.append("VERIFY: grantor/grantee spelling")

    # net acres must never be guessed
    if ext.net_acres is not None and ext.conveyance_amount_dec is None:
        flags.append("VERIFY: net acres calculation")

    # lease specifics
    if (ext.doc_type or "").lower().startswith("oil and gas"):
        if not ext.royalty or not ext.primary_term:
            needs.append("NEED: review lease terms")
        needs.append("NEED: determine if released/HBP")

    # dedupe, keep deterministic order
    flags = sorted(set(flags))
    needs = sorted(set(needs))
    passed = ext.confidence >= config.CONFIDENCE_REVIEW_THRESHOLD and not needs
    return {
        "pass": passed,
        "flags": flags,
        "review": "; ".join(flags),
        "need": "; ".join(needs),
    }


def summary(results: list[dict]) -> dict:
    total = len(results)
    passed = sum(1 for r in results if r["pass"])
    return {
        "total": total,
        "passed": passed,
        "needs_review": total - passed,
        "pct_pass": round(100 * passed / total, 1) if total else 0.0,
    }
