"""BaseAgent — every DataBossX agent leaves proof of what it did.

Agents are labor. Each meaningful action is appended as a JSONL record to
agent_outputs/<agent_name>.jsonl so there is always an auditable trail.
"""
from __future__ import annotations

import datetime
import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from app.logging_setup import get_logger

ROOT = Path(__file__).resolve().parent.parent
AGENT_OUTPUTS = ROOT / "agent_outputs"


class BaseAgent(ABC):
    """Subclass and implement run(). Use log_action() to leave proof."""

    def __init__(self, name: str, *, outputs_dir: Path | None = None) -> None:
        self.name = name
        self.log = get_logger(f"agent.{name}")
        self.outputs_dir = outputs_dir or AGENT_OUTPUTS
        self.outputs_dir.mkdir(parents=True, exist_ok=True)
        self._proof_path = self.outputs_dir / f"{name}.jsonl"

    def log_action(self, action: str, **detail: Any) -> dict[str, Any]:
        """Record one auditable action. Returns the record written."""
        record = {
            "ts": datetime.datetime.now().isoformat(timespec="seconds"),
            "agent": self.name,
            "action": action,
            "detail": detail,
        }
        with open(self._proof_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
        self.log.info("%s | %s", action, detail or "")
        return record

    @abstractmethod
    def run(self, *args: Any, **kwargs: Any) -> Any:
        """Perform the agent's work. Must call log_action() for key steps."""
        raise NotImplementedError
