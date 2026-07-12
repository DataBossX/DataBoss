import hashlib
import json
from pathlib import Path

import pytest

from automation.drive_command_center.watcher import (
    EXPECTED_FOLDERS,
    CommandCenterWatcher,
    WatcherConfig,
)
from automation.drive_command_center.windows_setup import install_startup


def make_center(tmp_path: Path) -> Path:
    root = tmp_path / "command-center"
    for folder in EXPECTED_FOLDERS:
        (root / folder).mkdir(parents=True)
    return root


def make_watcher(root: Path) -> CommandCenterWatcher:
    return CommandCenterWatcher(
        WatcherConfig(root=root, canonical_folder_id="synthetic-folder-id")
    )


def write_job(root: Path, name: str = "JOB_TEST-001.json", **changes: object) -> Path:
    job = {"schema_version": "1.0", "job_id": "TEST-001", "operation": "noop"}
    job.update(changes)
    path = root / "inbox" / name
    path.write_text(json.dumps(job), encoding="utf-8")
    return path


def test_noop_job_completes_with_ack_heartbeat_and_receipt(tmp_path: Path) -> None:
    root = make_center(tmp_path)
    evidence = tmp_path / "evidence.txt"
    evidence.write_text("must not change", encoding="utf-8")
    before = hashlib.sha256(evidence.read_bytes()).hexdigest()
    job = write_job(root)

    assert make_watcher(root).run(once=True) == 0

    assert not job.exists()
    assert (root / "results" / "ACK_TEST-001.json").is_file()
    assert (root / "logs" / "HEARTBEAT_TEST-001.json").is_file()
    assert (root / "completed" / "JOB_TEST-001.json").is_file()
    receipt_path = root / "completed" / "RESULT_TEST-001.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["status"] == "completed"
    assert receipt["source_files_modified"] is False
    assert receipt["expected_folders_detected"] == list(EXPECTED_FOLDERS)
    assert receipt["errors"] == []
    assert hashlib.sha256(evidence.read_bytes()).hexdigest() == before


def test_malformed_job_is_quarantined(tmp_path: Path) -> None:
    root = make_center(tmp_path)
    job = root / "inbox" / "JOB_BAD.json"
    job.write_text("{not json", encoding="utf-8")

    make_watcher(root).run(once=True)

    assert not job.exists()
    assert (root / "quarantine" / job.name).is_file()


def test_disallowed_operation_is_rejected(tmp_path: Path) -> None:
    root = make_center(tmp_path)
    job = write_job(root, operation="shell")

    make_watcher(root).run(once=True)

    assert not job.exists()
    assert (root / "rejected" / job.name).is_file()
    assert not list((root / "completed").iterdir())


def test_duplicate_content_is_quarantined(tmp_path: Path) -> None:
    root = make_center(tmp_path)
    first = write_job(root)
    content = first.read_text(encoding="utf-8")
    make_watcher(root).run(once=True)
    second = root / "inbox" / "JOB_TEST-002.json"
    second.write_text(content, encoding="utf-8")

    make_watcher(root).run(once=True)

    assert (root / "quarantine" / second.name).is_file()


def test_missing_folder_fails_closed(tmp_path: Path) -> None:
    root = make_center(tmp_path)
    (root / "quarantine").rmdir()

    with pytest.raises(FileNotFoundError):
        make_watcher(root).validate_layout()


def test_startup_requires_successful_self_test(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_center(tmp_path)
    config = tmp_path / "watcher_config.json"
    config.write_text(
        json.dumps({"root": str(root), "canonical_folder_id": "synthetic-folder-id"}),
        encoding="utf-8",
    )
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData"))

    with pytest.raises(RuntimeError, match="self-test"):
        install_startup(config, "SELFTEST-001")


def test_startup_uses_user_startup_folder_after_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_center(tmp_path)
    config = tmp_path / "watcher_config.json"
    config.write_text(
        json.dumps({"root": str(root), "canonical_folder_id": "synthetic-folder-id"}),
        encoding="utf-8",
    )
    receipt = {
        "job_id": "SELFTEST-001",
        "status": "completed",
        "source_files_modified": False,
        "safety_statement": "Original project evidence and Dropbox were not modified.",
    }
    (root / "completed" / "RESULT_SELFTEST-001.json").write_text(
        json.dumps(receipt), encoding="utf-8"
    )
    appdata = tmp_path / "AppData"
    monkeypatch.setenv("APPDATA", str(appdata))

    startup = install_startup(config, "SELFTEST-001")

    assert startup.is_file()
    assert str(config.resolve()) in startup.read_text(encoding="utf-8")
    assert startup.parent.name == "Startup"
