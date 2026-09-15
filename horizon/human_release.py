"""Fail-closed human release token and package-completion predicate.

``packages_complete`` is true only when every required finish gate ran and
passed, Drive readback is an Isolated/ copy, index/QA/print gates hash
the current isolated workbook, and a writer-held owner-review token
matches that hash. After execute, finish receipts stay incomplete while
the examiner queue has blanks or conflicts, and while ``pdf_census``
still names image-only empty-text faces. The token cannot claim
external delivery or READY_TO_SUBMIT.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

from .examiner import require_named_examiner, write_new_json
from .isolated_delta import sha256_file
from .source_acquisition import PRIORITY_SECTIONS

PACKET_SCHEMA_ID = "dbx.human_release_token"
PACKET_SCHEMA_VERSION = "1.0"
DRAFT_SCHEMA_ID = "dbx.human_release_draft"
DRAFT_SCHEMA_VERSION = "1.0"
DRAFT_STATUS = "UNAPPROVED_DRAFT"
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


def write_human_release_token(
    *,
    workbook: Path,
    output: Path,
    operator: str,
    sections: Sequence[int],
    packet_id: str,
) -> Dict[str, object]:
    """Write an owner-review token bound to the isolated workbook hash."""
    try:
        named = require_named_examiner(operator)
    except ValueError as exc:
        raise HumanReleaseError(str(exc)) from exc
    if not sections or any(section not in PRIORITY_SECTIONS for section in sections):
        raise HumanReleaseError(f"sections must come from {PRIORITY_SECTIONS}")
    if len(sections) != len(set(sections)):
        raise HumanReleaseError("sections must be unique")
    resolved = workbook.expanduser()
    if not resolved.is_file():
        raise HumanReleaseError(f"workbook does not exist: {resolved}")
    token_id = packet_id.strip()
    if not token_id or "\n" in token_id:
        raise HumanReleaseError("packet_id must be a single-line string")
    token = {
        "schema_id": PACKET_SCHEMA_ID,
        "schema_version": PACKET_SCHEMA_VERSION,
        "packet_id": token_id,
        "sections": list(sections),
        "operator": named,
        "workbook_sha256": sha256_file(resolved),
        "statement": OWNER_REVIEW_STATEMENT,
        "external_release": False,
    }
    try:
        write_new_json(token, output, "human release token")
    except ValueError as exc:
        raise HumanReleaseError(str(exc)) from exc
    assessed = assess_human_release(
        token, workbook=resolved, requested_sections=sections
    )
    if not assessed.technical_pass:
        raise HumanReleaseError("; ".join(assessed.issues) or "human release token failed")
    return token


def write_human_release_draft(
    *,
    workbook: Path,
    output: Path,
    sections: Sequence[int],
    packet_id: str,
) -> Dict[str, object]:
    """Hash-bind a draft. Does not name an examiner or release a package."""
    if not sections or any(section not in PRIORITY_SECTIONS for section in sections):
        raise HumanReleaseError(f"sections must come from {PRIORITY_SECTIONS}")
    if len(sections) != len(set(sections)):
        raise HumanReleaseError("sections must be unique")
    resolved = workbook.expanduser().resolve()
    if not resolved.is_file():
        raise HumanReleaseError(f"workbook does not exist: {resolved}")
    token_id = packet_id.strip()
    if not token_id or "\n" in token_id:
        raise HumanReleaseError("packet_id must be a single-line string")
    draft = {
        "schema_id": DRAFT_SCHEMA_ID,
        "schema_version": DRAFT_SCHEMA_VERSION,
        "status": DRAFT_STATUS,
        "packet_id": token_id,
        "sections": list(sections),
        "operator": "",
        "workbook_sha256": sha256_file(resolved),
        "statement": OWNER_REVIEW_STATEMENT,
        "external_release": False,
        "notes": [
            "UNAPPROVED_DRAFT cannot bind human_release",
            "Attest with a named examiner against the current isolated workbook",
        ],
    }
    output = output.expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(draft, indent=2, sort_keys=True), encoding="utf-8")
    return draft


def attest_human_release_draft(
    draft: Dict[str, object],
    *,
    workbook: Path,
    output: Path,
    operator: str,
) -> Dict[str, object]:
    """Promote a draft after owner review. Horizon does not invent the examiner."""
    if (
        draft.get("schema_id") != DRAFT_SCHEMA_ID
        or draft.get("schema_version") != DRAFT_SCHEMA_VERSION
        or draft.get("status") != DRAFT_STATUS
    ):
        raise HumanReleaseError("human release draft schema is invalid")
    resolved = workbook.expanduser().resolve()
    if not resolved.is_file():
        raise HumanReleaseError(f"workbook does not exist: {resolved}")
    actual = sha256_file(resolved)
    expected = str(draft.get("workbook_sha256") or "").casefold()
    if actual != expected:
        raise HumanReleaseError(
            "Workbook hash does not match the owner-review draft; reissue "
            "against the current isolated workbook"
        )
    raw_sections = draft.get("sections")
    if not isinstance(raw_sections, list):
        raise HumanReleaseError("sections must be a non-empty list")
    return write_human_release_token(
        workbook=resolved,
        output=output,
        operator=operator,
        sections=raw_sections,
        packet_id=str(draft.get("packet_id") or ""),
    )


def _load_json(path: Path) -> Dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HumanReleaseError(f"Cannot read {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise HumanReleaseError(f"{path} must contain a JSON object")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Write an owner-review token. Not external client delivery."
    )
    parser.add_argument("--draft", action="store_true")
    parser.add_argument("--attest", action="store_true")
    parser.add_argument("--from-draft", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workbook", type=Path)
    parser.add_argument("--operator")
    parser.add_argument(
        "--section",
        dest="sections",
        type=int,
        action="append",
        choices=PRIORITY_SECTIONS,
    )
    parser.add_argument("--packet-id")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        if args.draft:
            if args.workbook is None or args.packet_id is None or not args.sections:
                raise HumanReleaseError(
                    "--draft requires --workbook, --packet-id, and --section"
                )
            draft = write_human_release_draft(
                workbook=args.workbook,
                output=args.output,
                sections=args.sections,
                packet_id=args.packet_id,
            )
            print(
                json.dumps(
                    {
                        "output": str(args.output),
                        "status": draft["status"],
                        "workbook_sha256": draft["workbook_sha256"],
                        "packages_complete": False,
                    },
                    indent=2,
                )
            )
            return 0
        if args.attest:
            if args.from_draft is None or args.workbook is None or args.operator is None:
                raise HumanReleaseError(
                    "--attest requires --from-draft, --workbook, and --operator"
                )
            token = attest_human_release_draft(
                _load_json(args.from_draft),
                workbook=args.workbook,
                output=args.output,
                operator=args.operator,
            )
        else:
            if args.workbook is None or args.operator is None or args.packet_id is None:
                raise HumanReleaseError(
                    "Pass --workbook, --operator, --section, and --packet-id, "
                    "or --draft / --attest"
                )
            if not args.sections:
                raise HumanReleaseError("--section is required")
            token = write_human_release_token(
                workbook=args.workbook,
                output=args.output,
                operator=args.operator,
                sections=args.sections,
                packet_id=args.packet_id,
            )
    except (OSError, HumanReleaseError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "output": str(args.output),
                "workbook_sha256": token["workbook_sha256"],
                "sections": token["sections"],
                "external_release": False,
                "packages_complete": False,
            },
            indent=2,
        )
    )
    return 0


def _gate_map(gates: Iterable[object]) -> Dict[str, object]:
    return {gate.name: gate for gate in gates if getattr(gate, "ran", False)}


def _normalize_workbook_sha256(value: object) -> str:
    digest = value.casefold() if isinstance(value, str) else ""
    if len(digest) == 64 and all(character in "0123456789abcdef" for character in digest):
        return digest
    return ""


def _gate_workbook_sha256(gate: object) -> str:
    detail = getattr(gate, "detail", {}) or {}
    if not isinstance(detail, dict):
        return ""
    for key in (
        "workbook_sha256",
        "final_workbook_sha256",
        "source_workbook_sha256",
        "readback_sha256",
    ):
        digest = _normalize_workbook_sha256(detail.get(key))
        if digest:
            return digest
    return ""


def _index_fields_complete(
    gates: Dict[str, object],
    *,
    workbook_sha256: str = "",
) -> bool:
    expected = _normalize_workbook_sha256(workbook_sha256)
    recon = gates.get("index_reconciliation")
    if recon is not None and recon.technical_pass:
        blanks = recon.detail.get("blank_required_count")
        conflicts = recon.detail.get("conflict_count")
        if blanks == 0 and conflicts == 0:
            source = recon.detail.get("candidate_from")
            if source == "workbook":
                if not expected or _gate_workbook_sha256(recon) == expected:
                    return True
    repair = gates.get("repair_loop")
    if repair is not None and repair.technical_pass:
        if (
            repair.detail.get("remaining_blanks") == 0
            and repair.detail.get("remaining_conflicts") == 0
        ):
            if not expected or _gate_workbook_sha256(repair) == expected:
                return True
    return False


def evaluate_package_completion(
    gates: Sequence[object],
    *,
    requested_sections: Sequence[int],
    workbook_sha256: Optional[str] = None,
) -> tuple[bool, List[str]]:
    by_name = _gate_map(gates)
    expected = _normalize_workbook_sha256(workbook_sha256)
    missing: List[str] = []
    if not expected:
        missing.append("isolated workbook hash is required")
    for name in REQUIRED_COMPLETION_GATES:
        gate = by_name.get(name)
        if gate is None or not gate.technical_pass:
            missing.append(f"required gate {name} did not pass")
            continue
        if name == "drive_readback":
            detail = getattr(gate, "detail", {}) or {}
            if (
                not isinstance(detail, dict)
                or detail.get("isolated_copy") is not True
            ):
                missing.append(
                    "required gate drive_readback Isolated/ copy is not bound"
                )
    bound: Dict[str, str] = {}
    for name in ("native_print", "drive_readback", "human_release"):
        gate = by_name.get(name)
        if gate is None or not gate.technical_pass:
            continue
        digest = _gate_workbook_sha256(gate)
        if not digest:
            missing.append(f"required gate {name} workbook hash is missing")
            continue
        bound[name] = digest
        if expected and digest != expected:
            missing.append(
                f"required gate {name} workbook hash does not match isolated file"
            )
    if bound and len(set(bound.values())) > 1:
        missing.append(
            "Print Preview, Isolated/, and owner-review hashes do not match"
        )
    qa = by_name.get("workbook_qa")
    if qa is not None and qa.technical_pass and expected:
        digest = _gate_workbook_sha256(qa)
        if not digest:
            missing.append("required gate workbook_qa workbook hash is missing")
        elif digest != expected:
            missing.append(
                "required gate workbook_qa workbook hash does not match isolated file"
            )
    if not _index_fields_complete(by_name, workbook_sha256=expected):
        missing.append(
            "index fields are not complete (reconciliation or repair loop)"
        )
    census = by_name.get("pdf_census")
    if census is not None and getattr(census, "ran", False):
        detail = getattr(census, "detail", {}) or {}
        empty = detail.get("empty_text_files") if isinstance(detail, dict) else None
        if isinstance(empty, int) and empty > 0:
            missing.append(
                f"{empty} image-only PDF(s) still have empty extracted text"
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


if __name__ == "__main__":
    raise SystemExit(main())
