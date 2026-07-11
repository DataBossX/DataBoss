from __future__ import annotations

import json
from pathlib import Path

from databossx.versioned import (
    base_stem,
    list_versions,
    next_version_path,
    parse_version,
    versioned_write,
    versioned_write_json,
)


def test_parse_and_strip_version():
    assert parse_version(Path("report_v003.xlsx")) == 3
    assert parse_version(Path("report.xlsx")) is None
    assert base_stem(Path("report_v003.xlsx")) == "report"
    assert base_stem(Path("plain.txt")) == "plain"


def test_versioned_write_never_overwrites(tmp_path: Path):
    p1 = versioned_write(tmp_path, "out", ".txt", "one")
    p2 = versioned_write(tmp_path, "out", ".txt", "two")
    assert p1.name == "out_v001.txt"
    assert p2.name == "out_v002.txt"
    assert p1.read_text(encoding="utf-8") == "one"  # original untouched
    assert p2.read_text(encoding="utf-8") == "two"


def test_versioned_stem_with_existing_suffix_does_not_stack(tmp_path: Path):
    versioned_write(tmp_path, "out", ".txt", "one")
    p = next_version_path(tmp_path, "out_v001", ".txt")
    assert p.name == "out_v002.txt"


def test_list_versions_sorted_and_filtered(tmp_path: Path):
    for _ in range(3):
        versioned_write(tmp_path, "a", ".txt", "x")
    versioned_write(tmp_path, "b", ".txt", "y")
    (tmp_path / "a.txt").write_text("unversioned")
    versions = list_versions(tmp_path, "a", ".txt")
    assert [v.name for v in versions] == ["a_v001.txt", "a_v002.txt", "a_v003.txt"]
    assert list_versions(tmp_path / "nope", "a", ".txt") == []


def test_versioned_write_bytes_and_json(tmp_path: Path):
    p = versioned_write(tmp_path, "bin", ".dat", b"\x00\x01")
    assert p.read_bytes() == b"\x00\x01"
    j = versioned_write_json(tmp_path, "payload", {"k": 1})
    assert json.loads(j.read_text(encoding="utf-8")) == {"k": 1}
