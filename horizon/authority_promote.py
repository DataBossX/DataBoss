"""Promote an unapproved Phase 1 draft after a named examiner attests.

This writes ``dbx.source_authority_manifest`` and hash-binds
``authority_hashes.source_authority`` in a project manifest. It does not
invent examiner names, legal facts, or package release. Live roots are
re-hashed so stale draft bytes cannot be authorized.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .authority_draft import DRAFT_SCHEMA_ID, UNAPPROVED_STATUS
from .examiner import (
    require_assigned_id,
    require_named_examiner,
    write_new_json,
)
from .source_acquisition import (
    DEFAULT_REQUIRED_ROLES,
    PRIORITY_SECTIONS,
    SOURCE_ROLES,
    SourceAcquisitionError,
    build_receipt,
    parse_root,
    sha256_file,
)

MANIFEST_SCHEMA_ID = "dbx.source_authority_manifest"
MANIFEST_SCHEMA_VERSION = "1.0"
PROJECT_SCHEMA_ID = "dbx.project_manifest"
PROJECT_SCHEMA_VERSION = "1.1"
_ASSERTION_FIELDS = {
    "root_label",
    "relative_path",
    "section",
    "role",
    "expected_sha256",
}


class AuthorityPromoteError(ValueError):
    """Raised when a draft cannot be promoted safely."""


def _require_id(value: str, field_name: str) -> str:
    try:
        return require_assigned_id(value, field_name)
    except ValueError as exc:
        raise AuthorityPromoteError(str(exc)) from exc


def _require_approved_by(value: str, project_id: str, decision_id: str) -> str:
    try:
        stripped = require_named_examiner(value)
    except ValueError as exc:
        raise AuthorityPromoteError(
            "approved_by must be a named examiner, not a placeholder"
        ) from exc
    if stripped.casefold() in {project_id.casefold(), decision_id.casefold()}:
        raise AuthorityPromoteError(
            "approved_by must be a named examiner, not a placeholder"
        )
    return stripped


def _load_json(path: Path) -> Dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AuthorityPromoteError(f"Cannot read {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise AuthorityPromoteError(f"{path} must contain a JSON object")
    return payload


def load_draft(path: Path) -> Dict[str, object]:
    payload = _load_json(path)
    if (
        payload.get("schema_id") != DRAFT_SCHEMA_ID
        or payload.get("status") != UNAPPROVED_STATUS
    ):
        raise AuthorityPromoteError("expected dbx.source_authority_draft UNAPPROVED_DRAFT")
    if str(payload.get("approved_by") or "").strip():
        raise AuthorityPromoteError("draft approved_by must stay empty until promotion")
    authorities = payload.get("authorities")
    if not isinstance(authorities, list):
        raise AuthorityPromoteError("draft authorities must be a list")
    return payload


def _normalize_assertion(raw: object, index: int) -> Dict[str, object]:
    if not isinstance(raw, dict) or set(raw) != _ASSERTION_FIELDS:
        raise AuthorityPromoteError(f"draft authority {index} has invalid fields")
    section = raw["section"]
    role = raw["role"]
    digest = raw["expected_sha256"]
    if (
        type(section) is not int
        or section not in PRIORITY_SECTIONS
        or not isinstance(role, str)
        or role not in SOURCE_ROLES
        or not isinstance(digest, str)
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
        or not isinstance(raw["root_label"], str)
        or not raw["root_label"]
        or not isinstance(raw["relative_path"], str)
        or not raw["relative_path"]
    ):
        raise AuthorityPromoteError(f"draft authority {index} is invalid")
    return {
        "root_label": raw["root_label"],
        "relative_path": raw["relative_path"],
        "section": section,
        "role": role,
        "expected_sha256": digest,
    }


def _select_authorities(
    draft: Dict[str, object],
    *,
    confirm_sections: Sequence[int],
    required_roles: Sequence[str],
) -> List[Dict[str, object]]:
    if not confirm_sections or any(
        section not in PRIORITY_SECTIONS for section in confirm_sections
    ):
        raise AuthorityPromoteError(
            f"confirm-section values must come from {PRIORITY_SECTIONS}"
        )
    if len(confirm_sections) != len(set(confirm_sections)):
        raise AuthorityPromoteError("confirm-section values must be unique")
    selected: List[Dict[str, object]] = []
    for index, raw in enumerate(draft.get("authorities") or []):
        assertion = _normalize_assertion(raw, index)
        if assertion["section"] in confirm_sections:
            selected.append(assertion)
    for section in confirm_sections:
        present = {item["role"] for item in selected if item["section"] == section}
        missing = [role for role in required_roles if role not in present]
        if missing:
            raise AuthorityPromoteError(
                f"section {section} is missing classified required roles: "
                + ", ".join(missing)
            )
    if not selected:
        raise AuthorityPromoteError("no confirmed authorities to promote")
    return selected


def _verify_live_hashes(
    authorities: Sequence[Dict[str, object]],
    roots: Sequence[str],
    confirm_sections: Sequence[int],
) -> None:
    if not roots:
        raise AuthorityPromoteError("Pass --root so live bytes can be re-hashed")
    try:
        receipt = build_receipt(
            [parse_root(raw) for raw in roots],
            requested_sections=list(confirm_sections),
        )
    except (OSError, SourceAcquisitionError) as exc:
        raise AuthorityPromoteError(str(exc)) from exc
    live = {
        (item.root_label, item.relative_path): item.sha256 for item in receipt.files
    }
    for assertion in authorities:
        key = (assertion["root_label"], assertion["relative_path"])
        digest = live.get(key)
        if digest is None:
            raise AuthorityPromoteError(
                f"{key[0]}:{key[1]} is not present on the live roots"
            )
        if digest != assertion["expected_sha256"]:
            raise AuthorityPromoteError(
                f"{key[0]}:{key[1]} hash no longer matches the draft"
            )


def build_manifest(
    *,
    project_id: str,
    decision_id: str,
    approved_by: str,
    authorities: Sequence[Dict[str, object]],
) -> Dict[str, object]:
    return {
        "schema_id": MANIFEST_SCHEMA_ID,
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "project_id": project_id,
        "decision_id": decision_id,
        "approved_by": approved_by,
        "authorities": list(authorities),
    }


def build_project_manifest(project_id: str, source_authority_sha256: str) -> Dict[str, object]:
    return {
        "schema_id": PROJECT_SCHEMA_ID,
        "schema_version": PROJECT_SCHEMA_VERSION,
        "project_id": project_id,
        "source_policy": "IMMUTABLE_READ_ONLY",
        "authority_hashes": {"source_authority": source_authority_sha256},
        "candidate_deliverables": [
            {
                "path": "candidate.xlsx",
                "reported_sha256": "0" * 64,
                "status": "CANDIDATE",
            }
        ],
        "required_checks": ["source_acquisition"],
        "release_policy": {
            "technical_verification_is_not_release": True,
            "approved_hash_required": True,
            "human_gate": "G7",
        },
    }


def _write_new_json(payload: Dict[str, object], path: Path, label: str) -> Path:
    try:
        return write_new_json(payload, path, label)
    except ValueError as exc:
        raise AuthorityPromoteError(str(exc)) from exc


def promote(
    *,
    draft_path: Path,
    output: Path,
    project_manifest_output: Path,
    project_id: str,
    decision_id: str,
    approved_by: str,
    confirm_sections: Sequence[int],
    roots: Sequence[str],
    required_roles: Sequence[str] = DEFAULT_REQUIRED_ROLES,
) -> Dict[str, object]:
    project_id = _require_id(project_id, "project_id")
    decision_id = _require_id(decision_id, "decision_id")
    approved_by = _require_approved_by(approved_by, project_id, decision_id)
    draft = load_draft(draft_path)
    authorities = _select_authorities(
        draft,
        confirm_sections=confirm_sections,
        required_roles=required_roles,
    )
    _verify_live_hashes(authorities, roots, confirm_sections)
    manifest = build_manifest(
        project_id=project_id,
        decision_id=decision_id,
        approved_by=approved_by,
        authorities=authorities,
    )
    authority_path = _write_new_json(manifest, output, "authority manifest")
    project = build_project_manifest(project_id, sha256_file(authority_path))
    project_path = _write_new_json(
        project, project_manifest_output, "project manifest"
    )
    return {
        "schema_id": "dbx.authority_promote_receipt",
        "schema_version": "1.0",
        "packages_complete": False,
        "technical_pass": True,
        "authority_manifest": str(authority_path),
        "project_manifest": str(project_path),
        "source_authority_sha256": project["authority_hashes"]["source_authority"],
        "confirmed_sections": list(confirm_sections),
        "authority_count": len(authorities),
        "approved_by": approved_by,
        "notes": [
            "This promotion is not package release",
            "Rerun the PC operator with the same receipt-dir to bind Phase 2",
        ],
    }


def build_promote_command(
    *,
    draft_path: str,
    output: str,
    project_manifest_output: str,
    confirm_sections: Sequence[int],
    roots: Sequence[str],
) -> str:
    import shlex

    parts: List[object] = [
        "python3",
        "-m",
        "horizon.authority_promote",
        "--draft",
        draft_path,
        "--output",
        output,
        "--project-manifest-output",
        project_manifest_output,
        "--project-id",
        "EXAMINER_PROJECT_ID",
        "--decision-id",
        "EXAMINER_DECISION_ID",
        "--approved-by",
        "EXAMINER_NAME",
    ]
    for section in confirm_sections:
        parts.extend(["--confirm-section", section])
    for root in roots:
        parts.extend(["--root", root])
    return " ".join(shlex.quote(str(part)) for part in parts)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Promote an UNAPPROVED_DRAFT after a named examiner attests. "
            "Does not finish a package."
        )
    )
    parser.add_argument("--draft", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--project-manifest-output", type=Path, required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--decision-id", required=True)
    parser.add_argument("--approved-by", required=True)
    parser.add_argument(
        "--confirm-section",
        dest="confirm_sections",
        type=int,
        action="append",
        choices=PRIORITY_SECTIONS,
        required=True,
    )
    parser.add_argument("--root", action="append", default=[])
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        receipt = promote(
            draft_path=args.draft,
            output=args.output,
            project_manifest_output=args.project_manifest_output,
            project_id=args.project_id,
            decision_id=args.decision_id,
            approved_by=args.approved_by,
            confirm_sections=args.confirm_sections,
            roots=args.root,
        )
    except (OSError, AuthorityPromoteError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt["technical_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
