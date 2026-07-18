"""Tests for the project registry and root resolution."""

import os
from pathlib import Path

import pytest

from databossx.projects import (
    all_projects,
    get_project,
    golden_demo_root,
    resolve_root,
)
from databossx.selfcheck import run_doctor


def test_named_projects_registered():
    keys = {p.key for p in all_projects()}
    for expected in ("horizon", "penterra", "roger_mills", "beckham", "ryder",
                     "golden_demo"):
        assert expected in keys


def test_lookup_by_name_and_key():
    assert get_project("horizon").name == "Horizon"
    assert get_project("Beckham County").key == "beckham"
    assert get_project("Roger Mills").key == "roger_mills"
    assert get_project("nope") is None


def test_explicit_override_wins(tmp_path):
    root = resolve_root("horizon", override=str(tmp_path))
    assert root == Path(tmp_path)


def test_env_var_resolution(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABOSSX_PENTERRA_ROOT", str(tmp_path / "pent"))
    assert resolve_root("penterra") == tmp_path / "pent"


def test_base_env_composes_with_folder(monkeypatch, tmp_path):
    monkeypatch.delenv("DATABOSSX_RYDER_ROOT", raising=False)
    monkeypatch.setenv("DATABOSSX_ROOT", str(tmp_path))
    got = resolve_root("ryder")
    assert got == tmp_path / "Ryder"


def test_golden_demo_resolves_into_repo_by_default(monkeypatch):
    monkeypatch.delenv("DATABOSSX_GOLDEN_DEMO_ROOT", raising=False)
    assert resolve_root("golden_demo") == golden_demo_root()


def test_unknown_project_returns_none():
    assert resolve_root("does-not-exist") is None


def test_doctor_passes_in_this_env():
    report = run_doctor()
    # Core engines must be healthy; PDF may WARN if reportlab is absent, but
    # nothing should FAIL in a correctly set-up environment.
    assert report.ok, [(_c.name, _c.status, _c.detail)
                       for _c in report.checks if _c.status == "FAIL"]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
