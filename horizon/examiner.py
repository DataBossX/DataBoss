"""Shared fail-closed checks for named examiners.

These helpers do not invent names, page counts, or legal facts. They only
reject placeholders so writer-held packets cannot be auto-approved.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, Set

REPO_ROOT = Path(__file__).resolve().parents[1]
ID_RE = re.compile(r"^[A-Z][A-Z0-9._-]{2,63}$")
PLACEHOLDER_IDS = {
    "decision_id",
    "examiner_decision_id",
    "examiner_project_id",
    "project_id",
    "source-auth-000",
    "tbd",
    "todo",
}
PLACEHOLDER_NAMES = {
    "approved_by",
    "changeme",
    "examiner",
    "examiner_name",
    "n/a",
    "na",
    "named human examiner",
    "operator",
    "placeholder",
    "tbd",
    "todo",
    "unknown",
}


def is_placeholder(value: str, banned: Set[str]) -> bool:
    folded = value.strip().casefold()
    if folded in banned:
        return True
    if folded.startswith("<") and folded.endswith(">"):
        return True
    if folded.startswith("examiner_") or folded.endswith("_here"):
        return True
    return False


def require_named_examiner(value: str) -> str:
    stripped = " ".join(value.split())
    if (
        len(stripped) < 3
        or len(stripped) > 80
        or not any(character.isalpha() for character in stripped)
        or is_placeholder(stripped, PLACEHOLDER_NAMES)
    ):
        raise ValueError("operator must be a named examiner, not a placeholder")
    return stripped


def require_assigned_id(value: str, field_name: str) -> str:
    stripped = value.strip()
    if not ID_RE.fullmatch(stripped) or is_placeholder(stripped, PLACEHOLDER_IDS):
        raise ValueError(
            f"{field_name} must be an examiner-assigned id, not a placeholder"
        )
    return stripped


def assert_outside_repo(path: Path, label: str) -> Path:
    resolved = path.expanduser().resolve()
    if resolved == REPO_ROOT or REPO_ROOT in resolved.parents:
        raise ValueError(f"{label} must be outside this repository")
    return resolved


def write_new_json(payload: Dict[str, object], path: Path, label: str) -> Path:
    resolved = assert_outside_repo(path, label)
    if resolved.exists():
        raise ValueError(f"{label} already exists: {resolved}")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return resolved
