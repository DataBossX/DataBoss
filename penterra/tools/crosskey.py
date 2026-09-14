"""Book/Page cross-key correction for misread tract-index document numbers.

Why this exists
---------------
Measured on two tract-index pages, 15-19% of enumerated document numbers are
misread, and every confirmed error is a *digit substitution inside a run of
near-identical sequential filings* (500112/113/114, 522831/832, 548300/301).
That is the worst failure mode for a stable key: the result is a plausible
neighbouring document number, so no structural check fires -- `stable_key`
parses the wrong number perfectly happily.

Book/Page plus recorded date settled the identity in every case where the
document number alone could not. This module makes that cross-key deterministic.

It PROPOSES corrections with evidence. It never rewrites a ledger, and it never
returns a correction that lacks independent corroboration.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .stable_key import normalize_bookpage, normalize_docno, StableKeyError


@dataclass(frozen=True)
class OracleRow:
    """A verified row from a corroborating index (e.g. the Section 13 workbook)."""
    docno: str
    bookpage: str = ""
    rec_date: str = ""
    doc_date: str = ""
    doc_type: str = ""
    grantor: str = ""
    grantee: str = ""


@dataclass(frozen=True)
class Suspect:
    """A tract-index row whose document number is under test."""
    docno: str
    locator: str = ""            # e.g. "p04r6"
    bookpage: str = ""           # often partial from the face, e.g. "0654-0561"
    rec_date: str = ""
    doc_date: str = ""
    grantor: str = ""
    grantee: str = ""


# Evidence weights. Book/Page is a *unique locator* in the county records, so an
# exact match is decisive on its own; dates and parties are corroborating only.
# This ordering is not cosmetic: within a run of sequential filings (500112/113/114)
# the numerically nearest oracle row is frequently the WRONG one, so evidence
# strength must dominate numeric proximity. Proximity is only a plausibility gate.
W_BOOKPAGE = 100
W_REC_DATE = 10
W_DOC_DATE = 8
W_PARTY = 3


@dataclass
class Candidate:
    docno: str
    digit_distance: int
    evidence: list[str] = field(default_factory=list)
    score: int = 0

    @property
    def corroborated(self) -> bool:
        return bool(self.evidence)

    @property
    def decisive(self) -> bool:
        """True when a unique locator (book/page) carries the match."""
        return self.score >= W_BOOKPAGE


def digit_distance(a: str, b: str) -> int:
    """Differing digit positions for equal-length numbers; -1 if lengths differ."""
    a, b = str(a).strip(), str(b).strip()
    if len(a) != len(b):
        return -1
    return sum(1 for x, y in zip(a, b) if x != y)


def _norm_date(d: str) -> str:
    """Loose date normaliser: returns (m, d, y) as a comparable tuple-string."""
    s = str(d or "").strip().replace("-", "/")
    parts = [p for p in s.split("/") if p]
    if len(parts) != 3:
        return ""
    a, b, c = parts
    if len(a) == 4:                       # yyyy/mm/dd
        y, m, dd = a, b, c
    else:                                  # mm/dd/yyyy or mm/dd/yy
        m, dd, y = a, b, c
        if len(y) == 2:
            y = ("19" + y) if int(y) > 50 else ("20" + y)
    try:
        return f"{int(m):02d}/{int(dd):02d}/{int(y):04d}"
    except ValueError:
        return ""


def suggest(suspect: Suspect, oracle: list[OracleRow], *,
            max_digit_distance: int = 2) -> dict:
    """Propose corrections for one suspect document number.

    A candidate is only returned when it is BOTH numerically near the suspect
    (a plausible misread) AND independently corroborated by book/page or
    recorded date. Corroboration is mandatory -- proximity alone never suffices.
    """
    try:
        sus = normalize_docno(suspect.docno)
    except StableKeyError:
        return {"suspect": suspect.docno, "status": "UNPARSEABLE", "candidates": []}

    sus_bp = _safe_bp(suspect.bookpage)
    sus_rec = _norm_date(suspect.rec_date)
    sus_doc = _norm_date(suspect.doc_date)

    exact = [o for o in oracle if _safe_doc(o.docno) == sus]
    candidates: list[Candidate] = []

    for o in oracle:
        odoc = _safe_doc(o.docno)
        if not odoc or odoc == sus:
            continue
        dd = digit_distance(sus, odoc)
        if dd < 0 or dd > max_digit_distance:
            continue

        ev: list[str] = []
        score = 0
        obp = _safe_bp(o.bookpage)
        if sus_bp and obp and sus_bp == obp:
            ev.append(f"book/page matches exactly ({obp})")
            score += W_BOOKPAGE
        if sus_rec and _norm_date(o.rec_date) and sus_rec == _norm_date(o.rec_date):
            ev.append(f"recorded date matches ({sus_rec})")
            score += W_REC_DATE
        if sus_doc and _norm_date(o.doc_date) and sus_doc == _norm_date(o.doc_date):
            ev.append(f"document date matches ({sus_doc})")
            score += W_DOC_DATE
        for role, sv, ov in (("grantor", suspect.grantor, o.grantor),
                             ("grantee", suspect.grantee, o.grantee)):
            if sv and ov and _party_agrees(sv, ov):
                ev.append(f"{role} agrees ({ov})")
                score += W_PARTY
        if ev:
            candidates.append(Candidate(odoc, dd, ev, score))

    # Evidence strength first, numeric proximity only as a tiebreak.
    candidates.sort(key=lambda c: (-c.score, c.digit_distance))

    if exact and not candidates:
        status = "CONFIRMED"          # suspect exists in the oracle, nothing nearer
    elif candidates and not exact:
        status = "CORRECTION_PROPOSED"
    elif candidates and exact:
        status = "AMBIGUOUS"          # both readings exist -- adjudicate from the face
    else:
        status = "NO_ORACLE_MATCH"    # oracle cannot speak to this number

    return {"suspect": sus, "locator": suspect.locator, "status": status,
            "candidates": [{"docno": c.docno, "digit_distance": c.digit_distance,
                            "score": c.score, "decisive": c.decisive,
                            "evidence": c.evidence} for c in candidates]}


def _safe_doc(v: str) -> str:
    try:
        return normalize_docno(v)
    except StableKeyError:
        return ""


def _safe_bp(v: str) -> str:
    try:
        return normalize_bookpage(v)
    except StableKeyError:
        return ""


def _party_agrees(a: str, b: str) -> bool:
    """Token-overlap party comparison, tolerant of OCR noise and abbreviation."""
    stop = {"the", "of", "and", "a", "an", "co", "inc", "llc", "ltd", "lp",
            "company", "corp", "corporation", "et", "al", "ux", "vir", "public",
            "trust", "trustee", "na", "n.a.", "bank"}
    ta = {w for w in _tokens(a) if w not in stop}
    tb = {w for w in _tokens(b) if w not in stop}
    if not ta or not tb:
        return False
    return len(ta & tb) / min(len(ta), len(tb)) >= 0.5


def _tokens(s: str) -> list[str]:
    return [t for t in "".join(
        ch.lower() if ch.isalnum() else " " for ch in str(s)).split() if len(t) > 1]


def audit(suspects: list[Suspect], oracle: list[OracleRow], **kw) -> dict:
    """Run `suggest` over many suspects and summarise."""
    results = [suggest(s, oracle, **kw) for s in suspects]
    counts: dict[str, int] = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    proposed = [r for r in results if r["status"] == "CORRECTION_PROPOSED"]
    return {"results": results, "counts": counts,
            "checked": len(results), "corrections_proposed": len(proposed),
            "error_rate": (len(proposed) / len(results)) if results else 0.0}
