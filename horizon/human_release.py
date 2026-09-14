"""Fail-closed human release token and package-completion predicate.

``packages_complete`` is true only when every required finish gate ran and
passed and a writer-held owner-review token matches the isolated workbook
hash. The token cannot claim external delivery or READY_TO_SUBMIT.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

from .isolated_delta import sha256_file

PACKET_SCHEMA_ID = "dbx.human_release_token"
PACKET_SCHEMA_VERSION = "1.0"
RECEIPT_SCHEMA_ID = "dbx.human_release_receipt"
RECEIPT_SCHEMA_VERSION = "1.0"
REQUIRED_KEYS = {
    "schema_id",
    "schema_version",
    "packet_id",
    "sections",
    "operator",
    "workbook_sha256",
    "statement",
    "external_release",
}
OWNER_REVIEW_STATEMENT = (
    "I release this isolated copy for owner review only. "
    "It is not an external client delivery."
)
FORBIDDEN_PHRASES = (
    "READY_TO_SUBMIT",
    "EXTERNAL_RELEASE",
    "FINAL_TURNIN",
    "100%",
)
REQUIRED_COMPLETION_GATES = (
    "source_acquisition",
    "reextraction",
    "occurrence_ledger",
    "workbook_qa",
    "native_print",
    "drive_readback",
    "human_release",
)
# Index fields may be proved either by standalone reconciliation or by a
# repair loop that ended with no blanks or conflicts.
INDEX_GATES = ("index_reconciliation", "repair_loop")


class HumanReleaseError(ValueError):
    """Raised when a human-release token is unsafe."""


@dataclass
class HumanReleaseReceipt:
    generated_utc: str
    packet_id: str
    sections: List[int]
    operator: str
    workbook_sha256: str
    issues: List[str]
    technical_pass: bool
    schema_id: str = RECEIPT_SCHEMA_ID
    schema_version: str = RECEIPT_SCHEMA_VERSION
    notes: List[str] = field(
        default_factory=lambda: [
            "Owner-review release is not external client delivery",
            "technical_pass is not package completion by itself",
        ]
    )

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def _require_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\n" in value:
        raise HumanReleaseError(f"{label} must be a single-line string")
    return value.strip()


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def assess_human_release(
    payload: Dict[str, object],
    *,
    workbook: Optional[Path] = None,
    requested_sections: Sequence[int] = (),
) -> HumanReleaseReceipt:
    if set(payload) != REQUIRED_KEYS:
        raise HumanReleaseError("Human release token has invalid top-level fields")
    if (
        payload["schema_id"] != PACKET_SCHEMA_ID
        or payload["schema_version"] != PACKET_SCHEMA_VERSION
    ):
        raise HumanReleaseError("Human release token schema is invalid")
    packet_id = _require_text(payload["packet_id"], "packet_id")
    operator = _require_text(payload["operator"], "operator")
    statement = _require_text(payload["statement"], "statement")
    digest = payload["workbook_sha256"]
    if isinstance(digest, str):
        digest = digest.casefold()
    if not _is_sha256(digest):
        raise HumanReleaseError("workbook_sha256 is invalid")
    raw_sections = payload["sections"]
    if not isinstance(raw_sections, list) or not raw_sections:
        raise HumanReleaseError("sections must be a non-empty list")
    sections: List[int] = []
    for item in raw_sections:
        if type(item) is not int or item not in (15, 13, 11):
            raise HumanReleaseError("sections must be 15, 13, and/or 11")
        if item not in sections:
            sections.append(item)
    issues: List[str] = []
    if payload["external_release"] is not False:
        issues.append("external_release must be false")
    if statement != OWNER_REVIEW_STATEMENT:
        issues.append("statement must be the owner-review declaration")
    upper = statement.upper()
    if any(phrase in upper for phrase in FORBIDDEN_PHRASES):
        issues.append("statement contains a forbidden promotion phrase")
    if requested_sections and set(sections) != set(requested_sections):
        issues.append(
            f"token sections {sections} do not match requested {list(requested_sections)}"
        )
    if workbook is not None:
        actual = sha256_file(workbook)
        if actual != digest:
            issues.append("token workbook hash does not match the isolated workbook")
    return HumanReleaseReceipt(
        generated_utc=datetime.now(timezone.utc).isoformat(),
        packet_id=packet_id,
        sections=sections,
        operator=operator,
        workbook_sha256=digest,
        issues=issues,
        technical_pass=not issues,
    )


def _gate_map(gates: Iterable[object]) -> Dict[str, object]:
    return {gate.name: gate for gate in gates if getattr(gate, "ran", False)}


def _index_fields_complete(gates: Dict[str, object]) -> bool:
    recon = gates.get("index_reconciliation")
    if recon is not None and recon.technical_pass:
        blanks = recon.detail.get("blank_required_count")
        conflicts = recon.detail.get("conflict_count")
        if blanks == 0 and conflicts == 0:
            return True
    repair = gates.get("repair_loop")
    if repair is not None and repair.technical_pass:
        if (
            repair.detail.get("remaining_blanks") == 0
            and repair.detail.get("remaining_conflicts") == 0
        ):
            return True
    return False


def evaluate_package_completion(
    gates: Sequence[object],
    *,
    requested_sections: Sequence[int],
) -> tuple[bool, List[str]]:
    by_name = _gate_map(gates)
    missing: List[str] = []
    for name in REQUIRED_COMPLETION_GATES:
        gate = by_name.get(name)
        if gate is None or not gate.technical_pass:
            missing.append(f"required gate {name} did not pass")
    if not _index_fields_complete(by_name):
        missing.append(
            "index fields are not complete (reconciliation or repair loop)"
        )
    for gate in by_name.values():
        if gate.technical_pass is False:
            label = f"blocking gate {gate.name}"
            if label not in missing:
                missing.append(label)
    if not requested_sections:
        missing.append("no sections were requested")
    complete = not missing
    return complete, missing
