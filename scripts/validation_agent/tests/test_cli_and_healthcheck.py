"""CLI entrypoint and healthcheck behavior."""

from __future__ import annotations

from pathlib import Path

from tests.fixtures.make_workbook import build_certifiable_workbook, materialize_sources


def test_cli_missing_arg_returns_usage_error():
    from core import cli

    assert cli.main(["cli"]) == 2


def test_cli_missing_file_returns_error(tmp_path):
    from core import cli

    assert cli.main(["cli", str(tmp_path / "nope.xlsx")]) == 2


def test_cli_certifies_and_returns_zero(tmp_path, monkeypatch):
    root = tmp_path / "root"
    root.mkdir()
    wb = build_certifiable_workbook(tmp_path / "cli.xlsx", defect="acreage_total")
    docs = materialize_sources(wb, tmp_path / "docs")

    monkeypatch.setenv("DATABOSSX_ROOT", str(root))
    monkeypatch.setenv("DATABOSSX_AGENT_ROOT", str(tmp_path))
    monkeypatch.setenv("DATABOSSX_EXTRA_SOURCE_DIRS", str(docs))

    from core import cli

    rc = cli.main(["cli", str(wb)])
    assert rc == 0
    # run artifacts landed under the isolated agent root
    assert (tmp_path / "outputs").exists()


def test_healthcheck_reports_append_only_pass():
    from tools.healthcheck import run_healthcheck

    checks = run_healthcheck()
    by_name = {name: (ok, detail) for name, ok, detail in checks}
    assert by_name["append_only_manager"][0] is True
    assert by_name["append_only_raw"][0] is True
    assert by_name["db_init"][0] is True
    # secrets are never surfaced in the healthcheck output
    joined = " ".join(f"{n} {d}" for n, _, d in checks)
    assert "password" not in joined.lower() or "REDACTED" in joined or "missing" in joined.lower()


def test_launcher_log_smoke(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABOSSX_AGENT_ROOT", str(tmp_path))
    from core import launcher_log

    assert launcher_log.main() == 0
    # a launcher_events row was appended
    import sqlite3

    db_file = tmp_path / "db" / "databossx_agent.sqlite3"
    assert db_file.exists()
    conn = sqlite3.connect(str(db_file))
    try:
        n = conn.execute("SELECT COUNT(*) FROM launcher_events").fetchone()[0]
    finally:
        conn.close()
    assert n >= 1
