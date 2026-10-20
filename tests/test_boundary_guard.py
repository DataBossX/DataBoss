"""Synthetic checks for the public-boundary guard.

Offending strings are assembled at runtime so this file never carries a
serial, legal reference, or cloud link of its own.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from databossx.boundary_guard import (
    BUILTIN_RULES,
    Config,
    load_config,
    main,
    scan_file,
    scan_text,
)

SERIAL = "WY" + "W-" + "123456"
MLRS = "WY" + "WY" + "123456789"
LEGAL = "-".join(["7", "47N", "76W"])
TR = "T" + "47N" + " R" + "76W"
DRIVE = "https://drive.google.com/" + "file/d/" + "A" * 33 + "/view"
PRIVATE_PATH = "C:" + "\\" + "DataBoss" + "\\" + "Penterra"
HASH = "ab" * 32


def _config(**kwargs) -> Config:
    base = dict(allow_binary_globs=("tests/fixtures/**",), allow_scan_globs=(), ignore_globs=(), extra_rules=())
    base.update(kwargs)
    return Config(**base)


def _codes(findings) -> set[str]:
    return {f.code for f in findings}


def test_builtin_rules_catch_title_data_markers():
    text = "\n".join([SERIAL, MLRS, f"Lots 1-4 of {LEGAL}, aol", TR, DRIVE, PRIVATE_PATH])
    codes = _codes(scan_text("notes.md", text, BUILTIN_RULES))
    assert {"federal-serial", "section-township-range", "township-range", "cloud-file-link", "private-path"} <= codes


def test_findings_never_echo_matched_values():
    findings = scan_text("notes.md", f"{SERIAL} and {DRIVE}", BUILTIN_RULES)
    assert findings
    rendered = " ".join(str(f) for f in findings)
    assert "123456" not in rendered
    assert "AAAA" not in rendered


def test_hash_is_warning_not_error():
    findings = scan_text("notes.md", HASH, BUILTIN_RULES)
    assert [f.severity for f in findings] == ["warn"]


def test_clean_text_has_no_findings():
    text = "Generic OCR pipeline. Section 11 style. No serials here. See https://example.com/page."
    assert scan_text("README.md", text, BUILTIN_RULES) == []


def test_inline_allow_marker_skips_reviewed_line():
    line = f"{SERIAL}  # boundary-guard: allow synthetic"
    assert scan_text("fixture.py", line, BUILTIN_RULES) == []


def test_blocked_file_types_outside_allowlist(tmp_path: Path):
    for rel in ("deliverables/S1/index.xlsx", "docs/letter.pdf", "data/x.csv", "evidence/p1.png", "out/pack.zip"):
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"\x00\x01")
        assert scan_file(tmp_path, rel, _config()), rel


def test_allowlisted_binary_is_accepted(tmp_path: Path):
    target = tmp_path / "tests" / "fixtures" / "sample.xlsx"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"PK\x00\x00")
    assert scan_file(tmp_path, "tests/fixtures/sample.xlsx", _config()) == []


def test_extra_private_patterns_from_env_and_local_file(tmp_path: Path):
    (tmp_path / ".boundary-guard.local.json").write_text(json.dumps(["secretproj\\d+"]), encoding="utf-8")
    config = load_config(tmp_path, env={"BOUNDARY_GUARD_EXTRA_PATTERNS": json.dumps(["clientco"])})
    note = tmp_path / "note.md"
    note.write_text("Work for ClientCo on SecretProj42.", encoding="utf-8")
    findings = scan_file(tmp_path, "note.md", config)
    assert len([f for f in findings if f.code.startswith("private-identifier")]) == 2


def test_scan_file_reads_text_and_reports_line_numbers(tmp_path: Path):
    note = tmp_path / "docs" / "n.md"
    note.parent.mkdir()
    note.write_text(f"ok\nok\nfound {SERIAL}\n", encoding="utf-8")
    findings = scan_file(tmp_path, "docs/n.md", _config())
    assert [(f.code, f.line) for f in findings] == [("federal-serial", 3)]


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def test_cli_base_mode_blocks_new_offender_only(tmp_path: Path, capsys):
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "README.md").write_text("clean\n", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "base")
    _git(tmp_path, "checkout", "-q", "-b", "feature")
    clean = tmp_path / "ok.py"
    clean.write_text("print('ok')\n", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "clean")
    assert main(["--root", str(tmp_path), "--base", "main"]) == 0

    bad = tmp_path / "deliverables" / "idx.xlsx"
    bad.parent.mkdir()
    bad.write_bytes(b"PK\x00\x00")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "bad")
    assert main(["--root", str(tmp_path), "--base", "main"]) == 1
    captured = capsys.readouterr()
    assert "blocked" in captured.out + captured.err


def test_repository_tree_is_clean():
    repo = Path(__file__).resolve().parents[1]
    assert main(["--root", str(repo), "--all"]) == 0
