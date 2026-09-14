"""Build an unapproved Phase 1 authority draft from classified hashes.

The draft names candidate files and SHA-256 values only. It is not a
source-authority manifest, does not invent legal facts, and cannot be
passed to Phase 2 until a named examiner copies it into
``dbx.source_authority_manifest`` and hash-binds it.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .source_acquisition import (
    DEFAULT_REQUIRED_ROLES,
    PRIORITY_SECTIONS,
    SOURCE_ROLES,
    SourceAcquisitionError,
    SourceFile,
    build_receipt,
    parse_root,
)

DRAFT_SCHEMA_ID = "dbx.source_authority_draft"
DRAFT_SCHEMA_VERSION = "1.0"
UNAPPROVED_STATUS = "UNAPPROVED_DRAFT"
_ROLE_EQUIVALENTS = {
    "index": {"index", "handwritten_index"},
}


class AuthorityDraftError(ValueError):
    """Raised when an authority draft cannot be built safely."""


def draft_from_files(
    files: Sequence[SourceFile],
    *,
    requested_sections: Sequence[int] = PRIORITY_SECTIONS,
    required_roles: Sequence[str] = DEFAULT_REQUIRED_ROLES,
) -> Dict[str, object]:
    if not requested_sections or any(
        section not in PRIORITY_SECTIONS for section in requested_sections
    ):
        raise AuthorityDraftError(
            f"Requested sections must come from {PRIORITY_SECTIONS}"
        )
    if any(role not in SOURCE_ROLES for role in required_roles):
        raise AuthorityDraftError(
            f"Required roles must come from {sorted(SOURCE_ROLES)}"
        )
    authorities: List[Dict[str, object]] = []
    notes = [
        "This draft is not legal authority and cannot be passed to Phase 2",
        "A named examiner must copy it to a dbx.source_authority_manifest, "
        "set project_id, decision_id, and approved_by, then hash-bind it "
        "in the project manifest",
    ]
    for section in requested_sections:
        for role in required_roles:
            equivalents = _ROLE_EQUIVALENTS.get(role, {role})
            matches = [
                item
                for item in files
                if item.section == section and item.candidate_role in equivalents
            ]
            if not matches:
                notes.append(f"section {section} missing classified {role}")
                continue
            matches = sorted(
                matches,
                key=lambda item: (item.relative_path.casefold(), item.root_label),
            )
            chosen = matches[0]
            if len(matches) > 1:
                notes.append(
                    f"section {section} {role}: {len(matches)} classified "
                    "candidates; first sorted path used; examiner must confirm"
                )
            authorities.append(
                {
                    "root_label": chosen.root_label,
                    "relative_path": chosen.relative_path,
                    "section": section,
                    "role": role,
                    "expected_sha256": chosen.sha256,
                }
            )
    return {
        "schema_id": DRAFT_SCHEMA_ID,
        "schema_version": DRAFT_SCHEMA_VERSION,
        "status": UNAPPROVED_STATUS,
        "project_id": "",
        "decision_id": "",
        "approved_by": "",
        "authorities": authorities,
        "notes": notes,
    }


def draft_from_roots(
    roots: Sequence[str],
    *,
    requested_sections: Sequence[int] = PRIORITY_SECTIONS,
    required_roles: Sequence[str] = DEFAULT_REQUIRED_ROLES,
) -> Dict[str, object]:
    try:
        receipt = build_receipt(
            [parse_root(raw) for raw in roots],
            requested_sections=list(requested_sections),
            required_roles=list(required_roles),
        )
    except (OSError, SourceAcquisitionError) as exc:
        raise AuthorityDraftError(str(exc)) from exc
    return draft_from_files(
        receipt.files,
        requested_sections=requested_sections,
        required_roles=required_roles,
    )


def write_draft(draft: Dict[str, object], path: Path) -> Path:
    resolved = path.expanduser()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(
        json.dumps(draft, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return resolved


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Write an unapproved Phase 1 authority draft from classified "
            "hashes. This is not Phase 2 and not package release."
        )
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--root", action="append", default=[])
    parser.add_argument(
        "--section",
        dest="sections",
        type=int,
        action="append",
        choices=PRIORITY_SECTIONS,
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        if not args.root:
            raise AuthorityDraftError("Pass --root pc=<abs> and/or --root drive=<abs>")
        draft = draft_from_roots(
            args.root,
            requested_sections=args.sections or list(PRIORITY_SECTIONS),
        )
        write_draft(draft, args.output)
    except (OSError, AuthorityDraftError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "output": str(args.output),
                "status": draft["status"],
                "authority_count": len(draft["authorities"]),
                "packages_complete": False,
            },
            indent=2,
        )
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
