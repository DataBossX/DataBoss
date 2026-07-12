from __future__ import annotations

import re
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


_SAFE_JOB_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def _is_within(path: Path, roots: list[Path]) -> bool:
    return any(path == root or root in path.parents for root in roots)


class JobState(StrEnum):
    INBOX = "inbox"
    CLAIMED = "claimed"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"
    QUARANTINE = "quarantine"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AgentJob(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    agent: str
    task_type: str
    prompt_file: str
    allowed_roots: list[str] = Field(min_length=1)
    output_root: str
    risk_level: RiskLevel = RiskLevel.LOW
    approval_required: bool = False
    approval_token: str | None = Field(default=None, exclude=True, repr=False)
    timeout_seconds: int = Field(default=3600, ge=1, le=86400)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("job_id")
    @classmethod
    def validate_job_id(cls, value: str) -> str:
        if value in {".", ".."} or not _SAFE_JOB_ID_PATTERN.fullmatch(value):
            raise ValueError("job_id must be a safe opaque identifier")
        return value

    def validate_paths(self) -> None:
        output = Path(self.output_root).resolve()
        allowed = [Path(root).resolve() for root in self.allowed_roots]
        prompt = Path(self.prompt_file)
        resolved_prompt = prompt.resolve()

        if not _is_within(output, allowed):
            raise ValueError(f"output_root is outside allowed_roots: {output}")
        if not _is_within(resolved_prompt, allowed):
            raise ValueError(f"prompt_file is outside allowed_roots: {resolved_prompt}")
        if prompt.is_symlink():
            raise ValueError("prompt_file must not be a symlink")
        if self.approval_required and not self.approval_token:
            raise ValueError("approval_token is required for this job")


class AgentReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    agent: str
    state: JobState
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    message: str
    progress_percent: float = Field(default=0, ge=0, le=100)
    input_hashes: dict[str, str] = Field(default_factory=dict)
    output_hashes: dict[str, str] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
