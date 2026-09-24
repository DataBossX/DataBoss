from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

import databossx


REPO_ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_ROOTS = (
    REPO_ROOT / "src" / "databossx",
    REPO_ROOT / "horizon",
    REPO_ROOT / "backend",
    REPO_ROOT / "frontend",
    REPO_ROOT / "website",
    REPO_ROOT / "grocery_report_pipeline.py",
)


def _iter_python_files(root: Path):
    if root.is_file():
        yield root
        return
    for path in root.rglob("*.py"):
        yield path


def test_production_package_does_not_export_rd():
    assert "databossx_rd" not in databossx.__all__
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    script = (
        "import databossx, sys; "
        "assert 'databossx_rd' not in databossx.__all__; "
        "assert not any(name == 'databossx_rd' or name.startswith('databossx_rd.') "
        "for name in sys.modules)"
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(REPO_ROOT),
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


def test_production_paths_do_not_import_rd():
    offenders = []
    for root in PRODUCTION_ROOTS:
        if not root.exists():
            continue
        for path in _iter_python_files(root):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name == "databossx_rd" or alias.name.startswith("databossx_rd."):
                            offenders.append(str(path))
                if isinstance(node, ast.ImportFrom) and node.module:
                    if node.module == "databossx_rd" or node.module.startswith("databossx_rd."):
                        offenders.append(str(path))
    assert not offenders, f"production path imported R&D package: {offenders}"


def test_rd_package_is_not_an_orchestrator():
    text = (REPO_ROOT / "src" / "databossx_rd" / "__init__.py").read_text(encoding="utf-8")
    assert "not an orchestrator" in text
    assert "no write authority" in text
