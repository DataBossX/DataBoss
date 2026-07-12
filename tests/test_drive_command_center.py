import hashlib
import json
import os
import time
from pathlib import Path

import pytest

from automation.drive_command_center.watcher import (
    EXPECTED_FOLDERS,
    CommandCenterWatcher,
    WatcherConfig,
    atomic_write_json,
)
from automation.drive_command_center.windows_setup import install_startup


def make_center(tmp_path: Path) -> Path:
    root = tmp_path / "command-center"
    for folder in EXPECTED_FOLDERS:
        (root / folder).mkdir(parents=True)
    return root


def make_watcher(root: Path) -> CommandCenterWatcher:
    return CommandCenterWatcher(
        WatcherConfig(
            root=root,
            canonical_folder_id="synthetic-folder-id",
            local_state_dir=root.parent / ".watcher-state",
        )
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
    second = root / "inbox" / "JOB_TEST-001.json"
    second.write_text(content, encoding="utf-8")

    make_watcher(root).run(once=True)

    assert (root / "quarantine" / second.name).is_file()


def test_filename_job_id_mismatch_is_quarantined(tmp_path: Path) -> None:
    root = make_center(tmp_path)
    job = write_job(root, name="JOB_OTHER-001.json")

    make_watcher(root).run(once=True)

    assert not job.exists()
    assert (root / "quarantine" / job.name).is_file()


def test_symlink_job_is_never_read_or_executed(tmp_path: Path) -> None:
    root = make_center(tmp_path)
    outside = tmp_path / "outside.json"
    outside.write_text(
        json.dumps(
            {"schema_version": "1.0", "job_id": "LINK-001", "operation": "noop"}
        ),
        encoding="utf-8",
    )
    job = root / "inbox" / "JOB_LINK-001.json"
    job.symlink_to(outside)

    make_watcher(root).run(once=True)

    assert outside.is_file()
    assert outside.read_text(encoding="utf-8")
    assert (root / "quarantine" / job.name).is_symlink()
    assert not list((root / "completed").iterdir())


def test_state_transition_never_overwrites_existing_file(tmp_path: Path) -> None:
    root = make_center(tmp_path)
    write_job(root)
    collision = root / "completed" / "JOB_TEST-001.json"
    collision.write_text("preserve me", encoding="utf-8")

    make_watcher(root).run(once=True)

    assert collision.read_text(encoding="utf-8") == "preserve me"
    receipt = json.loads(
        (root / "failed" / "RESULT_TEST-001.json").read_text(encoding="utf-8")
    )
    assert receipt["status"] == "failed"
    assert receipt["errors"]


def test_ack_collision_fails_job_without_overwrite(tmp_path: Path) -> None:
    root = make_center(tmp_path)
    write_job(root)
    existing_ack = root / "results" / "ACK_TEST-001.json"
    existing_ack.write_text('{"preserve": true}', encoding="utf-8")

    make_watcher(root).run(once=True)

    assert json.loads(existing_ack.read_text(encoding="utf-8")) == {"preserve": True}
    assert (root / "failed" / "JOB_TEST-001.json").is_file()
    receipt = json.loads(
        (root / "failed" / "RESULT_TEST-001.json").read_text(encoding="utf-8")
    )
    assert receipt["status"] == "failed"
    assert "FileExistsError" in receipt["errors"][0]


def test_atomic_writer_never_removes_foreign_temporary_file(tmp_path: Path) -> None:
    destination = tmp_path / "receipt.json"
    foreign_temporary = tmp_path / f".receipt.json.{os.getpid()}.0.tmp"
    foreign_temporary.write_text("preserve me", encoding="utf-8")

    with pytest.raises(FileExistsError):
        atomic_write_json(destination, {"status": "completed"}, allow_replace=False)

    assert foreign_temporary.read_text(encoding="utf-8") == "preserve me"
    assert not destination.exists()


def test_one_shot_returns_failure_when_poll_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_center(tmp_path)
    watcher = make_watcher(root)

    def fail_poll() -> int:
        raise OSError("synthetic sync failure")

    monkeypatch.setattr(watcher, "poll_once", fail_poll)

    assert watcher.run(once=True) == 1
    online = json.loads((root / "WATCHER_ONLINE.json").read_text(encoding="utf-8"))
    assert online["last_error"] == "OSError: synthetic sync failure"


def test_stale_claimed_job_gets_failed_terminal_receipt(tmp_path: Path) -> None:
    root = make_center(tmp_path)
    stale = root / "claimed" / "JOB_STALE-001.json"
    stale.write_text(
        json.dumps(
            {"schema_version": "1.0", "job_id": "STALE-001", "operation": "noop"}
        ),
        encoding="utf-8",
    )
    old = time.time() - 1_000
    os.utime(stale, (old, old))

    make_watcher(root).run(once=True)

    assert not stale.exists()
    assert (root / "failed" / stale.name).is_file()
    receipt = json.loads(
        (root / "failed" / "RESULT_STALE-001.json").read_text(encoding="utf-8")
    )
    assert receipt["status"] == "failed"
    assert "crash recovery" in receipt["errors"][0]


def test_missing_folder_fails_closed(tmp_path: Path) -> None:
    root = make_center(tmp_path)
    (root / "quarantine").rmdir()

    with pytest.raises(FileNotFoundError):
        make_watcher(root).validate_layout()


def test_startup_requires_successful_self_test(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_center(tmp_path)
    config = tmp_path / "watcher_config.json"
    config.write_text(
        json.dumps(
            {
                "root": str(root),
                "canonical_folder_id": "synthetic-folder-id",
                "local_state_dir": str(root.parent / ".watcher-state"),
            }
        ),
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
        json.dumps(
            {
                "root": str(root),
                "canonical_folder_id": "synthetic-folder-id",
                "local_state_dir": str(root.parent / ".watcher-state"),
            }
        ),
        encoding="utf-8",
    )
    write_job(root, name="JOB_SELFTEST-001.json", job_id="SELFTEST-001")
    assert make_watcher(root).run(once=True) == 0
    appdata = tmp_path / "AppData"
    monkeypatch.setenv("APPDATA", str(appdata))

    startup = install_startup(config, "SELFTEST-001")

    assert startup.is_file()
    assert str(config.resolve()) in startup.read_text(encoding="utf-8")
    assert str(Path("automation/drive_command_center/watcher.py")) in startup.read_text(
        encoding="utf-8"
    )
    assert startup.parent.name == "Startup"
    method = json.loads(
        (root / "config" / "startup_method.json").read_text(encoding="utf-8")
    )
    assert method["administrator_privileges_required"] is False
    assert method["registry_modified"] is False

    startup.write_text("preserve old startup", encoding="utf-8")
    install_startup(config, "SELFTEST-001")
    backups = list((root / "config" / "startup_backups").rglob("*.cmd"))
    assert any(path.read_text(encoding="utf-8") == "preserve old startup" for path in backups)
