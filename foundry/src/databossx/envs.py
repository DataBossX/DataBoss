"""``databossx env <project>`` — isolated virtualenvs with lockfiles.

Creates ``<project>/.venv`` (via ``uv`` when available, else ``python -m venv``),
installs the project's ``requirements.txt`` when present, and writes a lockfile.
Idempotent: a healthy venv is left alone; a broken venv is *moved* to the
project trash (never deleted — Zero-Destruction law) and rebuilt.

Lockfiles are versioned (``work/locks/requirements_vNNN.lock``) and the stable
pointer ``requirements.lock`` in the project root always mirrors the latest.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

from .errors import EnvError, ProjectNotFound
from .config import FoundryConfig
from .versioned import next_version_path

log = logging.getLogger("databossx.env")

Runner = Callable[..., subprocess.CompletedProcess]


@dataclass
class EnvReport:
    project: str
    venv_dir: Path
    python_path: Path
    created: bool = False
    repaired: bool = False
    requirements_installed: bool = False
    lockfile: Optional[Path] = None
    used_uv: bool = False
    log_lines: List[str] = field(default_factory=list)


def resolve_project_dir(config: FoundryConfig, project: str) -> Path:
    """A project name under ``projects/`` or an explicit existing path."""
    named = config.projects_dir / project
    if named.is_dir():
        return named
    explicit = Path(project).expanduser()
    if explicit.is_dir():
        return explicit
    raise ProjectNotFound(
        f"project {project!r} not found (looked in {named} and {explicit}); "
        f"create it with: databossx new {project}"
    )


def venv_python(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def is_healthy(venv_dir: Path, run: Runner = subprocess.run) -> bool:
    py = venv_python(venv_dir)
    if not py.exists():
        return False
    try:
        proc = run([str(py), "-c", "import sys; print(sys.prefix)"],
                   capture_output=True, text=True, timeout=60, check=False)
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0


def _quarantine_broken_venv(project_dir: Path, venv_dir: Path) -> Path:
    """Move (never delete) a broken venv into the project trash."""
    trash_root = project_dir / "work" / "trash"
    trash_root.mkdir(parents=True, exist_ok=True)
    target = next_version_path(trash_root, "venv_broken", "")
    # next_version_path names files; for a directory move the bare name is fine.
    shutil.move(str(venv_dir), str(target))
    return target


def _run_or_raise(cmd: List[str], run: Runner, what: str) -> subprocess.CompletedProcess:
    log.info("%s: %s", what, " ".join(cmd))
    try:
        proc = run(cmd, capture_output=True, text=True, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        raise EnvError(f"{what} failed to start: {exc}") from exc
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip()[-2000:]
        raise EnvError(f"{what} exited {proc.returncode}: {tail}")
    return proc


def ensure_env(
    config: FoundryConfig,
    project: str,
    run: Runner = subprocess.run,
    which: Callable[[str], Optional[str]] = shutil.which,
) -> EnvReport:
    project_dir = resolve_project_dir(config, project)
    venv_dir = project_dir / ".venv"
    uv = which("uv")
    report = EnvReport(
        project=project, venv_dir=venv_dir,
        python_path=venv_python(venv_dir), used_uv=bool(uv),
    )

    if venv_dir.exists():
        if is_healthy(venv_dir, run=run):
            report.log_lines.append(f"venv healthy: {venv_dir}")
        else:
            moved = _quarantine_broken_venv(project_dir, venv_dir)
            report.repaired = True
            report.log_lines.append(f"broken venv moved to {moved}")

    if not venv_dir.exists():
        if uv:
            _run_or_raise([uv, "venv", str(venv_dir)], run, "uv venv")
        else:
            _run_or_raise([sys.executable, "-m", "venv", str(venv_dir)], run, "python -m venv")
        report.created = True
        report.log_lines.append(f"venv created: {venv_dir}")

    py = venv_python(venv_dir)
    requirements = project_dir / "requirements.txt"
    if requirements.is_file():
        if uv:
            _run_or_raise(
                [uv, "pip", "install", "--python", str(py), "-r", str(requirements)],
                run, "uv pip install",
            )
        else:
            _run_or_raise(
                [str(py), "-m", "pip", "install", "-r", str(requirements)],
                run, "pip install",
            )
        report.requirements_installed = True
        report.log_lines.append(f"installed {requirements}")

    # Lockfile: versioned history + stable pointer.
    if uv:
        freeze = _run_or_raise([uv, "pip", "freeze", "--python", str(py)], run, "uv pip freeze")
    else:
        freeze = _run_or_raise([str(py), "-m", "pip", "freeze"], run, "pip freeze")
    locks_dir = project_dir / "work" / "locks"
    locks_dir.mkdir(parents=True, exist_ok=True)
    lock_path = next_version_path(locks_dir, "requirements", ".lock")
    lock_path.write_text(freeze.stdout or "", encoding="utf-8")
    pointer = project_dir / "requirements.lock"
    pointer.write_text(freeze.stdout or "", encoding="utf-8")
    report.lockfile = lock_path
    report.log_lines.append(f"lockfile written: {lock_path}")
    return report
