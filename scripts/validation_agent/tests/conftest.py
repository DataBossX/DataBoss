"""Shared pytest fixtures. All workbook data here is SYNTHETIC test data."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from config.settings import load_settings          # noqa: E402
from db.db_client import DatabaseManager            # noqa: E402
from tests.fixtures.build import build_workbook, build_workbook_with_media  # noqa: E402


@pytest.fixture()
def tmp_agent(tmp_path):
    settings = load_settings()
    settings.agent_root = tmp_path
    settings.ensure_dirs()
    return settings


@pytest.fixture()
def db(tmp_agent):
    return DatabaseManager(tmp_agent.db_path)


@pytest.fixture()
def sample_wb(tmp_path):
    return str(build_workbook(tmp_path / "fixture_wb.xlsx"))


@pytest.fixture()
def sample_wb_media(tmp_path):
    src = build_workbook(tmp_path / "fixture_src.xlsx")
    return str(build_workbook_with_media(src, tmp_path / "fixture_media.xlsx"))
