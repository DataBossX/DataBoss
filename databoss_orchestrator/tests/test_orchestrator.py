from pathlib import Path

import pytest
from pydantic import ValidationError

from databoss_orchestrator.adapters import FileDropAdapter
from databoss_orchestrator.cli import main
from databoss_orchestrator.models import AgentJob, JobState
from databoss_orchestrator.orchestrator import Orchestrator


def make_job(root: Path, prompt: Path, **overrides: object) -> AgentJob:
    values: dict[str, object] = {
        "agent": "cursor",
        "task_type": "noop",
        "prompt_file": str(prompt),
        "allowed_roots": [str(root.parent)],
        "output_root": str(root / "results"),
    }
    values.update(overrides)
    return AgentJob(**values)


def make_orchestrator(root: Path) -> Orchestrator:
    adapter = FileDropAdapter("cursor", root / "agents" / "cursor" / "inbox")
    return Orchestrator(root, {"cursor": adapter})


def test_package_and_cli_import_cleanly() -> None:
    assert callable(main)


def test_file_drop_claims_valid_job(tmp_path: Path) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("safe test", encoding="utf-8")
    root = tmp_path / "control"
    orchestrator = make_orchestrator(root)
    job = make_job(root, prompt)

    receipt = orchestrator.submit(job)

    assert receipt.state == JobState.CLAIMED
    assert (root / "claimed" / f"{job.job_id}__RECEIPT.json").exists()
    assert (root / "agents" / "cursor" / "inbox" / job.job_id / "JOB.json").exists()


def test_unknown_agent_is_rejected(tmp_path: Path) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("safe test", encoding="utf-8")
    root = tmp_path / "control"
    orchestrator = Orchestrator(root, {})
    job = make_job(root, prompt, agent="unknown")

    assert orchestrator.submit(job).state == JobState.REJECTED


@pytest.mark.parametrize("job_id", ["../escape", r"..\escape", "/absolute", ".", ".."])
def test_unsafe_job_id_is_rejected(tmp_path: Path, job_id: str) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("safe test", encoding="utf-8")

    with pytest.raises(ValidationError):
        make_job(tmp_path / "control", prompt, job_id=job_id)


def test_allowed_roots_are_required(tmp_path: Path) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("safe test", encoding="utf-8")

    with pytest.raises(ValidationError):
        make_job(tmp_path / "control", prompt, allowed_roots=[])


def test_prompt_outside_allowed_roots_is_rejected(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    prompt = tmp_path / "outside.md"
    prompt.write_text("safe test", encoding="utf-8")
    root = allowed / "control"
    orchestrator = make_orchestrator(root)
    job = make_job(root, prompt, allowed_roots=[str(allowed)])

    assert orchestrator.submit(job).state == JobState.REJECTED


def test_output_outside_allowed_roots_is_rejected(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    prompt = allowed / "prompt.md"
    prompt.write_text("safe test", encoding="utf-8")
    root = allowed / "control"
    orchestrator = make_orchestrator(root)
    job = make_job(
        root,
        prompt,
        allowed_roots=[str(allowed)],
        output_root=str(tmp_path / "outside"),
    )

    assert orchestrator.submit(job).state == JobState.REJECTED


def test_symlinked_prompt_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "source.md"
    source.write_text("safe test", encoding="utf-8")
    prompt = tmp_path / "prompt.md"
    prompt.symlink_to(source)
    root = tmp_path / "control"
    orchestrator = make_orchestrator(root)
    job = make_job(root, prompt)

    assert orchestrator.submit(job).state == JobState.REJECTED


def test_missing_required_approval_is_rejected(tmp_path: Path) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("safe test", encoding="utf-8")
    root = tmp_path / "control"
    orchestrator = make_orchestrator(root)
    job = make_job(root, prompt, approval_required=True)

    assert orchestrator.submit(job).state == JobState.REJECTED


def test_prompt_cannot_replace_package_artifact(tmp_path: Path) -> None:
    prompt = tmp_path / "JOB.json"
    prompt.write_text("safe test", encoding="utf-8")
    root = tmp_path / "control"
    orchestrator = make_orchestrator(root)
    job = make_job(root, prompt)

    assert orchestrator.submit(job).state == JobState.REJECTED
    assert not (root / "agents" / "cursor" / "inbox" / job.job_id).exists()


def test_approval_token_is_not_persisted(tmp_path: Path) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("safe test", encoding="utf-8")
    root = tmp_path / "control"
    orchestrator = make_orchestrator(root)
    job = make_job(
        root,
        prompt,
        approval_required=True,
        approval_token="do-not-persist",
    )

    assert orchestrator.submit(job).state == JobState.CLAIMED
    stored_job = (
        root / "agents" / "cursor" / "inbox" / job.job_id / "JOB.json"
    ).read_text(encoding="utf-8")
    assert "do-not-persist" not in stored_job
    assert "approval_token" not in stored_job


def test_duplicate_submission_does_not_overwrite(tmp_path: Path) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("safe test", encoding="utf-8")
    root = tmp_path / "control"
    orchestrator = make_orchestrator(root)
    job = make_job(root, prompt, job_id="stable-job-id")

    first = orchestrator.submit(job)
    package = root / "agents" / "cursor" / "inbox" / job.job_id / "JOB.json"
    receipt = root / "claimed" / f"{job.job_id}__RECEIPT.json"
    package_before = package.read_bytes()
    receipt_before = receipt.read_bytes()

    second = orchestrator.submit(job)

    assert first.state == JobState.CLAIMED
    assert second.state == JobState.REJECTED
    assert package.read_bytes() == package_before
    assert receipt.read_bytes() == receipt_before
    assert not (root / "rejected" / f"{job.job_id}__RECEIPT.json").exists()


def test_existing_empty_package_directory_is_not_overwritten(tmp_path: Path) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("safe test", encoding="utf-8")
    root = tmp_path / "control"
    orchestrator = make_orchestrator(root)
    job = make_job(root, prompt, job_id="reserved-job-id")
    package = root / "agents" / "cursor" / "inbox" / job.job_id
    package.mkdir()

    receipt = orchestrator.submit(job)

    assert receipt.state == JobState.REJECTED
    assert not any(package.iterdir())
