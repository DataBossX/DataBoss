"""Typed contracts shared by the command center, agents, and providers."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_hash(value: Any) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class TaskContract:
    run_id: str
    task_id: str
    project_id: str
    role: str
    objective: str
    operation: str
    input_artifacts: List[str] = field(default_factory=list)
    allowed_paths: List[str] = field(default_factory=list)
    prohibited_paths: List[str] = field(default_factory=list)
    evidence_requirements: List[str] = field(default_factory=list)
    output_schema: str = "dbx.agent_result.v1"
    completion_criteria: List[str] = field(default_factory=list)
    cost_limit_usd: str = "0"
    timeout_seconds: int = 300
    max_retries: int = 2
    dependencies: List[str] = field(default_factory=list)
    required_citations: bool = True
    confidence_scale: str = "0-1"
    release_impact: str = "BLOCKING"
    parent_task_id: Optional[str] = None

    def validate(self) -> None:
        if not all((self.run_id, self.task_id, self.project_id, self.role, self.objective)):
            raise ValueError("task identity, role, and objective are required")
        if self.timeout_seconds < 1 or self.timeout_seconds > 86_400:
            raise ValueError("timeout_seconds must be between 1 and 86400")
        if self.max_retries < 0 or self.max_retries > 5:
            raise ValueError("max_retries must be between 0 and 5")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AgentResult:
    task_id: str
    provider: str
    model: str
    started_at: str
    completed_at: str
    status: str
    summary: str
    claims: List[Dict[str, Any]] = field(default_factory=list)
    citations: List[Dict[str, Any]] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)
    unresolved_items: List[str] = field(default_factory=list)
    contradictions: List[str] = field(default_factory=list)
    confidence_by_claim: Dict[str, str] = field(default_factory=dict)
    recommended_next_action: str = ""
    output_artifact_paths: List[str] = field(default_factory=list)
    response_hash: str = ""
    token_usage: Dict[str, int] = field(default_factory=dict)
    cost_usd: str = "0"
    retry_count: int = 0

    def _hash_payload(self) -> Dict[str, Any]:
        value = asdict(self)
        value.pop("response_hash", None)
        return value

    @property
    def computed_hash(self) -> str:
        return canonical_hash(self._hash_payload())

    def validate(self) -> None:
        if self.status not in {
            "SUCCEEDED",
            "BLOCKED",
            "FAILED_RETRYABLE",
            "FAILED_TERMINAL",
        }:
            raise ValueError(f"unsupported agent result status: {self.status}")
        if not self.task_id or not self.provider or not self.model:
            raise ValueError("task_id, provider, and model are required")
        if self.claims and not self.citations:
            raise ValueError("claims require citations")
        if not self.response_hash:
            raise ValueError("response_hash is required")
        if self.response_hash != self.computed_hash:
            raise ValueError("response_hash does not match canonical result content")

    def to_dict(self) -> Dict[str, Any]:
        value = asdict(self)
        if not value["response_hash"]:
            value["response_hash"] = self.computed_hash
        return value
