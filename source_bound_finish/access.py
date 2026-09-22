"""Fail-closed access probe. No source means no completeness claim."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

SOURCE_ENV = "SOURCE_BOUND_ROOT"


@dataclass
class AccessReceipt:
    writable_client_targets: bool
    sole_writer: bool
    source_root: str
    source_root_exists: bool
    source_file_count: int
    report_writes: int
    status: str
    blockers: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def probe_access(
    source_root: str | Path | None = None,
    *,
    sole_writer: bool = False,
) -> AccessReceipt:
    """Probe a local source root only.

    Authenticated remote stores are out of scope. Absence is a blocker, not a
    zero-source census.
    """
    blockers: list[str] = []
    notes = [
        "UNKNOWN is not ZERO",
        "A staged prompt is not sole-writer authority",
        "Model agreement is not source proof",
    ]
    raw = source_root or os.environ.get(SOURCE_ENV, "")
    root = Path(raw) if raw else Path()
    exists = bool(raw) and root.exists() and root.is_dir()
    count = 0
    if exists:
        count = sum(1 for path in root.rglob("*") if path.is_file())
        if count == 0:
            blockers.append("SOURCE_ROOT_EMPTY")
    else:
        blockers.append("SOURCE_ROOT_UNAVAILABLE")
    if not sole_writer:
        notes.append("REPORT_WRITES=0; no sole-writer acknowledgement in this session")
    status = "BLOCKED" if blockers else "LOCAL_SOURCES_PRESENT"
    return AccessReceipt(
        writable_client_targets=False,
        sole_writer=bool(sole_writer),
        source_root=str(root) if raw else "",
        source_root_exists=exists,
        source_file_count=count,
        report_writes=0,
        status=status,
        blockers=blockers,
        notes=notes,
    )
