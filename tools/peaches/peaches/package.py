"""Build a clean client ZIP from a manifest, with a separate QA receipt.

Manifest JSON: either a list of entries or {"files": [entries]}.
Each entry: {"path": ..., "arcname": optional, "role": optional}.
Any entry whose arcname/path matches a QA/internal pattern
(*QA*, *ledger*, *prompt*, *.py — case-insensitive) is EXCLUDED from the
client ZIP unless its role is exactly "include".

The QA receipt (QA_RECEIPT.json) is written to a separate QA directory,
never inside the client ZIP.

CLI: python -m peaches.package <manifest.json> <client_zip> <qa_dir>
"""
from __future__ import annotations

import fnmatch
import json
import os
import sys
import zipfile
from datetime import datetime, timezone

from .inventory import sha256_file

EXCLUDE_PATTERNS = ["*qa*", "*ledger*", "*prompt*", "*.py"]


def _excluded_by(name):
    lowered = name.lower()
    for pattern in EXCLUDE_PATTERNS:
        if fnmatch.fnmatch(lowered, pattern):
            return pattern
    return None


def build_package(manifest_path, zip_path, qa_dir):
    with open(manifest_path, encoding="utf-8") as fh:
        manifest = json.load(fh)
    entries = manifest["files"] if isinstance(manifest, dict) else manifest
    members = []
    excluded = []
    os.makedirs(os.path.dirname(os.path.abspath(zip_path)), exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for entry in entries:
            src = entry["path"]
            arcname = entry.get("arcname") or os.path.basename(src)
            role = entry.get("role", "")
            pattern = None if role == "include" else (
                _excluded_by(arcname) or _excluded_by(src))
            if pattern:
                excluded.append({"path": src, "arcname": arcname,
                                 "pattern": pattern})
                continue
            digest = sha256_file(src)
            zf.write(src, arcname)
            members.append({"arcname": arcname, "source_path": src,
                            "sha256": digest,
                            "bytes": os.path.getsize(src)})
    with zipfile.ZipFile(zip_path) as zf:
        bad = zf.testzip()
        crc_ok = bad is None
        zip_members = zf.namelist()
    receipt = {
        "zip": os.path.basename(zip_path),
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "manifest": os.path.abspath(manifest_path),
        "member_count": len(zip_members),
        "members": members,
        "excluded": excluded,
        "crc_ok": crc_ok,
        "crc_bad_file": bad,
    }
    os.makedirs(qa_dir, exist_ok=True)
    with open(os.path.join(qa_dir, "QA_RECEIPT.json"), "w",
              encoding="utf-8") as fh:
        json.dump(receipt, fh, indent=2)
    return receipt


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 3:
        print("usage: python -m peaches.package <manifest.json> <client_zip> "
              "<qa_dir>", file=sys.stderr)
        return 2
    receipt = build_package(argv[0], argv[1], argv[2])
    print("package: %d members, %d excluded, CRC %s -> %s (receipt in %s)"
          % (receipt["member_count"], len(receipt["excluded"]),
             "ok" if receipt["crc_ok"] else "FAILED: %s" % receipt["crc_bad_file"],
             argv[1], argv[2]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
