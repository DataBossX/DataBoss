"""Deterministic client-package builder and terminal byte gates.

Builds a ZIP with a fixed member order and fixed timestamps so the same
member bytes always yield the same outer SHA-256, then verifies:

* exact required membership (no extra / missing members)
* ZIP CRC (``testzip``)
* per-member SHA-256 and the outer SHA-256
* readback equality of a re-downloaded copy
* a clean-cycle ledger that resets whenever the outer SHA changes

READY requires all gates on one unchanged SHA plus N consecutive clean
cycles after the last byte change.
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

FIXED_TIME = (1980, 1, 1, 0, 0, 0)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_zip(out: Path, members: Sequence[Path]) -> str:
    """Write *members* (flat, in the given order) with fixed timestamps; return outer SHA."""
    names = [Path(m).name for m in members]
    if len(set(names)) != len(names):
        raise ValueError("duplicate member names")
    with zipfile.ZipFile(out, "w") as zf:
        for m in members:
            info = zipfile.ZipInfo(Path(m).name, date_time=FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, Path(m).read_bytes(), compresslevel=9)
    return sha256_file(out)


@dataclass
class GateReport:
    outer_sha256: str
    members: dict[str, str] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.failures

    def as_dict(self) -> dict:
        return {"outer_sha256": self.outer_sha256, "members": self.members,
                "failures": self.failures, "passed": self.passed}


def verify_zip(path: Path, required: Sequence[str]) -> GateReport:
    report = GateReport(outer_sha256=sha256_file(path))
    with zipfile.ZipFile(path) as zf:
        bad = zf.testzip()
        if bad is not None:
            report.failures.append(f"CRC:{bad}")
        names = zf.namelist()
        missing = sorted(set(required) - set(names))
        extra = sorted(set(names) - set(required))
        if missing:
            report.failures.append("MISSING:" + "|".join(missing))
        if extra:
            report.failures.append("EXTRA:" + "|".join(extra))
        for n in names:
            report.members[n] = sha256_bytes(zf.read(n))
    return report


def readback_matches(original: Path, readback: Path) -> bool:
    return sha256_file(original) == sha256_file(readback)


def record_cycle(ledger_path: Path, outer_sha: str, clean: bool, note: str = "") -> int:
    """Append a QA cycle; return consecutive clean cycles on *outer_sha*.

    Any cycle on a different SHA, or any unclean cycle, resets the streak.
    """
    ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else []
    ledger.append({"sha256": outer_sha, "clean": bool(clean), "note": note})
    ledger_path.write_text(json.dumps(ledger, indent=1))
    streak = 0
    for entry in reversed(ledger):
        if entry["sha256"] != outer_sha or not entry["clean"]:
            break
        streak += 1
    return streak
