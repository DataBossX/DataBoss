"""Shared test fixtures: isolated settings, DB, audit logger, and workbooks."""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from config.settings import Settings, load_settings  # noqa: E402
from db.audit_logger import AuditLogger  # noqa: E402
from db.db_client import DatabaseManager  # noqa: E402
from tests.fixtures.make_workbook import (  # noqa: E402
    build_missing_vesting_workbook,
    build_overconveyance_workbook,
    build_valid_workbook,
)


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    s = load_settings()
    root = tmp_path / "dbx_root"
    root.mkdir(parents=True, exist_ok=True)
    object.__setattr__(s, "databossx_root", root)
    object.__setattr__(s, "outputs_dir", tmp_path / "outputs")
    object.__setattr__(s, "db_path", tmp_path / "db" / "test.sqlite3")
    object.__setattr__(s, "extra_source_dirs", [])
    (tmp_path / "outputs").mkdir(parents=True, exist_ok=True)
    return s


@pytest.fixture()
def db(settings: Settings) -> DatabaseManager:
    manager = DatabaseManager(settings.db_path)
    manager.initialize_schema()
    yield manager
    manager.close()


@pytest.fixture()
def audit(db: DatabaseManager) -> AuditLogger:
    return AuditLogger(db)


@pytest.fixture()
def valid_workbook(tmp_path: Path) -> Path:
    return build_valid_workbook(tmp_path / "valid.xlsx")


@pytest.fixture()
def overconveyance_workbook(tmp_path: Path) -> Path:
    return build_overconveyance_workbook(tmp_path / "overconvey.xlsx")


@pytest.fixture()
def missing_vesting_workbook(tmp_path: Path) -> Path:
    return build_missing_vesting_workbook(tmp_path / "missing_vesting.xlsx")
