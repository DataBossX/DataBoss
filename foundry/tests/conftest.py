"""Shared fixtures: every test runs against an isolated tmp root."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from databossx.config import FoundryConfig

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def config(tmp_path: Path) -> FoundryConfig:
    """A FoundryConfig rooted in an isolated temp directory."""
    return FoundryConfig(
        root=tmp_path,
        discover_roots=(tmp_path / "Horizon", tmp_path / "Penterra"),
    )


@pytest.fixture()
def repo_config(tmp_path: Path) -> FoundryConfig:
    """A config whose plugins dir is the real repo /plugins (for absorb tests)."""
    return FoundryConfig(
        root=tmp_path,
        discover_roots=(tmp_path / "Horizon",),
    )


@pytest.fixture()
def real_plugins_dir() -> Path:
    return REPO_ROOT / "plugins"


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Keep the CLI's load_config() away from the developer's real env."""
    monkeypatch.setenv("DATABOSSX_ROOT", str(tmp_path))
    monkeypatch.delenv("DATABOSSX_DISCOVER_ROOTS", raising=False)
    yield


@pytest.fixture()
def python_exe() -> str:
    return sys.executable
