"""Tests for zero-destruction versioned writes."""

from pathlib import Path

from horizon.versioning import (
    latest_version,
    list_versions,
    next_version_path,
    parse_version,
    stem_without_version,
)


def test_parse_version():
    assert parse_version(Path("report_v001.xlsx")) == 1
    assert parse_version(Path("report_v012.xlsx")) == 12
    assert parse_version(Path("report.xlsx")) is None


def test_stem_without_version():
    assert stem_without_version(Path("31-12N-24W_report_v003.xlsx")) == "31-12N-24W_report"
    assert stem_without_version(Path("plain.xlsx")) == "plain"


def test_next_version_starts_at_001(tmp_path):
    p = next_version_path(tmp_path, "report")
    assert p.name == "report_v001.xlsx"


def test_next_version_increments(tmp_path):
    (tmp_path / "report_v001.xlsx").write_text("")
    (tmp_path / "report_v002.xlsx").write_text("")
    p = next_version_path(tmp_path, "report")
    assert p.name == "report_v003.xlsx"


def test_next_version_ignores_other_stems(tmp_path):
    (tmp_path / "report_v001.xlsx").write_text("")
    (tmp_path / "other_v009.xlsx").write_text("")
    assert next_version_path(tmp_path, "report").name == "report_v002.xlsx"


def test_latest_and_list(tmp_path):
    for n in (1, 2, 5):
        (tmp_path / f"report_v{n:03d}.xlsx").write_text("")
    versions = list_versions(tmp_path, "report")
    assert [parse_version(p) for p in versions] == [1, 2, 5]
    assert latest_version(tmp_path, "report").name == "report_v005.xlsx"


def test_next_version_accepts_base_with_version(tmp_path):
    (tmp_path / "report_v001.xlsx").write_text("")
    # Passing an already-versioned stem should still resolve the base.
    assert next_version_path(tmp_path, "report_v001").name == "report_v002.xlsx"
