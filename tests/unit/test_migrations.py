"""Tests for databossx.db.migrations.MigrationRunner."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from databossx.db.migrations import MigrationRunner

REPO_MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"


@pytest.fixture()
def db_path(tmp_path):
    return tmp_path / "test.db"


def test_run_applies_real_migrations(db_path):
    runner = MigrationRunner(db_path, REPO_MIGRATIONS_DIR)
    applied = runner.run()
    assert applied >= 1
    assert runner.current_version() >= 1


def test_current_version_zero_before_run(db_path):
    runner = MigrationRunner(db_path, REPO_MIGRATIONS_DIR)
    assert runner.current_version() == 0


def test_run_is_idempotent(db_path):
    runner = MigrationRunner(db_path, REPO_MIGRATIONS_DIR)
    first = runner.run()
    second = runner.run()
    assert first >= 1
    assert second == 0
    assert runner.current_version() == first


def test_status_reports_all_migrations(db_path):
    runner = MigrationRunner(db_path, REPO_MIGRATIONS_DIR)
    runner.run()
    statuses = runner.status()
    assert len(statuses) >= 1
    for entry in statuses:
        assert "number" in entry
        assert "name" in entry
        assert entry["applied_at"] is not None


def test_expected_tables_created(db_path):
    runner = MigrationRunner(db_path, REPO_MIGRATIONS_DIR)
    runner.run()
    conn = sqlite3.connect(db_path)
    try:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')"
            ).fetchall()
        }
    finally:
        conn.close()
    expected = {
        "projects",
        "source_connections",
        "source_snapshots",
        "assets",
        "asset_versions",
        "derived_artifacts",
        "evidence_spans",
        "claims",
        "claim_supports",
        "conflicts",
        "workflow_definitions",
        "runs",
        "tasks",
        "task_dependencies",
        "task_attempts",
        "task_leases",
        "worker_capabilities",
        "review_gates",
        "review_decisions",
        "approvals",
        "artifact_versions",
        "model_route_decisions",
        "tool_definitions",
        "tool_runs",
        "audit_events",
        "title_projects",
        "jurisdictions",
        "tracts",
        "instruments",
        "instrument_parties",
        "recording_references",
        "chain_links",
        "interest_ledger_entries",
        "title_exceptions",
        "curative_items",
        "workbook_candidates",
        "schema_migrations",
    }
    assert expected.issubset(tables)


def test_multi_migration_directory_applied_in_order(tmp_path):
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()
    (migrations_dir / "001_first.sql").write_text(
        "CREATE TABLE first_table (id INTEGER PRIMARY KEY);"
    )
    (migrations_dir / "002_second.sql").write_text(
        "CREATE TABLE second_table (id INTEGER PRIMARY KEY);"
    )

    db_path = tmp_path / "multi.db"
    runner = MigrationRunner(db_path, migrations_dir)
    applied = runner.run()
    assert applied == 2
    assert runner.current_version() == 2

    conn = sqlite3.connect(db_path)
    try:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
    finally:
        conn.close()
    assert "first_table" in tables
    assert "second_table" in tables


def test_failed_migration_rolls_back(tmp_path):
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()
    (migrations_dir / "001_bad.sql").write_text(
        "CREATE TABLE ok_table (id INTEGER PRIMARY KEY);\n"
        "SELECT * FROM this_table_does_not_exist;"
    )

    db_path = tmp_path / "bad.db"
    runner = MigrationRunner(db_path, migrations_dir)
    with pytest.raises(sqlite3.OperationalError):
        runner.run()

    # Migration must not be recorded as applied, and the partial DDL from
    # the failed migration must have been rolled back.
    assert runner.current_version() == 0
    conn = sqlite3.connect(db_path)
    try:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
    finally:
        conn.close()
    assert "ok_table" not in tables
