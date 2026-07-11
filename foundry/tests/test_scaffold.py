from __future__ import annotations

import json
from pathlib import Path

import pytest

from databossx.errors import FoundryError
from databossx.planfile import parse_plan_file
from databossx.scaffold import SUBDIRS, scaffold_project, validate_name


def test_scaffold_creates_everything(config):
    report = scaffold_project(config, "demo")
    d = report.project_dir
    assert d == config.projects_dir / "demo"
    for sub in SUBDIRS:
        assert (d / sub).is_dir()
        assert (d / sub / ".gitkeep").is_file()
    project = json.loads((d / "PROJECT.json").read_text(encoding="utf-8"))
    assert project["name"] == "demo"
    status = json.loads((d / "STATUS.json").read_text(encoding="utf-8"))
    assert status["status"] == "new"
    assert (d / "TODO.md").is_file()
    tasks = parse_plan_file(d / "PLAN.md")
    assert "hello" in tasks  # generated plan is immediately runnable


def test_scaffold_is_idempotent_and_never_overwrites(config):
    first = scaffold_project(config, "demo")
    marker = first.project_dir / "PLAN.md"
    marker.write_text("# customized by human\n\n## Tasks\n\n### hello\n- cmd: x\n",
                      encoding="utf-8")
    second = scaffold_project(config, "demo")
    assert "PLAN.md" in second.skipped_existing
    assert "customized by human" in marker.read_text(encoding="utf-8")
    assert not second.created  # nothing recreated


def test_scaffold_fills_in_missing_pieces_only(config):
    report = scaffold_project(config, "demo")
    (report.project_dir / "TODO.md").unlink()
    repaired = scaffold_project(config, "demo")
    assert repaired.created == ["TODO.md"]


@pytest.mark.parametrize("bad", ["", "Demo", "has space", "dot.name", "-lead", "UPPER"])
def test_invalid_names_rejected(bad):
    with pytest.raises(FoundryError):
        validate_name(bad)


def test_valid_names_accepted():
    for good in ("demo", "demo-2", "roger_mills", "a1"):
        assert validate_name(good) == good
