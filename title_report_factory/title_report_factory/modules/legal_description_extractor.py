"""legal_description_extractor -- normalize legal descriptions & detect subject."""
from __future__ import annotations

import re

_QTR = r"(?:[NSEW]/?2|[NSEW][EW]/?4|NE|NW|SE|SW|lots?\s*[\d,\sand-]+)"


def normalize_str(section: str, township: str, rng: str) -> str:
    return f"{section}-{township}-{rng}"


def matches_subject(text: str, subject: dict) -> bool:
    """True if the legal description text appears to reference the subject section."""
    if not text:
        return False
    t = text.upper().replace(" ", "")
    sec = subject["section"]
    twp = subject["township"].upper()
    rng = subject["range"].upper()
    # accept 27-11N-25W, 2711N25W, S27T11NR25W etc.
    patterns = [
        rf"{sec}-?{twp}-?{rng}",
        rf"S(?:EC)?{sec}T{twp}R{rng}",
        rf"{twp}{rng}{sec}",
    ]
    return any(re.search(p, t) for p in patterns)


def extract_quarter_calls(text: str) -> str:
    """Pull quarter/quarter-quarter calls (e.g. 'NE/4', 'W/2 SE')."""
    if not text:
        return ""
    found = re.findall(_QTR, text, flags=re.IGNORECASE)
    seen, out = set(), []
    for f in found:
        key = f.upper().replace(" ", "")
        if key not in seen:
            seen.add(key)
            out.append(f.strip())
    return ", ".join(out)


def tract_for_quarter(legal: str) -> str:
    """Map a leading quarter call to one of the four 160-acre tracts.

    Only returns a tract when the description *begins* with a real quarter call
    (e.g. 'NE/4 ...'). A whole-section description ('Section 27-11N-25W') returns
    '' so it is not misfiled — note 'SECTION' starts with 'SE' and must not match.
    """
    t = (legal or "").upper().strip()
    if t.startswith("SECTION") or t.startswith("ALL"):
        return ""
    m = re.match(r"\s*(NE|NW|SE|SW)\s*/?\s*4\b", t)
    if m:
        return f"{m.group(1)}/4"
    return ""
