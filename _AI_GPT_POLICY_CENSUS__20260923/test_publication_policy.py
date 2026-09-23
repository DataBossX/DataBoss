"""Tests for the copy-ready publication-policy gate.

Forbidden fixtures are assembled from fragments so this test module can itself
be scanned. Every forbidden temporary file includes an explicit SYNTHETIC
marker and contains no real credential, cloud identifier, path, or client fact.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


HERE = Path(__file__).resolve().parent
REPOSITORY_ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from publication_policy_gate import scan_path, summarise  # noqa: E402


def _rules(root: Path) -> set[str]:
    return {finding.rule for finding in scan_path(root)}


@pytest.mark.parametrize(
    ("name", "content", "expected_rule"),
    [
        (
            "synthetic_credential.txt",
            "SYNTHETIC_FORBIDDEN\napi_key = "
            + '"'
            + ("qz" * 18)
            + '"\n',
            "credential_assignment",
        ),
        (
            "synthetic_windows_path.txt",
            "SYNTHETIC_FORBIDDEN "
            + "D:"
            + "\\"
            + "Users"
            + "\\"
            + "Example"
            + "\\private.txt\n",
            "private_windows_path",
        ),
        (
            "synthetic_drive_id.txt",
            "SYNTHETIC_FORBIDDEN folder_id = " + ("A" * 28) + "\n",
            "cloud_drive_id",
        ),
    ],
)
def test_synthetic_forbidden_content_fails_closed(
    tmp_path: Path, name: str, content: str, expected_rule: str
) -> None:
    (tmp_path / name).write_text(content, encoding="utf-8")
    assert expected_rule in _rules(tmp_path)


def test_synthetic_forbidden_report_filename_fails_closed(tmp_path: Path) -> None:
    filename = "_".join(("SYNTHETIC", "CLIENT", "FINAL", "REPORT")) + ".xlsx"
    (tmp_path / filename).write_bytes(b"synthetic-only")
    assert "client_report_filename" in _rules(tmp_path)


def test_synthetic_fixture_directory_allows_noncredential_patterns(tmp_path: Path) -> None:
    fixture = tmp_path / "examples" / "projects" / "SYNTHETIC-DEMO"
    fixture.mkdir(parents=True)
    content = (
        "SYNTHETIC_FIXTURE "
        + "D:"
        + "\\"
        + "Users"
        + "\\Example "
        + "folder_id="
        + ("B" * 28)
    )
    (fixture / "SYNTHETIC_CLIENT_FINAL_REPORT.xlsx").write_text(
        content, encoding="utf-8"
    )
    assert scan_path(tmp_path) == []


def test_architecture_docs_allow_noncredential_examples(tmp_path: Path) -> None:
    architecture = tmp_path / "docs" / "architecture"
    architecture.mkdir(parents=True)
    content = (
        "Architecture example: "
        + "D:"
        + "\\"
        + "Users"
        + "\\Example; folder_id="
        + ("C" * 28)
    )
    (architecture / "design.md").write_text(content, encoding="utf-8")
    assert scan_path(tmp_path) == []


def test_allowlisted_context_does_not_allow_credentials(tmp_path: Path) -> None:
    architecture = tmp_path / "docs" / "architecture"
    architecture.mkdir(parents=True)
    content = "SYNTHETIC_FORBIDDEN\nsecret_key=" + '"' + ("qv" * 18) + '"\n'
    (architecture / "design.md").write_text(content, encoding="utf-8")
    assert "credential_assignment" in _rules(tmp_path)


def test_summary_redacts_values_and_paths(tmp_path: Path) -> None:
    sensitive_name = "_".join(("SYNTHETIC", "OWNER", "REPORT")) + ".pdf"
    (tmp_path / sensitive_name).write_bytes(b"synthetic-only")
    rendered = json.dumps(summarise(scan_path(tmp_path)), sort_keys=True)
    assert sensitive_name not in rendered
    assert "synthetic-only" not in rendered
    assert "path_digest" in rendered


def test_current_tree_findings_are_documented_without_historical_failure(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Inventory current findings; do not turn intentional public docs into failure."""

    result = summarise(scan_path(REPOSITORY_ROOT))
    documented = {
        "pass": result["pass"],
        "finding_count": result["finding_count"],
        "by_rule": result["by_rule"],
        "note": "Historical/current findings are census data, not a test assertion.",
    }
    print(json.dumps(documented, sort_keys=True))
    captured = capsys.readouterr()
    assert "finding_count" in captured.out
    assert isinstance(result["finding_count"], int)
