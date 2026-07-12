from pathlib import Path

from databoss_orchestrator.adapters import FileDropAdapter
from databoss_orchestrator.models import AgentJob, JobState
from databoss_orchestrator.orchestrator import Orchestrator


def test_file_drop_claims_valid_job(tmp_path: Path) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("safe test", encoding="utf-8")
    root = tmp_path / "control"
    adapter = FileDropAdapter("cursor", root / "agents" / "cursor" / "inbox")
    orchestrator = Orchestrator(root, {"cursor": adapter})
    job = AgentJob(
        agent="cursor",
        task_type="noop",
        prompt_file=str(prompt),
        allowed_roots=[str(root)],
        output_root=str(root / "results"),
    )

    receipt = orchestrator.submit(job)

    assert receipt.state == JobState.CLAIMED
    assert (root / "claimed" / f"{job.job_id}__RECEIPT.json").exists()
    assert (root / "agents" / "cursor" / "inbox" / job.job_id / "JOB.json").exists()


def test_unknown_agent_is_rejected(tmp_path: Path) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("safe test", encoding="utf-8")
    root = tmp_path / "control"
    orchestrator = Orchestrator(root, {})
    job = AgentJob(
        agent="unknown",
        task_type="noop",
        prompt_file=str(prompt),
        allowed_roots=[str(root)],
        output_root=str(root / "results"),
    )

    assert orchestrator.submit(job).state == JobState.REJECTED
