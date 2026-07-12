from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

from databoss_orchestrator.adapters.base import AgentAdapter
from databoss_orchestrator.models import AgentJob, AgentReceipt, JobState


_PACKAGE_ARTIFACT_NAMES = {"claim.json", "job.json"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class FileDropAdapter(AgentAdapter):
    """Safe adapter that drops a validated prompt package into an agent inbox."""

    def __init__(self, name: str, inbox: Path) -> None:
        self.name = name
        self.inbox = inbox

    def healthcheck(self) -> tuple[bool, str]:
        if self.inbox.is_symlink():
            return False, "Agent inbox must not be a symlink"
        self.inbox.mkdir(parents=True, exist_ok=True)
        return self.inbox.is_dir(), str(self.inbox)

    def execute(self, job: AgentJob, workspace: Path) -> AgentReceipt:
        try:
            job.validate_paths()
        except ValueError:
            return self._rejected_receipt(
                job,
                "Job failed path or approval validation",
            )

        workspace = workspace.resolve()
        inbox = self.inbox.resolve()
        if self.inbox.is_symlink() or not (
            inbox == workspace or workspace in inbox.parents
        ):
            return self._rejected_receipt(
                job,
                "Agent inbox is outside the control plane",
            )

        prompt = Path(job.prompt_file).resolve()
        if not prompt.is_file():
            return AgentReceipt(
                job_id=job.job_id,
                agent=self.name,
                state=JobState.FAILED,
                message="Prompt file is missing",
            )
        if prompt.name.casefold() in _PACKAGE_ARTIFACT_NAMES:
            return self._rejected_receipt(
                job,
                "Prompt filename conflicts with a package artifact",
            )

        target = inbox / job.job_id
        reservation = inbox / f".{job.job_id}.lock"
        try:
            descriptor = os.open(
                reservation,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o600,
            )
        except FileExistsError:
            return self._rejected_receipt(job, "Duplicate job ID")
        os.close(descriptor)

        if os.path.lexists(target):
            return self._rejected_receipt(job, "Duplicate job ID")

        staging: Path | None = None
        try:
            staging = Path(tempfile.mkdtemp(prefix=f".{job.job_id}.", dir=inbox))
            copied_prompt = staging / prompt.name
            shutil.copy2(prompt, copied_prompt)
            (staging / "JOB.json").write_text(
                job.model_dump_json(indent=2), encoding="utf-8"
            )
            input_hashes = {
                prompt.name: sha256_file(copied_prompt),
                "JOB.json": sha256_file(staging / "JOB.json"),
            }
            (staging / "CLAIM.json").write_text(
                json.dumps(
                    {
                        "job_id": job.job_id,
                        "agent": self.name,
                        "state": JobState.CLAIMED,
                        "input_hashes": input_hashes,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            if os.path.lexists(target):
                return self._rejected_receipt(job, "Duplicate job ID")
            os.rename(staging, target)
        except FileExistsError:
            return self._rejected_receipt(job, "Duplicate job ID")
        except Exception:
            reservation.unlink(missing_ok=True)
            raise
        finally:
            if staging is not None and staging.exists():
                shutil.rmtree(staging)

        return AgentReceipt(
            job_id=job.job_id,
            agent=self.name,
            state=JobState.CLAIMED,
            message="Job package delivered",
            progress_percent=5,
            input_hashes=input_hashes,
        )

    def _rejected_receipt(self, job: AgentJob, message: str) -> AgentReceipt:
        return AgentReceipt(
            job_id=job.job_id,
            agent=self.name,
            state=JobState.REJECTED,
            message=message,
        )
