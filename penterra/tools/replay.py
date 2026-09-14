"""No-replay detection.

A replay is a candidate that reintroduces a value a source adjudication already
rejected. Values are compared per (stable_key, field).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Rejection:
    key: str
    field: str
    value: str
    reason: str
    receipt: str


class ReplayDetected(RuntimeError):
    pass


def check(candidate_cells: dict[tuple[str, str], str],
          rejections: list[Rejection], *, strict: bool = False) -> dict:
    """Flag any candidate cell that re-asserts a previously rejected value."""
    index: dict[tuple[str, str], list[Rejection]] = {}
    for r in rejections:
        index.setdefault((r.key, r.field), []).append(r)

    replays = []
    for (key, field), value in candidate_cells.items():
        for r in index.get((key, field), []):
            if str(value).strip() == str(r.value).strip():
                replays.append({"key": key, "field": field, "value": value,
                                "rejected_because": r.reason, "receipt": r.receipt})
    if replays and strict:
        raise ReplayDetected(f"{len(replays)} rejected value(s) re-asserted: {replays}")
    return {"replays": replays, "replay_count": len(replays),
            "checked": len(candidate_cells), "clean": not replays}
