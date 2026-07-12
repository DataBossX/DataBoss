from __future__ import annotations

import json
import os
import tempfile
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
JOB_RESERVATION_DIRECTORY = ".job_ids"


def initialize_control_plane(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for name in (*QUEUE_NAMES, JOB_RESERVATION_DIRECTORY):
        directory = root / name
        if directory.is_symlink():
            raise ValueError(f"Control-plane directory must not be a symlink: {name}")
        directory.mkdir(exist_ok=True)


class Orchestrator:
    def __init__(self, root: Path, adapters: dict[str, AgentAdapter]) -> None:
        self.root = root.resolve()
        self.adapters = adapters
        initialize_control_plane(self.root)

    def submit(self, job: AgentJob) -> AgentReceipt:
        if not self._reserve_job_id(job.job_id):
            return self._duplicate_receipt(job)

        if job.agent not in self.adapters:
            receipt = AgentReceipt(
                job_id=job.job_id,
                agent=job.agent,
                state=JobState.REJECTED,
                message="Unknown agent adapter",
                errors=[job.agent],
            )
        else:
            adapter = self.adapters[job.agent]
            healthy, detail = adapter.healthcheck()
            if not healthy:
                receipt = AgentReceipt(
                    job_id=job.job_id,
                    agent=job.agent,
                    state=JobState.FAILED,
                    message="Agent healthcheck failed",
                    errors=[detail],
                )
            else:
                receipt = adapter.execute(job, self.root)

        if not self._write_receipt(receipt):
            return self._duplicate_receipt(job)
        return receipt

    def _has_receipt(self, job_id: str) -> bool:
        return any(
            (self.root / state.value / f"{job_id}__RECEIPT.json").exists()
            for state in JobState
        )

    def _reserve_job_id(self, job_id: str) -> bool:
        if self._has_receipt(job_id):
            return False

        reservation = self.root / JOB_RESERVATION_DIRECTORY / job_id
        try:
            descriptor = os.open(
                reservation,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o600,
            )
        except FileExistsError:
            return False
        os.close(descriptor)
        return True

    @staticmethod
    def _duplicate_receipt(job: AgentJob) -> AgentReceipt:
        return AgentReceipt(
            job_id=job.job_id,
            agent=job.agent,
            state=JobState.REJECTED,
            message="Duplicate job ID",
        )

    def _write_receipt(self, receipt: AgentReceipt) -> bool:
        path = self.root / receipt.state.value / f"{receipt.job_id}__RECEIPT.json"
        fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(receipt.model_dump_json(indent=2))
                handle.flush()
                os.fsync(handle.fileno())
            os.link(temporary, path)
        except FileExistsError:
            return False
        finally:
            temporary.unlink(missing_ok=True)
        return True

    def health_report(self) -> dict[str, dict[str, object]]:
        report: dict[str, dict[str, object]] = {}
        for name, adapter in self.adapters.items():
            healthy, detail = adapter.healthcheck()
            report[name] = {"healthy": healthy, "detail": detail}
        (self.root / "logs" / "AGENT_HEALTH.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        return report
