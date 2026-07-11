from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from databossx.envs import ensure_env, is_healthy, resolve_project_dir, venv_python
from databossx.errors import EnvError, ProjectNotFound
from databossx.scaffold import scaffold_project


class FakeRun:
    """Records commands; simulates venv creation and pip output."""

    def __init__(self, freeze_output="pkg==1.0\n", fail_on=None):
        self.calls = []
        self.freeze_output = freeze_output
        self.fail_on = fail_on or ()

    def __call__(self, argv, **kwargs):
        self.calls.append(list(argv))
        joined = " ".join(str(a) for a in argv)
        if any(marker in joined for marker in self.fail_on):
            return subprocess.CompletedProcess(argv, 1, stdout="", stderr="simulated failure")
        if "-m venv" in joined or (argv[0].endswith("uv") and argv[1] == "venv"):
            venv_dir = Path(argv[-1])
            py = venv_python(venv_dir)
            py.parent.mkdir(parents=True, exist_ok=True)
            py.touch()
        stdout = self.freeze_output if "freeze" in joined else ""
        return subprocess.CompletedProcess(argv, 0, stdout=stdout, stderr="")


def test_resolve_project_by_name_and_path(config):
    scaffold_project(config, "demo")
    assert resolve_project_dir(config, "demo") == config.projects_dir / "demo"
    assert resolve_project_dir(config, str(config.projects_dir / "demo")).name == "demo"
    with pytest.raises(ProjectNotFound, match="databossx new"):
        resolve_project_dir(config, "ghost")


def test_creates_venv_and_lockfile(config):
    scaffold_project(config, "demo")
    fake = FakeRun()
    report = ensure_env(config, "demo", run=fake, which=lambda n: None)
    assert report.created and not report.repaired
    assert not report.used_uv
    project_dir = config.projects_dir / "demo"
    assert report.lockfile == project_dir / "work" / "locks" / "requirements_v001.lock"
    assert report.lockfile.read_text(encoding="utf-8") == "pkg==1.0\n"
    assert (project_dir / "requirements.lock").read_text(encoding="utf-8") == "pkg==1.0\n"


def test_prefers_uv_when_available(config):
    scaffold_project(config, "demo")
    fake = FakeRun()
    report = ensure_env(config, "demo", run=fake, which=lambda n: "/usr/bin/uv")
    assert report.used_uv
    assert fake.calls[0][:2] == ["/usr/bin/uv", "venv"]
    assert ["/usr/bin/uv", "pip", "freeze"] == fake.calls[-1][:3]


def test_healthy_venv_left_alone_and_lock_versions_accumulate(config):
    scaffold_project(config, "demo")
    fake = FakeRun()
    ensure_env(config, "demo", run=fake, which=lambda n: None)
    second = ensure_env(config, "demo", run=fake, which=lambda n: None)
    assert not second.created and not second.repaired
    assert second.lockfile.name == "requirements_v002.lock"


def test_broken_venv_quarantined_not_deleted(config):
    scaffold_project(config, "demo")
    project_dir = config.projects_dir / "demo"
    venv_dir = project_dir / ".venv"
    venv_dir.mkdir()
    (venv_dir / "junk.txt").write_text("broken venv contents")
    fake = FakeRun()
    report = ensure_env(config, "demo", run=fake, which=lambda n: None)
    assert report.repaired and report.created
    quarantined = project_dir / "work" / "trash" / "venv_broken_v001"
    assert (quarantined / "junk.txt").read_text() == "broken venv contents"


def test_requirements_installed_when_present(config):
    scaffold_project(config, "demo")
    (config.projects_dir / "demo" / "requirements.txt").write_text("requests\n")
    fake = FakeRun()
    report = ensure_env(config, "demo", run=fake, which=lambda n: None)
    assert report.requirements_installed
    assert any("pip" in " ".join(c) and "install" in c for c in fake.calls)


def test_create_failure_raises_enverror(config):
    scaffold_project(config, "demo")
    fake = FakeRun(fail_on=("-m venv",))
    with pytest.raises(EnvError, match="python -m venv"):
        ensure_env(config, "demo", run=fake, which=lambda n: None)


def test_is_healthy_false_when_python_missing(tmp_path: Path):
    assert not is_healthy(tmp_path / "novenv")


def test_is_healthy_real_interpreter(config, python_exe):
    # Integration: a real venv-shaped dir using the current interpreter.
    scaffold_project(config, "demo")
    venv_dir = config.projects_dir / "demo" / ".venv"
    py = venv_python(venv_dir)
    py.parent.mkdir(parents=True)
    try:
        py.symlink_to(python_exe)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")
    assert is_healthy(venv_dir)
