"""Workbook fingerprinting for DataBossX.

A fingerprint is the SHA-256 of the raw .xlsx bytes plus size/mtime. Used to
PROVE a source workbook was not modified by review tooling.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class Fingerprint:
    path: str
    size: int
    sha256: str

    def to_dict(self) -> dict:
        return asdict(self)


def fingerprint(path: Path) -> Fingerprint:
    path = Path(path)
    data = path.read_bytes()
    return Fingerprint(
        path=path.as_posix(),
        size=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
    )


def unchanged(before: Fingerprint, after: Fingerprint) -> bool:
    return before.sha256 == after.sha256 and before.size == after.size


def render_proof(before: Fingerprint, after: Fingerprint, ts: str) -> str:
    ok = unchanged(before, after)
    return "\n".join([
        f"# Source Change Proof — {ts}",
        "",
        f"Source workbook: `{before.path}`",
        "",
        "| Stage | Size (bytes) | SHA-256 |",
        "|-------|--------------|---------|",
        f"| Before review | {before.size} | `{before.sha256}` |",
        f"| After review  | {after.size} | `{after.sha256}` |",
        "",
        f"**Result: {'✅ SOURCE UNCHANGED' if ok else '🚨 SOURCE WAS MODIFIED — INVESTIGATE'}**",
        "",
        json.dumps({"before": before.to_dict(), "after": after.to_dict(), "unchanged": ok}, indent=2),
        "",
    ])
