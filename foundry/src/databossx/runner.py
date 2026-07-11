"""``databossx run <project>.<task>`` — execute a task declared in PLAN.md.

Guarantees:

* **Structured logs** — every run appends a JSONL event stream under
  ``work/logs/<task>_run_vNNN.jsonl`` (task_start, step_start, step_end,
  rollback, task_end) with wall-clock timing per step.
* **Versioned output** — a successful run writes
  ``outputs/<task>_result_vNNN.json``; nothing is ever overwritten.
* **Rollback on failure** — any file a failing task left in ``outputs/`` is
  moved (never deleted) to ``work/rollback/<run>/`` so outputs only ever
  contain artifacts of successful runs.
* **STATUS.json** — updated after every run with the outcome and a capped
  history so dashboards can poll it.
"""

from __future__ import annotations

import json
import logging
import os
import shlex
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

from .config import FoundryConfig
from .envs import resolve_project_dir, venv_python
from .errors import PlanError, TaskFailed
from .logs import JsonlLogger, utc_now_iso
from .planfile import TaskSpec, parse_plan_file
from .versioned import next_version_path, versioned_write_json

log = logging.getLogger("databossx.runner")

Runner = Callable[..., subprocess.CompletedProcess]

HISTORY_CAP = 100
_TAIL = 2000


@dataclass
class StepResult:
    cmd: str
    returncode: int
    duration_s: float
    stdout_tail: str
    stderr_tail: str


@dataclass
class RunResult:
    project: str
    task: str
    run_name: str
    status: str  # "success" | "failed"
    duration_s: float
    log_path: Path
    output_path: Optional[Path] = None
    rollback_dir: Optional[Path] = None
    steps: List[StepResult] = field(default_factory=list)


def split_ref(ref: str) -> tuple:
    """``demo.hello`` -> (``demo``, ``hello``)."""
    if "." not in ref:
        raise PlanError(
            f"task reference {ref!r} must be '<project>.<task>' (e.g. demo.hello)"
        )
    project, task = ref.split(".", 1)
    if not project or not task or "." in task:
        raise PlanError(f"malformed task reference {ref!r}: expected '<project>.<task>'")
    return project, task


def _placeholders(project_dir: Path) -> Dict[str, str]:
    venv_py = venv_python(project_dir / ".venv")
    return {
        "python": str(venv_py) if venv_py.exists() else sys.executable,
        "project_dir": str(project_dir),
        "inbox": str(project_dir / "inbox"),
        "work": str(project_dir / "work"),
        "outputs": str(project_dir / "outputs"),
        "proofs": str(project_dir / "proofs"),
    }


def _expand(cmd: str, mapping: Dict[str, str]) -> str:
    for key, value in mapping.items():
        cmd = cmd.replace("{" + key + "}", value)
    return cmd


def _snapshot(outputs_dir: Path) -> set:
    if not outputs_dir.is_dir():
        return set()
    return {p.relative_to(outputs_dir) for p in outputs_dir.rglob("*") if p.is_file()}


def _rollback(outputs_dir: Path, before: set, rollback_dir: Path, events: JsonlLogger) -> List[str]:
    """Move files created during a failed run out of outputs/ (never delete)."""
    moved: List[str] = []
    for rel in sorted(_snapshot(outputs_dir) - before):
        src = outputs_dir / rel
        dst = rollback_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        moved.append(str(rel))
        events.event("rollback", file=str(rel), moved_to=str(dst))
    return moved


def _update_status(project_dir: Path, entry: Dict[str, object]) -> None:
    status_path = project_dir / "STATUS.json"
    try:
        data = json.loads(status_path.read_text(encoding="utf-8")) if status_path.exists() else {}
    except json.JSONDecodeError:
        # Preserve the corrupt original rather than silently discarding it.
        corrupt = status_path.with_name("STATUS.corrupt.json")
        if not corrupt.exists():
            shutil.copy2(status_path, corrupt)
        data = {}
    data.setdefault("history", [])
    data["status"] = entry["status"]
    data["last_run"] = entry
    data["history"] = (data["history"] + [entry])[-HISTORY_CAP:]
    status_path.write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def run_task(
    config: FoundryConfig,
    ref: str,
    run: Runner = subprocess.run,
    extra_env: Optional[Dict[str, str]] = None,
) -> RunResult:
    project, task_name = split_ref(ref)
    project_dir = resolve_project_dir(config, project)
    tasks = parse_plan_file(project_dir / "PLAN.md")
    if task_name not in tasks:
        raise PlanError(
            f"task {task_name!r} not declared in {project_dir / 'PLAN.md'} "
            f"(available: {', '.join(sorted(tasks))})"
        )
    spec: TaskSpec = tasks[task_name]

    logs_dir = project_dir / "work" / "logs"
    log_path = next_version_path(logs_dir, f"{task_name}_run", ".jsonl")
    run_name = log_path.stem  # e.g. hello_run_v003
    events = JsonlLogger(log_path)

    outputs_dir = project_dir / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    before = _snapshot(outputs_dir)

    mapping = _placeholders(project_dir)
    cwd = Path(spec.cwd) if spec.cwd else project_dir
    env = dict(os.environ)
    if extra_env:
        env.update(extra_env)

    result = RunResult(
        project=project, task=task_name, run_name=run_name,
        status="failed", duration_s=0.0, log_path=log_path,
    )
    events.event("task_start", project=project, task=task_name, run=run_name,
                 steps=len(spec.cmds), timeout_s=spec.timeout)
    started = time.monotonic()
    failure: Optional[str] = None

    for index, raw_cmd in enumerate(spec.cmds, start=1):
        cmd = _expand(raw_cmd, mapping)
        argv = shlex.split(cmd, posix=(os.name != "nt"))
        events.event("step_start", step=index, cmd=cmd)
        step_started = time.monotonic()
        try:
            proc = run(argv, cwd=str(cwd), env=env, capture_output=True,
                       text=True, timeout=spec.timeout, check=False)
            rc, out, err = proc.returncode, proc.stdout or "", proc.stderr or ""
        except subprocess.TimeoutExpired:
            rc, out, err = -1, "", f"timed out after {spec.timeout}s"
        except (OSError, subprocess.SubprocessError) as exc:
            rc, out, err = -1, "", f"failed to start: {exc}"
        duration = time.monotonic() - step_started
        step = StepResult(cmd=cmd, returncode=rc, duration_s=round(duration, 3),
                          stdout_tail=out[-_TAIL:], stderr_tail=err[-_TAIL:])
        result.steps.append(step)
        events.event("step_end", step=index, cmd=cmd, returncode=rc,
                     duration_s=step.duration_s,
                     stdout_tail=step.stdout_tail, stderr_tail=step.stderr_tail)
        if rc != 0:
            failure = f"step {index} exited {rc}: {cmd}"
            break

    result.duration_s = round(time.monotonic() - started, 3)

    if failure is None:
        result.status = "success"
        result.output_path = versioned_write_json(
            outputs_dir, f"{task_name}_result",
            {
                "project": project,
                "task": task_name,
                "run": run_name,
                "finished_at": utc_now_iso(),
                "status": "success",
                "duration_s": result.duration_s,
                "steps": [
                    {"cmd": s.cmd, "returncode": s.returncode,
                     "duration_s": s.duration_s, "stdout_tail": s.stdout_tail}
                    for s in result.steps
                ],
            },
        )
    else:
        rollback_dir = project_dir / "work" / "rollback" / run_name
        moved = _rollback(outputs_dir, before, rollback_dir, events)
        result.rollback_dir = rollback_dir if moved else None

    events.event("task_end", status=result.status, duration_s=result.duration_s,
                 error=failure, output=str(result.output_path) if result.output_path else None)
    _update_status(project_dir, {
        "task": f"{project}.{task_name}",
        "run": run_name,
        "status": result.status,
        "finished_at": utc_now_iso(),
        "duration_s": result.duration_s,
        "log": str(result.log_path),
        "output": str(result.output_path) if result.output_path else None,
        "error": failure,
    })

    if failure is not None:
        raise TaskFailed(
            f"{project}.{task_name} failed ({failure}); "
            f"log: {log_path}"
            + (f"; new outputs rolled back to {result.rollback_dir}" if result.rollback_dir else "")
        )
    log.info("%s.%s succeeded in %.3fs -> %s", project, task_name,
             result.duration_s, result.output_path)
    return result
