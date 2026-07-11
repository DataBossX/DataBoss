"""``databossx new <project>`` — project scaffolding.

Creates ``projects/<name>/`` with PROJECT.json, STATUS.json, TODO.md, PLAN.md
and the working folders ``inbox`` ``work`` ``outputs`` ``proofs``.

Idempotent and non-destructive: existing files are NEVER overwritten — missing
pieces are filled in, everything already present is left untouched.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from . import __version__
from .config import FoundryConfig
from .errors import FoundryError

log = logging.getLogger("databossx.scaffold")

_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_\-]*$")

SUBDIRS = ("inbox", "work", "outputs", "proofs")

PLAN_TEMPLATE = """\
# PLAN — {name}

Tasks are declared under the `## Tasks` heading. Each `### <task>` section is
one runnable unit for `databossx run {name}.<task>`. Recognized bullets:

- `- cmd:` shell-free command line (repeat for sequential steps). Placeholders:
  `{{python}}` (project venv python if present, else the Foundry python),
  `{{project_dir}}`, `{{inbox}}`, `{{work}}`, `{{outputs}}`, `{{proofs}}`.
- `- timeout:` seconds per step (default 600).
- `- desc:` one-line description.

## Tasks

### hello
- desc: smoke task proving the runner works end to end
- cmd: {{python}} -c "print('hello from {name}')"
- timeout: 60
"""

TODO_TEMPLATE = """\
# TODO — {name}

- [ ] Drop source material into `inbox/`
- [ ] Flesh out `PLAN.md` tasks
- [ ] Run `databossx run {name}.hello` to verify the pipeline
"""


@dataclass
class ScaffoldReport:
    project: str
    project_dir: Path
    created: List[str] = field(default_factory=list)
    skipped_existing: List[str] = field(default_factory=list)


def validate_name(name: str) -> str:
    if not _NAME_RE.match(name or ""):
        raise FoundryError(
            f"invalid project name {name!r}: use lowercase letters, digits, '-', '_' "
            "(no dots — the runner uses '.' to separate project from task)"
        )
    return name


def _write_if_absent(report: ScaffoldReport, path: Path, content: str) -> None:
    rel = path.name
    if path.exists():
        report.skipped_existing.append(rel)
        return
    path.write_text(content, encoding="utf-8")
    report.created.append(rel)


def scaffold_project(config: FoundryConfig, name: str) -> ScaffoldReport:
    validate_name(name)
    project_dir = config.projects_dir / name
    report = ScaffoldReport(project=name, project_dir=project_dir)

    project_dir.mkdir(parents=True, exist_ok=True)
    for sub in SUBDIRS:
        d = project_dir / sub
        if not d.exists():
            d.mkdir()
            (d / ".gitkeep").touch()
            report.created.append(sub + "/")
        else:
            report.skipped_existing.append(sub + "/")

    now = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
    _write_if_absent(
        report, project_dir / "PROJECT.json",
        json.dumps(
            {
                "name": name,
                "created_utc": now,
                "foundry_version": __version__,
                "description": "",
            },
            indent=2,
        ) + "\n",
    )
    _write_if_absent(
        report, project_dir / "STATUS.json",
        json.dumps({"status": "new", "last_run": None, "history": []}, indent=2) + "\n",
    )
    _write_if_absent(report, project_dir / "TODO.md", TODO_TEMPLATE.format(name=name))
    _write_if_absent(report, project_dir / "PLAN.md", PLAN_TEMPLATE.format(name=name))

    log.info(
        "scaffold %s: %d created, %d already present",
        name, len(report.created), len(report.skipped_existing),
    )
    return report
