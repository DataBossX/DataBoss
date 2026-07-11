"""Tests for the foundation: scan, unzip, SHA256 dedup, quarantine."""

import zipfile
from pathlib import Path

import pytest

from horizon.audit import AuditLog
from horizon.config import HorizonConfig
from horizon.foundation import (
    dedupe,
    run_cleanup,
    scan,
    sha256_of,
    snapshot_backup,
    unzip_archives,
)


@pytest.fixture()
def workspace(tmp_path: Path):
    root = tmp_path / "Horizon"
    root.mkdir()
    cfg = HorizonConfig(root=root)
    audit = AuditLog(path=None, echo=False)
    return cfg, audit


def test_sha256_of(tmp_path):
    f = tmp_path / "a.txt"
    f.write_bytes(b"hello")
    import hashlib
    assert sha256_of(f) == hashlib.sha256(b"hello").hexdigest()


def test_scan_computes_hashes(workspace):
    cfg, audit = workspace
    (cfg.root / "one.csv").write_text("a,b\n1,2\n")
    (cfg.root / "sub").mkdir()
    (cfg.root / "sub" / "two.txt").write_text("hi")
    records = scan(cfg, audit)
    assert len(records) == 2
    assert all(r.sha256 for r in records)


def test_dedupe_keeps_highest_fidelity(workspace):
    cfg, audit = workspace
    cfg.ensure_workspace()
    # identical bytes, different extensions -> xlsx-ish wins over txt
    payload = b"DUPLICATE-CONTENT"
    (cfg.root / "keep.csv").write_bytes(payload)
    (cfg.root / "drop.txt").write_bytes(payload)
    records = scan(cfg, audit)
    result = dedupe(records, cfg, audit)
    assert result.duplicate_groups == 1
    assert len(result.quarantined) == 1
    # csv outranks txt, so drop.txt is quarantined
    assert result.quarantined[0].rel == "drop.txt"
    assert not (cfg.root / "drop.txt").exists()
    assert (cfg.trash / "drop.txt").exists()  # moved, not deleted
    assert (cfg.root / "keep.csv").exists()   # source untouched


def test_unique_files_not_quarantined(workspace):
    cfg, audit = workspace
    cfg.ensure_workspace()
    (cfg.root / "a.txt").write_bytes(b"aaa")
    (cfg.root / "b.txt").write_bytes(b"bbb")
    records = scan(cfg, audit)
    result = dedupe(records, cfg, audit)
    assert result.quarantined == []
    assert result.duplicate_groups == 0


def test_unzip_archives(workspace):
    cfg, audit = workspace
    cfg.ensure_workspace()
    archive = cfg.root / "bundle.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("inside/report.csv", "x,y\n1,2\n")
    extracted = unzip_archives(cfg, audit)
    assert len(extracted) == 1
    found = list(cfg.temp_raw.rglob("report.csv"))
    assert found and found[0].read_text().startswith("x,y")


def test_run_cleanup_end_to_end(workspace):
    cfg, audit = workspace
    (cfg.root / "orig.csv").write_bytes(b"same")
    (cfg.root / "copy.csv").write_bytes(b"same")
    result = run_cleanup(cfg, audit, backup=True)
    assert result.duplicate_groups == 1
    assert len(result.quarantined) == 1
    # snapshot backup created a sibling *_Backups tree
    assert cfg.backups.exists()
    assert audit.count("INFO") > 0


def test_snapshot_is_hash_verified(workspace):
    cfg, audit = workspace
    (cfg.root / "source.txt").write_bytes(b"authoritative")
    snapshot = snapshot_backup(cfg, audit)
    manifest = snapshot / "snapshot_manifest.json"
    assert manifest.exists()
    assert (snapshot / "source.txt").read_bytes() == b"authoritative"
    assert sha256_of(snapshot / "source.txt") == sha256_of(cfg.root / "source.txt")


def test_backup_failure_aborts_before_quarantine(workspace, monkeypatch):
    cfg, audit = workspace
    original = cfg.root / "original.csv"
    duplicate = cfg.root / "duplicate.csv"
    original.write_bytes(b"same")
    duplicate.write_bytes(b"same")

    def fail_copy(*_args, **_kwargs):
        raise OSError("simulated backup failure")

    monkeypatch.setattr("horizon.foundation.shutil.copy2", fail_copy)
    with pytest.raises(OSError, match="simulated backup failure"):
        run_cleanup(cfg, audit, backup=True)

    assert original.exists()
    assert duplicate.exists()
    assert list(cfg.trash.iterdir()) == []
    assert list(cfg.backups.iterdir()) == []
