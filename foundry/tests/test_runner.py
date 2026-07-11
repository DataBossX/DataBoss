from __future__ import annotations

import json
from pathlib import Path

import pytest

from databossx.errors import PlanError, TaskFailed
from databossx.runner import run_task, split_ref
from databossx.scaffold import scaffold_project


def read_events(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def write_plan(project_dir: Path, body: str) -> None:
    (project_dir / "PLAN.md").write_text("## Tasks\n\n" + body, encoding="utf-8")


def test_split_ref():
    assert split_ref("demo.hello") == ("demo", "hello")
    for bad in ("demo", "demo.", ".hello", "a.b.c"):
        with pytest.raises(PlanError):
            split_ref(bad)


def test_hello_task_end_to_end(config):
    scaffold_project(config, "demo")
    result = run_task(config, "demo.hello")
    assert result.status == "success"
    assert result.steps[0].returncode == 0
    assert "hello from demo" in result.steps[0].stdout_tail

    # Structured log with timing.
    events = read_events(result.log_path)
    kinds = [e["event"] for e in events]
    assert kinds == ["task_start", "step_start", "step_end", "task_end"]
    assert events[2]["duration_s"] >= 0
    assert events[3]["status"] == "success"

    # Versioned output.
    assert result.output_path.name == "hello_result_v001.json"
    payload = json.loads(result.output_path.read_text(encoding="utf-8"))
    assert payload["status"] == "success"
    assert "hello from demo" in payload["steps"][0]["stdout_tail"]

    # STATUS.json updated.
    status = json.loads((result.output_path.parents[1] / "STATUS.json").read_text())
    assert status["status"] == "success"
    assert status["last_run"]["task"] == "demo.hello"
    assert len(status["history"]) == 1


def test_second_run_gets_next_versions(config):
    scaffold_project(config, "demo")
    first = run_task(config, "demo.hello")
    second = run_task(config, "demo.hello")
    assert first.output_path.name == "hello_result_v001.json"
    assert second.output_path.name == "hello_result_v002.json"
    assert first.log_path.name == "hello_run_v001.jsonl"
    assert second.log_path.name == "hello_run_v002.jsonl"
    # First run's artifacts are untouched.
    assert json.loads(first.output_path.read_text())["run"] == "hello_run_v001"


def test_multi_step_task_runs_sequentially(config):
    scaffold_project(config, "demo")
    project_dir = config.projects_dir / "demo"
    write_plan(project_dir, (
        "### steps\n"
        '- cmd: {python} -c "open(r\'{outputs}/a.txt\',\'w\').write(\'A\')"\n'
        '- cmd: {python} -c "print(open(r\'{outputs}/a.txt\').read())"\n'
    ))
    result = run_task(config, "demo.steps")
    assert [s.returncode for s in result.steps] == [0, 0]
    assert "A" in result.steps[1].stdout_tail


def test_failure_rolls_back_new_outputs(config):
    scaffold_project(config, "demo")
    project_dir = config.projects_dir / "demo"
    keeper = project_dir / "outputs" / "keep.txt"
    keeper.write_text("pre-existing")
    write_plan(project_dir, (
        "### boom\n"
        '- cmd: {python} -c "open(r\'{outputs}/partial.txt\',\'w\').write(\'junk\')"\n'
        '- cmd: {python} -c "import sys; sys.exit(3)"\n'
    ))
    with pytest.raises(TaskFailed, match="exited 3"):
        run_task(config, "demo.boom")

    # The partial artifact was moved out of outputs/, never deleted.
    assert not (project_dir / "outputs" / "partial.txt").exists()
    rolled = project_dir / "work" / "rollback" / "boom_run_v001" / "partial.txt"
    assert rolled.read_text() == "junk"
    # Pre-existing outputs are untouched.
    assert keeper.read_text() == "pre-existing"

    events = read_events(project_dir / "work" / "logs" / "boom_run_v001.jsonl")
    assert any(e["event"] == "rollback" for e in events)
    status = json.loads((project_dir / "STATUS.json").read_text())
    assert status["status"] == "failed"
    assert "exited 3" in status["last_run"]["error"]


def test_failed_step_stops_remaining_steps(config):
    scaffold_project(config, "demo")
    project_dir = config.projects_dir / "demo"
    write_plan(project_dir, (
        "### halt\n"
        '- cmd: {python} -c "import sys; sys.exit(1)"\n'
        '- cmd: {python} -c "open(r\'{outputs}/never.txt\',\'w\').write(\'x\')"\n'
    ))
    with pytest.raises(TaskFailed):
        run_task(config, "demo.halt")
    assert not (project_dir / "outputs" / "never.txt").exists()


def test_timeout_fails_the_task(config):
    scaffold_project(config, "demo")
    project_dir = config.projects_dir / "demo"
    write_plan(project_dir, (
        "### slow\n"
        '- cmd: {python} -c "import time; time.sleep(30)"\n'
        "- timeout: 0.5\n"
    ))
    with pytest.raises(TaskFailed, match="slow"):
        run_task(config, "demo.slow")
    status = json.loads((project_dir / "STATUS.json").read_text())
    assert status["status"] == "failed"


def test_unknown_task_lists_available(config):
    scaffold_project(config, "demo")
    with pytest.raises(PlanError, match="available: hello"):
        run_task(config, "demo.ghost")


def test_unlaunchable_command_fails_cleanly(config):
    scaffold_project(config, "demo")
    project_dir = config.projects_dir / "demo"
    write_plan(project_dir, "### nope\n- cmd: definitely-not-a-real-binary-xyz\n")
    with pytest.raises(TaskFailed):
        run_task(config, "demo.nope")


def test_corrupt_status_is_preserved_not_discarded(config):
    scaffold_project(config, "demo")
    project_dir = config.projects_dir / "demo"
    (project_dir / "STATUS.json").write_text("{not json", encoding="utf-8")
    run_task(config, "demo.hello")
    assert (project_dir / "STATUS.corrupt.json").read_text() == "{not json"
    assert json.loads((project_dir / "STATUS.json").read_text())["status"] == "success"
