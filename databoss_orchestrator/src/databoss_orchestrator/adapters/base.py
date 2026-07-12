from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from databoss_orchestrator.models import AgentJob, AgentReceipt


class AgentAdapter(ABC):
    """Contract implemented by every AI integration."""

    name: str

    @abstractmethod
    def healthcheck(self) -> tuple[bool, str]:
        raise NotImplementedError

    @abstractmethod
    def execute(self, job: AgentJob, workspace: Path) -> AgentReceipt:
        raise NotImplementedError
