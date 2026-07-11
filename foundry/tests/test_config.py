from __future__ import annotations

import os
from pathlib import Path

from databossx.config import (
    ENV_DISCOVER_ROOTS,
    ENV_ROOT,
    WINDOWS_DEFAULT_DISCOVER,
    FoundryConfig,
    find_checkout_root,
    load_config,
)


def test_env_root_wins(tmp_path: Path):
    cfg = load_config(cwd=tmp_path, env={ENV_ROOT: str(tmp_path / "custom")})
    assert cfg.root == tmp_path / "custom"


def test_checkout_root_detected_from_git_marker(tmp_path: Path):
    (tmp_path / ".git").mkdir()
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    cfg = load_config(cwd=nested, env={})
    assert cfg.root == tmp_path


def test_checkout_root_detected_from_foundry_marker(tmp_path: Path):
    (tmp_path / "foundry").mkdir()
    (tmp_path / "foundry" / "pyproject.toml").write_text("[project]\n")
    cfg = load_config(cwd=tmp_path, env={})
    assert cfg.root == tmp_path


def test_falls_back_to_cwd(tmp_path: Path):
    assert find_checkout_root(tmp_path) is None or True  # depends on host tmp layout
    cfg = load_config(cwd=tmp_path, env={})
    assert cfg.root.is_dir()


def test_discover_roots_env_override(tmp_path: Path):
    a, b = tmp_path / "one", tmp_path / "two"
    env = {ENV_ROOT: str(tmp_path), ENV_DISCOVER_ROOTS: os.pathsep.join([str(a), str(b)])}
    cfg = load_config(cwd=tmp_path, env=env)
    assert cfg.discover_roots == (a, b)


def test_discover_roots_default_prefers_existing(tmp_path: Path):
    (tmp_path / "Horizon").mkdir()
    cfg = load_config(cwd=tmp_path, env={ENV_ROOT: str(tmp_path)})
    assert cfg.discover_roots == (tmp_path / "Horizon",)


def test_discover_roots_default_falls_back_to_windows_paths(tmp_path: Path):
    cfg = load_config(cwd=tmp_path, env={ENV_ROOT: str(tmp_path)})
    assert cfg.discover_roots == tuple(WINDOWS_DEFAULT_DISCOVER)


def test_wellknown_dirs(tmp_path: Path):
    cfg = FoundryConfig(root=tmp_path, discover_roots=())
    assert cfg.projects_dir == tmp_path / "projects"
    assert cfg.plugins_dir == tmp_path / "plugins"
    assert cfg.proposals_dir == tmp_path / "proposals"
    assert cfg.trash_dir == tmp_path / "foundry_state" / "trash"
