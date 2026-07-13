#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> int:
    here = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        dropbox = root / "dropbox"
        drive = root / "drive"
        output = root / "output"
        dropbox.mkdir()
        drive.mkdir()
        (dropbox / "0001.jpg").write_bytes(b"fake-image-source")
        (drive / "index.csv").write_text("book,page,grantor,grantee\n1,2,A,B\n", encoding="utf-8")
        config = root / "config.json"
        config.write_text(json.dumps({
            "source_roots": [
                {"name": "DROPBOX_TEST", "path": str(dropbox)},
                {"name": "DRIVE_TEST", "path": str(drive)}
            ],
            "output_root": str(output),
            "stability_delay_seconds": 0.01,
            "poll_seconds": 1
        }), encoding="utf-8")
        cmd = [sys.executable, str(here / "watcher.py"), "--config", str(config), "--once"]
        first = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if first.returncode != 0:
            print(first.stdout)
            print(first.stderr, file=sys.stderr)
            return 1
        inbox = list((output / "queue" / "INBOX").glob("*.json"))
        receipts = list((output / "receipts").glob("*.json"))
        if len(inbox) != 2 or len(receipts) != 2:
            print(f"Expected 2 jobs and receipts; got {len(inbox)} jobs, {len(receipts)} receipts")
            return 2
        second = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if second.returncode != 0:
            return 3
        if len(list((output / "queue" / "INBOX").glob("*.json"))) != 2:
            print("Duplicate jobs were emitted on unchanged second scan")
            return 4
        print("PASS: hashing, staging, receipts, jobs, and deduplication verified")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
