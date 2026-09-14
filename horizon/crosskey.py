"""Propose document-number corrections only with independent corroboration.

Proximity to a neighbouring number is never enough. Book/page is a unique
locator and is decisive by itself; recorded date, document date, and parties
only corroborate. This module never rewrites a ledger.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .stable_key import StableKeyError, normalize_bookpage, normalize_docno

WEIGHT_BOOKPAGE = 100
WEIGHT_REC_DATE = 10
WEIGHT_DOC_DATE = 8
WEIGHT_PARTY = 3
_STOP = {
    "the",
    "of",
    "and",
    "a",
    "an",
    "co",
    "inc",
    "llc",
    "ltd",
    "lp",
    "company",
    "corp",
    "corporation",
    "et",
    "al",
    "ux",
    "vir",
    "public",
    "trust",
    "trustee",
    "na",
    "n.a.",
    "bank",
}


@dataclass(frozen=True)
class OracleRow:
    docno: str
    bookpage: str = ""
    rec_date: str = ""
    doc_date: str = ""
    doc_type: str = ""
    grantor: str = ""
    grantee: str = ""


@dataclass(frozen=True)
class Suspect:
    docno: str
    locator: str = ""
    bookpage: str = ""
    rec_date: str = ""
    doc_date: str = ""
    grantor: str = ""
    grantee: str = ""


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
        return self.score >= WEIGHT_BOOKPAGE


def digit_distance(left: str, right: str) -> int:
    left_text, right_text = str(left).strip(), str(right).strip()
    if len(left_text) != len(right_text):
        return -1
    return sum(
        1 for first, second in zip(left_text, right_text) if first != second
    )


def normalize_date(value: str) -> str:
    text = str(value or "").strip().replace("-", "/")
    parts = [part for part in text.split("/") if part]
    if len(parts) != 3:
        return ""
    first, second, third = parts
    if len(first) == 4:
        year, month, day = first, second, third
    else:
        month, day, year = first, second, third
        if len(year) == 2:
            year = ("19" + year) if int(year) > 50 else ("20" + year)
    try:
        return f"{int(month):02d}/{int(day):02d}/{int(year):04d}"
    except ValueError:
        return ""


def _safe_doc(value: str) -> str:
    try:
        return normalize_docno(value)
    except StableKeyError:
        return ""


def _safe_bookpage(value: str) -> str:
    try:
        return normalize_bookpage(value)
    except StableKeyError:
        return ""


def _tokens(value: str) -> list[str]:
    cleaned = "".join(
        character.lower() if character.isalnum() else " " for character in str(value)
    )
    return [token for token in cleaned.split() if len(token) > 1]


def parties_agree(left: str, right: str) -> bool:
    left_tokens = {token for token in _tokens(left) if token not in _STOP}
    right_tokens = {token for token in _tokens(right) if token not in _STOP}
    if not left_tokens or not right_tokens:
        return False
    return len(left_tokens & right_tokens) / min(
        len(left_tokens),
        len(right_tokens),
    ) >= 0.5


def suggest(
    suspect: Suspect,
    oracle: list[OracleRow],
    *,
    max_digit_distance: int = 2,
) -> dict:
    try:
        suspect_doc = normalize_docno(suspect.docno)
    except StableKeyError:
        return {
            "suspect": suspect.docno,
            "locator": suspect.locator,
            "status": "UNPARSEABLE",
            "candidates": [],
        }

    suspect_bookpage = _safe_bookpage(suspect.bookpage)
    suspect_rec = normalize_date(suspect.rec_date)
    suspect_doc_date = normalize_date(suspect.doc_date)
    exact = [row for row in oracle if _safe_doc(row.docno) == suspect_doc]
    candidates: list[Candidate] = []

    for row in oracle:
        oracle_doc = _safe_doc(row.docno)
        if not oracle_doc or oracle_doc == suspect_doc:
            continue
        distance = digit_distance(suspect_doc, oracle_doc)
        if distance < 0 or distance > max_digit_distance:
            continue
        evidence: list[str] = []
        score = 0
        oracle_bookpage = _safe_bookpage(row.bookpage)
        if (
            suspect_bookpage
            and oracle_bookpage
            and suspect_bookpage == oracle_bookpage
        ):
            evidence.append(f"book/page matches exactly ({oracle_bookpage})")
            score += WEIGHT_BOOKPAGE
        if (
            suspect_rec
            and normalize_date(row.rec_date)
            and suspect_rec == normalize_date(row.rec_date)
        ):
            evidence.append(f"recorded date matches ({suspect_rec})")
            score += WEIGHT_REC_DATE
        if (
            suspect_doc_date
            and normalize_date(row.doc_date)
            and suspect_doc_date == normalize_date(row.doc_date)
        ):
            evidence.append(f"document date matches ({suspect_doc_date})")
            score += WEIGHT_DOC_DATE
        for role, suspect_value, oracle_value in (
            ("grantor", suspect.grantor, row.grantor),
            ("grantee", suspect.grantee, row.grantee),
        ):
            if (
                suspect_value
                and oracle_value
                and parties_agree(suspect_value, oracle_value)
            ):
                evidence.append(f"{role} agrees ({oracle_value})")
                score += WEIGHT_PARTY
        if evidence:
            candidates.append(
                Candidate(oracle_doc, distance, evidence, score)
            )

    candidates.sort(key=lambda item: (-item.score, item.digit_distance))
    if exact and not candidates:
        status = "CONFIRMED"
    elif candidates and not exact:
        status = "CORRECTION_PROPOSED"
    elif candidates and exact:
        status = "AMBIGUOUS"
    else:
        status = "NO_ORACLE_MATCH"
    return {
        "suspect": suspect_doc,
        "locator": suspect.locator,
        "status": status,
        "candidates": [
            {
                "docno": item.docno,
                "digit_distance": item.digit_distance,
                "score": item.score,
                "decisive": item.decisive,
                "evidence": item.evidence,
            }
            for item in candidates
        ],
    }


def audit(
    suspects: list[Suspect],
    oracle: list[OracleRow],
    **kwargs,
) -> dict:
    results = [suggest(suspect, oracle, **kwargs) for suspect in suspects]
    counts: dict[str, int] = {}
    for result in results:
        counts[result["status"]] = counts.get(result["status"], 0) + 1
    proposed = [
        result for result in results if result["status"] == "CORRECTION_PROPOSED"
    ]
    return {
        "results": results,
        "counts": counts,
        "checked": len(results),
        "corrections_proposed": len(proposed),
        "error_rate": (len(proposed) / len(results)) if results else 0.0,
    }
