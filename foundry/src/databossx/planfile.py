"""Parser for the ``## Tasks`` section of a project's PLAN.md.

Format (human-editable markdown):

    ## Tasks

    ### hello
    - desc: smoke task
    - cmd: {python} -c "print('hi')"
    - cmd: {python} -c "print('second step')"
    - timeout: 60

Multiple ``- cmd:`` bullets run sequentially as steps of one task. Parsing is
strict: unknown bullets, tasks without commands, duplicate task names and
non-numeric timeouts are all reported with line numbers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .errors import PlanError

_TASK_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_\-]*$")
_BULLET_RE = re.compile(r"^-\s+(\w+):\s*(.*)$")

KNOWN_KEYS = {"cmd", "timeout", "desc", "cwd"}
DEFAULT_TIMEOUT = 600.0


@dataclass
class TaskSpec:
    name: str
    cmds: Tuple[str, ...]
    timeout: float = DEFAULT_TIMEOUT
    desc: str = ""
    cwd: Optional[str] = None


@dataclass
class _Draft:
    name: str
    line: int
    cmds: List[str] = field(default_factory=list)
    timeout: float = DEFAULT_TIMEOUT
    desc: str = ""
    cwd: Optional[str] = None


def parse_plan_text(text: str, source: str = "PLAN.md") -> Dict[str, TaskSpec]:
    lines = text.splitlines()
    errors: List[str] = []
    tasks: Dict[str, TaskSpec] = {}

    in_tasks_section = False
    draft: Optional[_Draft] = None

    def finish(d: Optional[_Draft]) -> None:
        if d is None:
            return
        if not d.cmds:
            errors.append(f"{source}:{d.line}: task '{d.name}' declares no '- cmd:' step")
            return
        tasks[d.name] = TaskSpec(
            name=d.name, cmds=tuple(d.cmds), timeout=d.timeout, desc=d.desc, cwd=d.cwd,
        )

    for no, raw in enumerate(lines, start=1):
        line = raw.rstrip()
        stripped = line.strip()
        if stripped.startswith("## ") and not stripped.startswith("###"):
            finish(draft)
            draft = None
            in_tasks_section = stripped[3:].strip().lower() == "tasks"
            continue
        if not in_tasks_section:
            continue
        if stripped.startswith("### "):
            finish(draft)
            name = stripped[4:].strip()
            if not _TASK_NAME_RE.match(name):
                errors.append(f"{source}:{no}: invalid task name {name!r}")
                draft = None
                continue
            if name in tasks:
                errors.append(f"{source}:{no}: duplicate task name {name!r}")
                draft = None
                continue
            draft = _Draft(name=name, line=no)
            continue
        m = _BULLET_RE.match(stripped)
        if not m:
            continue  # prose between bullets is allowed
        if draft is None:
            errors.append(f"{source}:{no}: bullet outside of a '### task' section")
            continue
        key, value = m.group(1).lower(), m.group(2).strip()
        if key not in KNOWN_KEYS:
            errors.append(f"{source}:{no}: unknown key '{key}' (known: {sorted(KNOWN_KEYS)})")
        elif key == "cmd":
            if not value:
                errors.append(f"{source}:{no}: empty '- cmd:'")
            else:
                draft.cmds.append(value)
        elif key == "timeout":
            try:
                draft.timeout = float(value)
                if draft.timeout <= 0:
                    raise ValueError
            except ValueError:
                errors.append(f"{source}:{no}: timeout must be a positive number, got {value!r}")
        elif key == "desc":
            draft.desc = value
        elif key == "cwd":
            draft.cwd = value
    finish(draft)

    if errors:
        raise PlanError("invalid plan:\n  " + "\n  ".join(errors))
    if not tasks:
        raise PlanError(f"{source}: no tasks declared under a '## Tasks' heading")
    return tasks


def parse_plan_file(path: Path) -> Dict[str, TaskSpec]:
    path = Path(path)
    if not path.is_file():
        raise PlanError(f"plan file not found: {path}")
    return parse_plan_text(path.read_text(encoding="utf-8"), source=str(path))
