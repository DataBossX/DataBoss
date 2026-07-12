from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from databoss_orchestrator.adapters.base import AgentAdapter
from databoss_orchestrator.models import AgentJob, AgentReceipt, JobState


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
        self.inbox.mkdir(parents=True, exist_ok=True)
        return self.inbox.is_dir(), str(self.inbox)

    def execute(self, job: AgentJob, workspace: Path) -> AgentReceipt:
        job.validate_paths()
        prompt = Path(job.prompt_file).resolve()
        if not prompt.is_file():
            return AgentReceipt(
                job_id=job.job_id,
                agent=self.name,
                state=JobState.FAILED,
                message="Prompt file is missing",
                errors=[str(prompt)],
            )

        target = self.inbox / job.job_id
        target.mkdir(parents=True, exist_ok=False)
        copied_prompt = target / prompt.name
        shutil.copy2(prompt, copied_prompt)
        (target / "JOB.json").write_text(
            job.model_dump_json(indent=2), encoding="utf-8"
        )
        input_hashes = {
            prompt.name: sha256_file(copied_prompt),
            "JOB.json": sha256_file(target / "JOB.json"),
        }
        (target / "CLAIM.json").write_text(
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
        return AgentReceipt(
            job_id=job.job_id,
            agent=self.name,
            state=JobState.CLAIMED,
            message=f"Job package delivered to {target}",
            progress_percent=5,
            input_hashes=input_hashes,
        )
