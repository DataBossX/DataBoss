from __future__ import annotations

from pathlib import Path

import pytest

from databossx.errors import PlanError
from databossx.planfile import DEFAULT_TIMEOUT, parse_plan_file, parse_plan_text

GOOD_PLAN = """\
# PLAN — demo

Prose before the tasks section is ignored.

## Notes

- cmd: this bullet is outside ## Tasks and must be ignored

## Tasks

### hello
- desc: say hi
- cmd: python -c "print('hi')"
- timeout: 60

### two-step
Some prose inside a task is fine.
- cmd: python -c "print('a')"
- cmd: python -c "print('b')"
- cwd: work
"""


def test_parses_tasks_and_steps():
    tasks = parse_plan_text(GOOD_PLAN)
    assert set(tasks) == {"hello", "two-step"}
    assert tasks["hello"].timeout == 60.0
    assert tasks["hello"].desc == "say hi"
    assert tasks["two-step"].cmds == (
        'python -c "print(\'a\')"',
        'python -c "print(\'b\')"',
    )
    assert tasks["two-step"].cwd == "work"
    assert tasks["two-step"].timeout == DEFAULT_TIMEOUT


@pytest.mark.parametrize(
    "snippet, fragment",
    [
        ("## Tasks\n\n### hello\n- desc: no command\n", "declares no '- cmd:'"),
        ("## Tasks\n\n### Bad Name\n- cmd: x\n", "invalid task name"),
        ("## Tasks\n\n### a\n- cmd: x\n\n### a\n- cmd: y\n", "duplicate task name"),
        ("## Tasks\n\n### a\n- cmd: x\n- timeout: soon\n", "timeout must be"),
        ("## Tasks\n\n### a\n- cmd: x\n- timeout: -5\n", "timeout must be"),
        ("## Tasks\n\n### a\n- cmd: x\n- rocket: launch\n", "unknown key"),
        ("## Tasks\n\n### a\n- cmd:\n", "empty '- cmd:'"),
        ("## Tasks\n\n- cmd: orphan\n", "outside of a '### task'"),
        ("# no tasks heading\n", "no tasks declared"),
    ],
)
def test_bad_plans_rejected_with_line_info(snippet, fragment):
    with pytest.raises(PlanError) as err:
        parse_plan_text(snippet)
    assert fragment in str(err.value)


def test_error_collects_multiple_problems():
    bad = "## Tasks\n\n### a\n- cmd: x\n- timeout: soon\n- rocket: y\n"
    with pytest.raises(PlanError) as err:
        parse_plan_text(bad)
    msg = str(err.value)
    assert "timeout must be" in msg and "unknown key" in msg


def test_missing_file(tmp_path: Path):
    with pytest.raises(PlanError, match="not found"):
        parse_plan_file(tmp_path / "PLAN.md")


def test_file_roundtrip(tmp_path: Path):
    p = tmp_path / "PLAN.md"
    p.write_text(GOOD_PLAN, encoding="utf-8")
    assert "hello" in parse_plan_file(p)
