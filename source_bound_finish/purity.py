"""Client-cell purity. Process text never belongs on a client face."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from .constants import (
    ALLOWED_COMMENT_EXACT,
    FORBIDDEN_COMMENT_VALUES,
    GENERIC_PARTY_TOKENS,
    PROCESS_COMMENTARY_MARKERS,
)

_PAGE_RANGE = re.compile(r"^\s*\d+\s*[-–—to]+\s*\d+\s*$", re.I)
_HASH_CLIP = re.compile(r"^#+$")


@dataclass(frozen=True)
class PurityFinding:
    field: str
    code: str
    message: str
    row: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _lower(value: object) -> str:
    return _text(value).lower()


def check_comment(value: object, *, row: int | None = None) -> list[PurityFinding]:
    text = _text(value)
    lowered = text.lower()
    findings: list[PurityFinding] = []
    if lowered not in ALLOWED_COMMENT_EXACT:
        findings.append(
            PurityFinding(
                "Comments",
                "FORBIDDEN_COMMENT",
                "Comments must be blank or exact lowercase 'missing image'",
                row,
            )
        )
    if lowered in FORBIDDEN_COMMENT_VALUES:
        findings.append(
            PurityFinding("Comments", "PROCESS_TOKEN", f"forbidden token {text!r}", row)
        )
    return findings


def check_parties(value: object, *, row: int | None = None) -> list[PurityFinding]:
    lowered = _lower(value)
    findings: list[PurityFinding] = []
    for token in GENERIC_PARTY_TOKENS:
        if re.search(rf"\b{re.escape(token)}\b", lowered):
            findings.append(
                PurityFinding(
                    "Parties",
                    "GENERIC_PARTY",
                    f"generic party token {token!r} is not a recovered name",
                    row,
                )
            )
    if re.search(r"\bet al\.?\b", lowered):
        findings.append(
            PurityFinding("Parties", "GENERIC_PARTY", "et al is not a recovered name", row)
        )
    return findings


def check_page(value: object, *, row: int | None = None) -> list[PurityFinding]:
    text = _text(value)
    findings: list[PurityFinding] = []
    if not text:
        return findings
    if _PAGE_RANGE.match(text):
        findings.append(
            PurityFinding(
                "Page",
                "PAGE_RANGE",
                "Page must be one physical start, not a range",
                row,
            )
        )
    if _HASH_CLIP.match(text):
        findings.append(PurityFinding("Page", "CLIPPED", "clipped #### value", row))
    return findings


def check_legal(value: object, *, row: int | None = None) -> list[PurityFinding]:
    lowered = _lower(value)
    findings: list[PurityFinding] = []
    for marker in PROCESS_COMMENTARY_MARKERS:
        if marker in lowered:
            findings.append(
                PurityFinding(
                    "Legal Description",
                    "PROCESS_COMMENTARY",
                    f"process marker {marker!r} in Legal",
                    row,
                )
            )
    return findings


def check_purity(rows: list[dict], *, comments_field: str = "Comments") -> list[PurityFinding]:
    findings: list[PurityFinding] = []
    for index, row in enumerate(rows, start=1):
        findings.extend(check_comment(row.get(comments_field), row=index))
        if "Grantor" in row:
            findings.extend(check_parties(row.get("Grantor"), row=index))
        if "Grantee" in row:
            findings.extend(check_parties(row.get("Grantee"), row=index))
        if "Grantor" not in row and "Grantee" not in row and row.get("Parties") is not None:
            findings.extend(check_parties(row.get("Parties"), row=index))
        findings.extend(check_page(row.get("Page"), row=index))
        findings.extend(check_legal(row.get("Legal Description"), row=index))
        for field in ("Date of Doc", "Rec Date", "Filed Date", "Approval Date"):
            value = _text(row.get(field))
            if _lower(value) in FORBIDDEN_COMMENT_VALUES:
                findings.append(
                    PurityFinding(field, "PLACEHOLDER_DATE", "placeholder is not a date", index)
                )
    return findings
