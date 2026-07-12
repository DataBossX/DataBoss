"""Fail-closed filesystem, operation, redaction, and prompt controls."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Iterable


class SecurityViolation(ValueError):
    """Raised when untrusted work exceeds an administrator-owned policy."""


FORBIDDEN_OPERATIONS = frozenset(
    {
        "arbitrary_shell",
        "arbitrary_python",
        "unrestricted_file_write",
        "unrestricted_delete",
        "credential_entry",
        "external_publish",
        "permission_change",
        "purchase_records",
        "git_merge",
        "remote_code_execution",
    }
)

APPROVED_OPERATIONS = frozenset(
    {
        "communication_loop_self_test",
        "inventory_artifacts_read_only",
        "verify_hashes_read_only",
        "reconcile_source_manifests",
        "run_section32_evidence_audit",
        "build_missing_evidence_manifest",
        "run_isolated_workbook_qa",
        "repair_isolated_workbook",
        "compare_workbook_to_template",
        "run_multi_agent_analysis",
        "build_release_gate_matrix",
        "package_section32_candidate",
    }
)

_SECRET_KEY_RE = re.compile(
    r"(?i)(api[_-]?key|token|password|secret|authorization|connection[_-]?string)"
)
_SECRET_VALUE_RE = re.compile(
    r"(?i)(bearer\s+[a-z0-9._~+/=-]{8,}|"
    r"(?:sk|xox[baprs]|gh[pousr])[-_a-z0-9]{8,})"
)
_PROMPT_INJECTION_RE = re.compile(
    r"(?i)(ignore\s+(?:all\s+)?(?:previous|prior|system)\s+instructions|"
    r"reveal\s+(?:the\s+)?(?:system\s+prompt|secret|token)|"
    r"execute\s+(?:this\s+)?(?:shell|python|command)|"
    r"disable\s+(?:security|policy|guardrail))"
)


def validate_operation(operation: str) -> str:
    if operation in FORBIDDEN_OPERATIONS or operation not in APPROVED_OPERATIONS:
        raise SecurityViolation(f"operation is not allowlisted: {operation!r}")
    return operation


def resolve_bounded_path(
    candidate: Path,
    approved_roots: Iterable[Path],
    *,
    must_exist: bool = False,
    reject_symlinks: bool = True,
) -> Path:
    candidate = Path(candidate).expanduser()
    if ".." in candidate.parts:
        raise SecurityViolation("path traversal is prohibited")
    if reject_symlinks:
        current = candidate if candidate.is_absolute() else Path.cwd() / candidate
        for part in [current, *current.parents]:
            if part.exists() and part.is_symlink():
                raise SecurityViolation(f"symlink paths are prohibited: {candidate}")
    resolved = candidate.resolve(strict=must_exist)
    roots = [Path(root).expanduser().resolve(strict=False) for root in approved_roots]
    if not any(_relative_to(resolved, root) for root in roots):
        raise SecurityViolation("path is outside approved roots")
    return resolved


def _relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def redact(value: object) -> object:
    if isinstance(value, dict):
        return {
            str(key): "[REDACTED]" if _SECRET_KEY_RE.search(str(key)) else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact(item) for item in value)
    if isinstance(value, str):
        return _SECRET_VALUE_RE.sub("[REDACTED]", value)
    return value


def inspect_untrusted_text(text: str) -> bool:
    """Return True when text contains instructions that must remain inert."""
    return bool(_PROMPT_INJECTION_RE.search(text or ""))


def credential_status(environment_name: str) -> str:
    """Report presence only; never return an environment value."""
    return "YES" if os.environ.get(environment_name) else "NO"
