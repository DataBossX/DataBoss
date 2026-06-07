"""PipelineOrchestrator — chains all 5 stages with SQLite checkpointing.

Each stage writes its results to SQLite before proceeding.
If a job is resubmitted with the same ID and a non-terminal status,
it resumes from the last completed checkpoint.
"""

import asyncio
from datetime import datetime
from typing import Optional

from loguru import logger

from .db import ensure_jobs_table, get_job, upsert_job
from .models import Job
from .stages import run_extract, run_ingest, run_ocr, run_reason, run_report

STAGES = [
    ("ingesting", run_ingest),
    ("ocr", run_ocr),
    ("extracting", run_extract),
    ("reasoning", run_reason),
    ("reporting", run_report),
]

# Status order — used to determine which stages to skip on resume
STATUS_ORDER = {
    "queued": 0,
    "ingesting": 1,
    "ocr": 2,
    "extracting": 3,
    "reasoning": 4,
    "reporting": 5,
    "done": 6,
    "failed": 7,
}


class PipelineOrchestrator:

    def __init__(self):
        ensure_jobs_table()

    async def submit(self, job: Job) -> Job:
        """Save job to DB and kick off async execution (fire and forget)."""
        upsert_job(job.to_dict())
        asyncio.create_task(self._run(job))
        return job

    async def run_sync(self, job: Job) -> Job:
        """Run pipeline synchronously (blocks until done). Useful for testing."""
        upsert_job(job.to_dict())
        return await self._run(job)

    async def _run(self, job: Job) -> Job:
        logger.info(f"Pipeline starting: job={job.id} source={job.source}")

        for next_status, stage_fn in STAGES:
            # Skip stages already completed (resume logic)
            if STATUS_ORDER.get(job.status, 0) > STATUS_ORDER.get(next_status, 0):
                logger.debug(f"Skipping stage {next_status} (already past)")
                continue

            try:
                job = await stage_fn(job)
                self._checkpoint(job)
            except Exception as exc:
                job.status = "failed"
                job.error = str(exc)
                job.updated_at = datetime.utcnow().isoformat()
                job.log(next_status, f"FAILED: {exc}")
                self._checkpoint(job)
                logger.error(f"Pipeline failed at {next_status}: job={job.id} error={exc}")
                return job

        job.status = "done"
        job.updated_at = datetime.utcnow().isoformat()
        job.log("done", "Pipeline complete")
        self._checkpoint(job)
        logger.info(f"Pipeline done: job={job.id} cost=${job.total_cost:.4f}")
        return job

    def _checkpoint(self, job: Job) -> None:
        try:
            upsert_job(job.to_dict())
        except Exception as e:
            logger.error(f"Checkpoint failed for job {job.id}: {e}")

    def get_job(self, job_id: str) -> Optional[Job]:
        data = get_job(job_id)
        if not data:
            return None
        return Job.from_dict(data)

    def resume(self, job_id: str) -> Optional[Job]:
        """Reload a failed or stuck job and re-run from its last checkpoint."""
        job = self.get_job(job_id)
        if not job:
            return None
        if job.status in ("done",):
            return job
        # Reset failed status back one step so the failing stage reruns
        if job.status == "failed" and job.stage_log:
            job.status = "queued"
            job.error = None
        asyncio.create_task(self._run(job))
        return job


# Module-level singleton
orchestrator = PipelineOrchestrator()
