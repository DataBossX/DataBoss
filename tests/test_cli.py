"""Tests for the scriptable ``databossx`` command-line interface.

These exercise the CLI dispatch end to end against a temporary project root so no
real artifacts are written and no real source data is touched.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from databossx import __version__, cli
from databossx.core import paths


@pytest.fixture()
def sandbox(tmp_path: Path, monkeypatch) -> Path:
    """Redirect every artifact directory into a temp root."""
    monkeypatch.setattr(paths, "ROOT", tmp_path)
    monkeypatch.setattr(paths, "REPORTS", tmp_path / "reports")
    monkeypatch.setattr(paths, "LOGS", tmp_path / "logs")
    monkeypatch.setattr(paths, "BACKUPS", tmp_path / "backups")
    monkeypatch.setattr(paths, "DIAGNOSTICS", tmp_path / "diagnostics")
    monkeypatch.setattr(paths, "ROLLBACK", tmp_path / "rollback")
    monkeypatch.setattr(paths, "MEMORY", tmp_path / "memory")
    monkeypatch.setattr(paths, "REVIEW_OUTPUTS", tmp_path / "review_outputs")
    monkeypatch.setattr(
        paths, "ALL_ARTIFACT_DIRS",
        (paths.REPORTS, paths.LOGS, paths.BACKUPS, paths.DIAGNOSTICS,
         paths.ROLLBACK, paths.MEMORY, paths.REVIEW_OUTPUTS),
    )
    paths.ensure_dirs()
    return tmp_path


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_no_command_errors(capsys):
    # argparse requires a subcommand and exits non-zero.
    with pytest.raises(SystemExit) as exc:
        cli.main([])
    assert exc.value.code != 0


def test_build_parser_registers_all_commands():
    parser = cli.build_parser()
    sub = next(a for a in parser._actions if hasattr(a, "choices") and a.choices)
    expected = {
        "health", "backup", "scan", "map", "mock-workbook", "inspect",
        "review", "fingerprint", "preflight", "diagnostics", "first-task", "menu",
    }
    assert expected <= set(sub.choices)


def test_health_command(sandbox, capsys):
    code = cli.main(["health"])
    assert code == 0
    out = capsys.readouterr().out
    assert "health_report" in out


def test_scan_json_output_is_parseable(sandbox, capsys):
    code = cli.main(["--json", "scan"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert "tracked_findings" in payload
    assert payload["tracked_findings"] == 0


def test_scan_fail_on_tracked_flags_committed_secret(sandbox, monkeypatch, capsys):
    # A tracked secret must make `scan --fail-on-tracked` exit non-zero.
    (sandbox / ".env").write_text(
        "OPENAI_API_KEY=sk-abcdef0123456789ABCDEF0123456789ABCDEF\n"  # pragma: allowlist secret
    )
    monkeypatch.setattr(
        cli.secret_scan, "_git_tracked_files", lambda root: {".env"}
    )
    code = cli.main(["scan", "--fail-on-tracked"])
    assert code == 1
    payload = capsys.readouterr().out
    assert "tracked_findings" in payload


def test_scan_without_flag_is_green_even_with_secret(sandbox, monkeypatch):
    (sandbox / ".env").write_text(
        "OPENAI_API_KEY=sk-abcdef0123456789ABCDEF0123456789ABCDEF\n"  # pragma: allowlist secret
    )
    monkeypatch.setattr(
        cli.secret_scan, "_git_tracked_files", lambda root: {".env"}
    )
    assert cli.main(["scan"]) == 0


def test_mock_workbook_and_fingerprint(sandbox, capsys):
    out = sandbox / "wb.xlsx"
    assert cli.main(["mock-workbook", "-o", str(out)]) == 0
    capsys.readouterr()
    assert out.exists()

    assert cli.main(["--json", "fingerprint", str(out)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert len(payload["sha256"]) == 64
    assert payload["size"] > 0


def test_inspect_missing_file_returns_clean_error(sandbox, capsys):
    code = cli.main(["inspect", str(sandbox / "nope.xlsx")])
    assert code in (1, 2)
    err = capsys.readouterr().err
    assert "error" in err.lower()
