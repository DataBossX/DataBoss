"""Run manager: immutable baseline copy, versioning never overwrites, and the
original source workbook is never opened for writing."""

import hashlib

import pytest

from core.run_manager import RunManager, sha256_file
from tests.fixtures.make_fixtures import make_basic_workbook


def test_baseline_copies_and_hashes(tmp_path):
    src = make_basic_workbook(tmp_path / "source.xlsx")
    src_hash = sha256_file(src)
    rm = RunManager(tmp_path / "outputs", timestamp="20260101_000000")
    baseline, h = rm.ingest_baseline(src)
    assert baseline.exists()
    assert h == src_hash
    # Original is byte-identical and untouched.
    assert sha256_file(src) == src_hash


def test_all_subdirs_created(tmp_path):
    rm = RunManager(tmp_path / "outputs", timestamp="20260101_000001")
    for sub in ("input", "versions", "sources", "reports", "audit", "logs",
                "escalations", "exports"):
        assert (rm.run_dir / sub).is_dir()


def test_version_paths_never_collide(tmp_path):
    rm = RunManager(tmp_path / "outputs", timestamp="20260101_000002")
    src = make_basic_workbook(tmp_path / "source.xlsx")
    rm.ingest_baseline(src)
    p1 = rm.next_version_path()
    p1.write_bytes(b"v1")
    rm.register_version(p1)
    p2 = rm.next_version_path()
    assert p1 != p2
    assert p1.name == "workbook_v001.xlsx"
    assert p2.name == "workbook_v002.xlsx"


def test_baseline_refuses_double_write(tmp_path):
    rm = RunManager(tmp_path / "outputs", timestamp="20260101_000003")
    src = make_basic_workbook(tmp_path / "source.xlsx")
    rm.ingest_baseline(src)
    with pytest.raises(FileExistsError):
        rm.ingest_baseline(src)


def test_second_run_same_timestamp_gets_new_dir(tmp_path):
    out = tmp_path / "outputs"
    rm1 = RunManager(out, timestamp="20260101_000004")
    rm2 = RunManager(out, timestamp="20260101_000004")
    assert rm1.run_dir != rm2.run_dir


def test_unique_export_path(tmp_path):
    rm = RunManager(tmp_path / "outputs", timestamp="20260101_000005")
    a = rm.unique_export_path("report.md")
    a.write_text("x")
    b = rm.unique_export_path("report.md")
    assert a != b
