"""Typed project and work-order controls for auditable Horizon runs."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


class ControlFileError(ValueError):
    """Raised when a control file is incomplete or internally inconsistent."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ControlFileError(f"Cannot read control file {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ControlFileError(f"Control file {path} must contain a JSON object")
    return value


def _required(data: Dict[str, Any], field_name: str, source: Path) -> Any:
    value = data.get(field_name)
    if value in (None, "", []):
        raise ControlFileError(f"{source}: missing required field {field_name!r}")
    return value


@dataclass(frozen=True)
class CandidateDeliverable:
    path: str
    reported_sha256: str
    status: str = ""


@dataclass(frozen=True)
class ProjectManifest:
    path: Path
    project_id: str
    source_policy: str
    required_checks: List[str]
    candidates: List[CandidateDeliverable]
    release_policy: Dict[str, Any]
    metadata: Dict[str, str] = field(default_factory=dict)

    @property
    def project_root(self) -> Path:
        return self.path.parent

    @property
    def human_gate(self) -> str:
        return str(self.release_policy.get("human_gate", ""))

    def candidate(self, candidate_path: str) -> CandidateDeliverable:
        for item in self.candidates:
            if item.path == candidate_path:
                return item
        raise ControlFileError(
            f"{candidate_path!r} is not a candidate in {self.path}"
        )


def load_project_manifest(path: Path) -> ProjectManifest:
    path = Path(path)
    data = _read_json(path)
    if data.get("schema_id") != "dbx.project_manifest":
        raise ControlFileError(f"{path}: unsupported schema_id")

    release_policy = _required(data, "release_policy", path)
    if not isinstance(release_policy, dict):
        raise ControlFileError(f"{path}: release_policy must be an object")
    if release_policy.get("technical_verification_is_not_release") is not True:
        raise ControlFileError(
            f"{path}: technical_verification_is_not_release must be true"
        )
    if release_policy.get("approved_hash_required") is not True:
        raise ControlFileError(f"{path}: approved_hash_required must be true")
    if not release_policy.get("human_gate"):
        raise ControlFileError(f"{path}: release_policy.human_gate is required")

    raw_checks = _required(data, "required_checks", path)
    if not isinstance(raw_checks, list) or not all(
        isinstance(item, str) and item for item in raw_checks
    ):
        raise ControlFileError(f"{path}: required_checks must be non-empty strings")
    if len(raw_checks) != len(set(raw_checks)):
        raise ControlFileError(f"{path}: required_checks contains duplicates")

    candidates: List[CandidateDeliverable] = []
    for raw in _required(data, "candidate_deliverables", path):
        try:
            reported_hash = str(raw["reported_sha256"]).lower()
            if len(reported_hash) != 64 or any(
                char not in "0123456789abcdef" for char in reported_hash
            ):
                raise ValueError
            candidates.append(
                CandidateDeliverable(
                    path=str(raw["path"]),
                    reported_sha256=reported_hash,
                    status=str(raw.get("status", "")),
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ControlFileError(f"{path}: invalid candidate deliverable") from exc

    metadata = {
        key: str(data.get(key, ""))
        for key in ("jurisdiction", "county", "section", "township", "range")
    }
    return ProjectManifest(
        path=path,
        project_id=str(_required(data, "project_id", path)),
        source_policy=str(_required(data, "source_policy", path)),
        required_checks=list(raw_checks),
        candidates=candidates,
        release_policy=release_policy,
        metadata=metadata,
    )


@dataclass(frozen=True)
class WorkOrder:
    path: Path
    work_order_id: str
    project_id: str
    objective: str
    candidate_path: Path
    expected_sha256: str
    template_path: Optional[Path]
    profile_path: Optional[Path]
    staging_root: Path
    acceptance_tests: List[str]
    allowed_repairs: List[str]
    prohibited_paths: List[Path]
    max_attempts_per_defect: int
    stop_on_regression: bool
    require_human_approval: bool


def _resolve_control_path(value: Optional[str], base: Path) -> Optional[Path]:
    if not value:
        return None
    path = Path(value).expanduser()
    return path if path.is_absolute() else (base / path).resolve()


def load_work_order(path: Path, manifest: ProjectManifest) -> WorkOrder:
    path = Path(path)
    data = _read_json(path)
    if data.get("schema_id") != "dbx.work_order":
        raise ControlFileError(f"{path}: unsupported schema_id")
    project_id = str(_required(data, "project_id", path))
    if project_id != manifest.project_id:
        raise ControlFileError(
            f"{path}: project_id {project_id!r} does not match manifest"
        )

    candidate_ref = str(_required(data, "candidate_path", path))
    candidate = manifest.candidate(candidate_ref)
    expected_hash = str(data.get("expected_sha256") or candidate.reported_sha256).lower()
    if expected_hash != candidate.reported_sha256:
        raise ControlFileError(
            f"{path}: expected_sha256 differs from the manifest candidate hash"
        )

    acceptance = list(data.get("acceptance_tests") or manifest.required_checks)
    unknown = sorted(set(acceptance) - set(manifest.required_checks))
    if unknown:
        raise ControlFileError(f"{path}: checks absent from manifest: {unknown}")

    retry = data.get("retry_policy") or {}
    attempts = int(retry.get("max_attempts_per_defect", 3))
    if not 0 <= attempts <= 10:
        raise ControlFileError(f"{path}: max_attempts_per_defect must be 0..10")

    constraints = data.get("constraints") or {}
    if constraints.get("edit_originals", False):
        raise ControlFileError(f"{path}: edit_originals must be false")
    promotion = data.get("promotion") or {}
    if promotion.get("require_human_approval", True) is not True:
        raise ControlFileError(f"{path}: human approval cannot be disabled")

    base = path.parent
    candidate_path = _resolve_control_path(
        data.get("candidate_local_path") or candidate_ref, base
    )
    staging_root = _resolve_control_path(
        data.get("staging_root") or "runs", base
    )
    assert candidate_path is not None and staging_root is not None

    return WorkOrder(
        path=path,
        work_order_id=str(_required(data, "work_order_id", path)),
        project_id=project_id,
        objective=str(_required(data, "objective", path)),
        candidate_path=candidate_path,
        expected_sha256=expected_hash,
        template_path=_resolve_control_path(data.get("template_path"), base),
        profile_path=_resolve_control_path(data.get("profile_path"), base),
        staging_root=staging_root,
        acceptance_tests=acceptance,
        allowed_repairs=list(data.get("allowed_repairs") or []),
        prohibited_paths=[
            resolved
            for value in data.get("prohibited_paths", [])
            if (resolved := _resolve_control_path(str(value), base)) is not None
        ],
        max_attempts_per_defect=attempts,
        stop_on_regression=bool(retry.get("stop_on_regression", True)),
        require_human_approval=True,
    )
