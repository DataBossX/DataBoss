from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


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
    allowed_roots: list[str] = Field(default_factory=list)
    output_root: str
    risk_level: RiskLevel = RiskLevel.LOW
    approval_required: bool = False
    approval_token: str | None = None
    timeout_seconds: int = Field(default=3600, ge=1, le=86400)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def validate_paths(self) -> None:
        output = Path(self.output_root).resolve()
        allowed = [Path(root).resolve() for root in self.allowed_roots]
        if allowed and not any(output == root or root in output.parents for root in allowed):
            raise ValueError(f"output_root is outside allowed_roots: {output}")
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
