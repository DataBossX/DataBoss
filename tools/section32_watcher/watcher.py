#!/usr/bin/env python3
"""DataBossX Section 32 provenance-safe file watcher.

Watches local Google Drive/Dropbox sync roots read-only, hashes stable source files,
copies new/changed files into isolated staging, and emits deterministic JSON jobs
and receipts. It never edits source files or the canonical workbook.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

ALLOWED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".pdf", ".xlsx", ".xls",
    ".ods", ".csv", ".docx", ".txt", ".md", ".json", ".zip"
}
IGNORE_NAMES = {"thumbs.db", "desktop.ini", ".ds_store"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def stable(path: Path, delay: float) -> bool:
    try:
        first = path.stat()
        time.sleep(delay)
        second = path.stat()
        return first.st_size == second.st_size and first.st_mtime_ns == second.st_mtime_ns
    except (FileNotFoundError, PermissionError, OSError):
        return False


@dataclass(frozen=True)
class SourceRoot:
    name: str
    path: Path


class State:
    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(db_path)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute(
            """CREATE TABLE IF NOT EXISTS files (
                source_name TEXT NOT NULL,
                source_path TEXT NOT NULL,
                size INTEGER NOT NULL,
                mtime_ns INTEGER NOT NULL,
                sha256 TEXT NOT NULL,
                staged_path TEXT NOT NULL,
                first_seen_utc TEXT NOT NULL,
                last_seen_utc TEXT NOT NULL,
                PRIMARY KEY (source_name, source_path)
            )"""
        )
        self.db.commit()

    def prior_hash(self, source_name: str, source_path: str) -> str | None:
        row = self.db.execute(
            "SELECT sha256 FROM files WHERE source_name=? AND source_path=?",
            (source_name, source_path),
        ).fetchone()
        return row[0] if row else None

    def upsert(self, *, source_name: str, source_path: str, size: int,
               mtime_ns: int, sha256: str, staged_path: str) -> None:
        now = utc_now()
        self.db.execute(
            """INSERT INTO files
               (source_name, source_path, size, mtime_ns, sha256, staged_path,
                first_seen_utc, last_seen_utc)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(source_name, source_path) DO UPDATE SET
                 size=excluded.size, mtime_ns=excluded.mtime_ns,
                 sha256=excluded.sha256, staged_path=excluded.staged_path,
                 last_seen_utc=excluded.last_seen_utc""",
            (source_name, source_path, size, mtime_ns, sha256, staged_path, now, now),
        )
        self.db.commit()


def iter_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if path.is_file() and path.name.lower() not in IGNORE_NAMES:
            if path.suffix.lower() in ALLOWED_EXTENSIONS:
                yield path


def safe_component(value: str) -> str:
    return "".join(c if c.isalnum() or c in "._-" else "_" for c in value)


def process_file(source: SourceRoot, path: Path, output: Path, state: State,
                 stability_delay: float) -> dict | None:
    if not stable(path, stability_delay):
        return {"status": "deferred_unstable", "source": str(path)}

    stat = path.stat()
    digest = sha256_file(path)
    relative = path.relative_to(source.path)
    prior = state.prior_hash(source.name, str(relative))
    if prior == digest:
        return None

    staged = output / "staging" / safe_component(source.name) / digest[:2] / digest / relative.name
    staged.parent.mkdir(parents=True, exist_ok=True)
    if not staged.exists():
        shutil.copy2(path, staged)
    staged_digest = sha256_file(staged)
    if staged_digest != digest:
        staged.unlink(missing_ok=True)
        raise RuntimeError(f"Hash mismatch after staging: {path}")

    event_id = str(uuid.uuid4())
    event = {
        "schema_version": "1.0",
        "event_id": event_id,
        "detected_utc": utc_now(),
        "source_name": source.name,
        "source_root": str(source.path),
        "source_relative_path": str(relative),
        "source_size": stat.st_size,
        "source_mtime_ns": stat.st_mtime_ns,
        "sha256": digest,
        "staged_path": str(staged),
        "change_type": "new" if prior is None else "changed",
        "source_policy": "READ_ONLY",
        "canonical_workbook_policy": "NO_DIRECT_WRITE",
        "release_policy": "HOLD_NO_RELEASE",
    }
    atomic_json(output / "receipts" / f"{event_id}.json", event)

    job = {
        "job_id": f"DBX-S32-{event_id}",
        "created_utc": utc_now(),
        "job_type": "INGEST_AND_EXTRACT",
        "priority": "NORMAL",
        "input": event,
        "required_outputs": [
            "document_metadata.json", "page_manifest.json", "extractions.jsonl",
            "instrument_rows.csv", "validation_receipt.json"
        ],
        "rules": [
            "Never edit Dropbox or Google Drive source originals",
            "Never overwrite the canonical workbook",
            "Every extracted fact must cite source file, page/image, and text span",
            "Do not force acreage, ownership, WI, NRI, RI, MRI, or ORRI totals",
            "Quarantine unreadable, duplicate, conflicting, or partial instruments",
            "No promotion without hash and schema validation",
        ],
    }
    atomic_json(output / "queue" / "INBOX" / f"{job['job_id']}.json", job)
    state.upsert(
        source_name=source.name, source_path=str(relative), size=stat.st_size,
        mtime_ns=stat.st_mtime_ns, sha256=digest, staged_path=str(staged),
    )
    return event


def load_config(path: Path) -> tuple[list[SourceRoot], Path, float, int]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    roots = [SourceRoot(x["name"], Path(os.path.expandvars(x["path"])).expanduser())
             for x in raw["source_roots"]]
    output = Path(os.path.expandvars(raw["output_root"])).expanduser()
    return roots, output, float(raw.get("stability_delay_seconds", 2.0)), int(raw.get("poll_seconds", 60))


def run_once(config_path: Path) -> int:
    roots, output, delay, _ = load_config(config_path)
    state = State(output / "state" / "watcher.sqlite3")
    summary = {"started_utc": utc_now(), "roots": [], "events": [], "errors": []}
    for source in roots:
        record = {"name": source.name, "path": str(source.path), "exists": source.path.exists(), "files_seen": 0}
        summary["roots"].append(record)
        if not source.path.exists():
            summary["errors"].append(f"Missing source root: {source.path}")
            continue
        for path in iter_files(source.path):
            record["files_seen"] += 1
            try:
                result = process_file(source, path, output, state, delay)
                if result:
                    summary["events"].append(result)
            except Exception as exc:  # keep scanning, never fail silently
                summary["errors"].append(f"{path}: {type(exc).__name__}: {exc}")
    summary["finished_utc"] = utc_now()
    summary["new_or_changed_count"] = sum(1 for e in summary["events"] if e.get("event_id"))
    atomic_json(output / "status" / "latest_scan.json", summary)
    print(json.dumps(summary, indent=2))
    return 1 if summary["errors"] else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    if args.once:
        return run_once(args.config)
    _, _, _, poll = load_config(args.config)
    while True:
        run_once(args.config)
        time.sleep(poll)


if __name__ == "__main__":
    sys.exit(main())
