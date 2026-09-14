"""Source-file identity matching: bind a source PDF filename to a stable key.

A Campbell filename of the shape `dddd-dddd` is genuinely ambiguous: `2023-00118`
is a modern document number, `3305-0366` is a BOOK-PAGE, and both are four digits
either side. Campbell book numbers have reached 3400+, so a book named 2023 is
possible too. The filename alone cannot settle it, so this module never guesses:
it emits every candidate identity and lets the tract index resolve which one is
real. A stem that stays ambiguous after matching is reported, not assumed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from .stable_key import normalize_docno, normalize_bookpage, StableKeyError

# Modern Campbell doc numbers began with the 4-digit recording year.
_MODERN_YEARS = range(2000, 2100)
_PAIR = re.compile(r"^#?\s*(\d{1,4}[A-Z]{0,2})-(\d{1,5})$", re.I)
_BARE = re.compile(r"^#?\s*(\d{1,7})$")

DISPOSITIONS = ("MATCHED", "NON_INDEX", "DUPLICATE", "AMBIGUOUS", "UNDETERMINED")


@dataclass(frozen=True)
class SourceFile:
    name: str
    drive_id: str = ""
    size: int = 0
    pages: int = 0

    @property
    def stem(self) -> str:
        return re.sub(r"\.pdf$", "", self.name.strip(), flags=re.I)


def candidate_keys(name: str) -> list[str]:
    """Every identity a filename could denote, most-likely first. May be empty."""
    stem = re.sub(r"\.pdf$", "", str(name).strip(), flags=re.I)
    out: list[str] = []

    if m := _PAIR.match(stem):
        left, right = m.group(1).upper(), m.group(2)
        # Book-page reading: always possible for a dddd-dddd pair.
        if len(right) <= 4:
            try:
                out.append(f"|{normalize_bookpage(f'{left}-{right}')}")
            except StableKeyError:
                pass
        # Modern doc-number reading: only when the left half is a plausible year
        # and the right half has no alpha book suffix.
        if left.isdigit() and int(left) in _MODERN_YEARS and len(right) in (4, 5):
            try:
                out.insert(0, f"{normalize_docno(f'{int(left)}-{right}')}|")
            except StableKeyError:
                pass
        return out

    if m := _BARE.match(stem):
        try:
            return [f"{normalize_docno(m.group(1))}|"]
        except StableKeyError:
            return []
    return out


def key_from_filename(name: str) -> str | None:
    """Single best-guess identity, or None. Prefer candidate_keys() when matching."""
    c = candidate_keys(name)
    return c[0] if c else None


def match_sources(files: list[SourceFile], index_keys: set[str]) -> dict:
    """Bind every source file to a tract-index key or an explicit disposition.

    Matching is half-key tolerant: a file named by doc number matches an index
    entry carrying that doc number even when the index also records a book/page.
    Ambiguous `dddd-dddd` stems are resolved by whichever candidate the index
    actually contains; if the index contains both, the file is AMBIGUOUS.
    """
    by_doc: dict[str, set[str]] = {}
    by_bp: dict[str, set[str]] = {}
    for k in index_keys:
        d, _, b = k.partition("|")
        if d:
            by_doc.setdefault(d, set()).add(k)
        if b:
            by_bp.setdefault(b, set()).add(k)

    def hits_for(cand: str) -> set[str]:
        d, _, b = cand.partition("|")
        if d:
            return by_doc.get(d, set())
        return by_bp.get(b, set())

    matched: dict[str, SourceFile] = {}
    unmatched: list[dict] = []
    seen: dict[str, str] = {}

    for f in files:
        cands = candidate_keys(f.name)
        if not cands:
            unmatched.append({"file": f.name, "disposition": "UNDETERMINED",
                              "reason": "filename carries no parseable identity"})
            continue

        resolved = [(c, hits_for(c)) for c in cands]
        live = [(c, h) for c, h in resolved if h]
        if not live:
            unmatched.append({"file": f.name, "disposition": "NON_INDEX",
                              "candidates": cands,
                              "reason": "no parsed identity appears in the tract index"})
            continue
        if len(live) > 1:
            unmatched.append({"file": f.name, "disposition": "AMBIGUOUS",
                              "candidates": [c for c, _ in live],
                              "reason": "stem reads as both a doc number and a book-page, "
                                        "and the index contains both; resolve from the face"})
            continue

        key = sorted(live[0][1])[0]
        if key in seen:
            unmatched.append({"file": f.name, "disposition": "DUPLICATE",
                              "reason": f"identity already bound by {seen[key]}"})
            continue
        seen[key] = f.name
        matched[key] = f

    return {"matched": matched, "unmatched": unmatched,
            "matched_count": len(matched), "unmatched_count": len(unmatched),
            "index_keys": len(index_keys),
            "index_keys_without_source": sorted(index_keys - set(matched))}
