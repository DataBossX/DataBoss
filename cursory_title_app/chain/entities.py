"""Party-name entity resolution for chain-of-title work.

Old county records spell the same person many ways:
  "Marvin G. Mitchell and Carrie Lou" == "M. G. Mitchell" == "Mitchell, Marvin G."
  "Louis E. Jaques" == "L. E. Jacques"  (note the surname misspelling)

We model each conveyance party as a SET of persons; each person is (surname,
given-initials). Matching tolerates initials-vs-full-given and a 1-edit surname
misspelling. This is deliberately conservative — it exists to AVOID false
"broken chain" findings, not to merge unrelated people.
"""
from __future__ import annotations

import re

_STOP = {
    "AND", "HW", "WW", "HUSBAND", "WIFE", "UX", "ET", "AL", "ETAL", "ETUX",
    "THE", "OF", "A", "AN", "JR", "SR", "II", "III", "IV", "MR", "MRS", "MS",
    "TRUST", "TRUSTEE", "ESTATE", "HEIR", "HEIRS", "DECEASED", "LIVING",
    "FAMILY", "REVOCABLE", "AKA", "FKA", "NKA", "DBA", "INC", "LLC", "LP",
    "LLP", "CO", "COMPANY", "CORP", "CORPORATION", "PARTNERS", "PARTNERSHIP",
    "ROYALTY", "OIL", "GAS", "RESOURCES", "ENERGY", "MINERALS", "PROPERTIES",
    "INVESTMENTS", "HOLDINGS", "BANK", "NATIONAL", "TRUST", "ASSOCIATION",
}
SOVEREIGN = {
    "UNITED STATES OF AMERICA", "UNITED STATES", "USA", "GENERAL LAND OFFICE",
    "STATE OF OKLAHOMA", "U S A", "US A",
}


def _lev1(a: str, b: str) -> bool:
    """True if edit distance between a and b is <= 1 (cheap, length-bounded)."""
    if a == b:
        return True
    la, lb = len(a), len(b)
    if abs(la - lb) > 1:
        return False
    if la == lb:                                   # substitution
        return sum(1 for x, y in zip(a, b) if x != y) == 1
    # insertion/deletion
    if la > lb:
        a, b = b, a
    i = j = 0
    diff = 0
    while i < len(a) and j < len(b):
        if a[i] != b[j]:
            diff += 1
            j += 1
            if diff > 1:
                return False
        else:
            i += 1
            j += 1
    return True


def is_sovereign(name: str) -> bool:
    n = re.sub(r"[^A-Z ]", " ", (name or "").upper())
    n = re.sub(r"\s+", " ", n).strip()
    return any(s in n for s in SOVEREIGN)


class Person:
    __slots__ = ("surname", "initials")

    def __init__(self, surname: str, initials: frozenset):
        self.surname = surname
        self.initials = initials

    def matches(self, other: "Person") -> bool:
        if not _lev1(self.surname, other.surname):
            return False
        if not self.initials or not other.initials:
            return True                            # surname-only: accept
        return bool(self.initials & other.initials)

    def __repr__(self):
        return f"{self.surname}<{''.join(sorted(self.initials))}>"


def persons(name: str) -> list[Person]:
    """Split a party string into individual Person tokens."""
    if not name:
        return []
    raw = re.sub(r"\b(a/?k/?a|f/?k/?a|n/?k/?a)\b", ",", name, flags=re.I)
    raw = raw.replace("&", ",")
    parts = re.split(r"\s+and\s+|[,/;\n]", raw, flags=re.I)
    out: list[Person] = []
    for part in parts:
        toks = [t for t in re.split(r"[^A-Za-z]+", part.upper()) if t]
        toks = [t for t in toks if t not in _STOP and len(t) >= 1]
        words = [t for t in toks if len(t) > 1]
        if not words:
            continue
        surname = words[-1]
        given = words[:-1] + [t for t in toks if len(t) == 1]
        initials = frozenset(g[0] for g in given if g)
        out.append(Person(surname, initials))
    return out


def any_match(a_persons: list[Person], b_persons: list[Person]) -> bool:
    return any(pa.matches(pb) for pa in a_persons for pb in b_persons)
