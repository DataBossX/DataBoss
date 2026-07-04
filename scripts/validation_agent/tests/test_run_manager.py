"""Run manager: immutable folders, versioning, never overwrites."""

from __future__ import annotations

import pytest

from core.run_manager import RunManager, RunManagerError, RUN_SUBDIRS


def test_creates_all_subdirs(settings):
    run = RunManager.create(settings.outputs_dir, timestamp="20260704_010101")
    for sub in RUN_SUBDIRS:
        assert (run.run_folder / sub).is_dir()


def test_source_ingest_creates_v0_and_hash(settings, valid_workbook):
    run = RunManager.create(settings.outputs_dir, timestamp="20260704_010102")
    v0 = run.ingest_source_workbook(valid_workbook)
    assert v0.index == 0
    assert v0.label == "v000"
    assert v0.origin == "source_copy"
    assert len(v0.sha256) == 64
    assert v0.path.exists()
    # original preserved in input/ too
    assert (run.input_dir / valid_workbook.name).exists()


def test_original_workbook_unchanged_after_ingest(settings, valid_workbook):
    from core.hashing import sha256_file

    before = sha256_file(valid_workbook)
    run = RunManager.create(settings.outputs_dir, timestamp="20260704_010103")
    run.ingest_source_workbook(valid_workbook)
    after = sha256_file(valid_workbook)
    assert before == after  # source immutability


def test_new_version_never_overwrites(settings, valid_workbook):
    run = RunManager.create(settings.outputs_dir, timestamp="20260704_010104")
    run.ingest_source_workbook(valid_workbook)
    dest = run.new_version_path("repair")
    dest.write_bytes(b"PK\x03\x04dummy")
    v1 = run.register_version(dest, "repair")
    assert v1.index == 1
    # requesting a new version path again must not collide with v1
    dest2 = run.new_version_path("recalc")
    assert dest2 != dest
    assert not dest2.exists()


def test_double_create_same_timestamp_fails(settings):
    RunManager.create(settings.outputs_dir, timestamp="20260704_010105")
    with pytest.raises(RunManagerError):
        RunManager.create(settings.outputs_dir, timestamp="20260704_010105")
