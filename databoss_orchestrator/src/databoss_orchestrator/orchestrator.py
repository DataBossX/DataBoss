from __future__ import annotations

import json
from pathlib import Path

from databoss_orchestrator.adapters.base import AgentAdapter
from databoss_orchestrator.models import AgentJob, AgentReceipt, JobState


QUEUE_NAMES = (
    "inbox",
    "claimed",
    "running",
    "completed",
    "failed",
    "rejected",
    "quarantine",
    "logs",
    "results",
    "approvals",
    "agents",
)


def initialize_control_plane(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for name in QUEUE_NAMES:
        (root / name).mkdir(exist_ok=True)


class Orchestrator:
    def __init__(self, root: Path, adapters: dict[str, AgentAdapter]) -> None:
        self.root = root.resolve()
        self.adapters = adapters
        initialize_control_plane(self.root)

    def submit(self, job: AgentJob) -> AgentReceipt:
        if job.agent not in self.adapters:
            return AgentReceipt(
                job_id=job.job_id,
                agent=job.agent,
                state=JobState.REJECTED,
                message="Unknown agent adapter",
                errors=[job.agent],
            )
        adapter = self.adapters[job.agent]
        healthy, detail = adapter.healthcheck()
        if not healthy:
            return AgentReceipt(
                job_id=job.job_id,
                agent=job.agent,
                state=JobState.FAILED,
                message="Agent healthcheck failed",
                errors=[detail],
            )
        receipt = adapter.execute(job, self.root)
        self._write_receipt(receipt)
        return receipt

    def _write_receipt(self, receipt: AgentReceipt) -> None:
        path = self.root / receipt.state.value / f"{receipt.job_id}__RECEIPT.json"
        path.write_text(receipt.model_dump_json(indent=2), encoding="utf-8")

    def health_report(self) -> dict[str, dict[str, object]]:
        report: dict[str, dict[str, object]] = {}
        for name, adapter in self.adapters.items():
            healthy, detail = adapter.healthcheck()
            report[name] = {"healthy": healthy, "detail": detail}
        (self.root / "logs" / "AGENT_HEALTH.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        return report
