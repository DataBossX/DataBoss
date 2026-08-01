"""Cross-candidate consensus and disagreement analysis.

The rule that matters here: **agreement is not evidence.** If any qualified
reader reports a cell as unreadable, a majority of confident readings does not
get to overwrite that — the cell becomes a human-review item with the competing
readings attached. Majority vote is used only to summarise agreement, never to
manufacture a value the source does not support.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass


@dataclass(frozen=True)
class CellConsensus:
    page_id: str
    row: int
    field: str
    status: str  # agreed | disagreed | contested_unreadable | no_assertion
    value: str | None
    readings: dict
    unreadable_reports: tuple
    requires_human_review: bool

    def to_dict(self) -> dict:
        return {
            "page_id": self.page_id,
            "row": self.row,
            "field": self.field,
            "status": self.status,
            "value": self.value,
            "readings": self.readings,
            "unreadable_reports": list(self.unreadable_reports),
            "requires_human_review": self.requires_human_review,
        }


def build_consensus(candidates: list[dict], truth: dict | None = None) -> dict:
    """Compare candidates cell by cell.

    ``candidates`` are schema-valid candidate outputs. ``truth`` is optional and
    only used to record where a vote would have overruled the source; it never
    changes what is adopted.
    """
    cells: dict[tuple, dict] = {}
    for candidate in candidates:
        candidate_id = candidate["candidate_id"]
        for entry in candidate.get("entries", []):
            page_id = entry.get("page_id")
            row = entry.get("row")
            for name, field in entry.get("fields", {}).items():
                cells.setdefault((page_id, row, name), {})[candidate_id] = field

    results: list[CellConsensus] = []
    vote_overruled: list[str] = []

    for (page_id, row, name), readings in sorted(cells.items(), key=lambda item: str(item[0])):
        unreadable = tuple(
            sorted(cid for cid, field in readings.items() if field.get("state") == "unreadable")
        )
        asserted = {
            cid: field.get("value")
            for cid, field in readings.items()
            if field.get("state") in ("known", "uncertain") and field.get("value") is not None
        }
        display = {
            cid: {
                "value": field.get("value"),
                "state": field.get("state"),
                "confidence": field.get("confidence"),
            }
            for cid, field in sorted(readings.items())
        }

        if unreadable and asserted:
            # Source evidence wins: a smudge does not become a value because
            # other readers were confident.
            results.append(
                CellConsensus(
                    page_id, row, name, "contested_unreadable", None, display, unreadable, True
                )
            )
            if truth is not None:
                true_value, true_state = truth.get((page_id, row, name), (None, "unknown"))
                if true_state in ("unreadable", "absent"):
                    vote_overruled.append(
                        f"{page_id}#{row}.{name}: {len(asserted)} candidate(s) asserted a value for a "
                        f"cell the source records as {true_state}; not adopted."
                    )
            continue

        if not asserted:
            results.append(
                CellConsensus(page_id, row, name, "no_assertion", None, display, unreadable, False)
            )
            continue

        counts = Counter(str(value) for value in asserted.values())
        top_value, top_count = counts.most_common(1)[0]
        if len(counts) == 1 and not unreadable:
            results.append(
                CellConsensus(page_id, row, name, "agreed", top_value, display, unreadable, False)
            )
        else:
            results.append(
                CellConsensus(
                    page_id,
                    row,
                    name,
                    "disagreed",
                    None if top_count <= len(asserted) / 2 else top_value,
                    display,
                    unreadable,
                    True,
                )
            )

    disagreements = [cell for cell in results if cell.status in ("disagreed", "contested_unreadable")]
    return {
        "cells": [cell.to_dict() for cell in results],
        "disagreements": [cell.to_dict() for cell in disagreements],
        "agreed_count": sum(1 for cell in results if cell.status == "agreed"),
        "disagreed_count": sum(1 for cell in results if cell.status == "disagreed"),
        "contested_unreadable_count": sum(
            1 for cell in results if cell.status == "contested_unreadable"
        ),
        "vote_overruled_by_source": vote_overruled,
        "human_review_cells": [cell.to_dict() for cell in results if cell.requires_human_review],
    }


def describe_disagreements(consensus: dict, limit: int = 10) -> list[str]:
    lines = []
    for cell in consensus["disagreements"][:limit]:
        readings = ", ".join(
            f"{cid}={info['value']!r} ({info['state']}, {info['confidence']})"
            for cid, info in sorted(cell["readings"].items())
        )
        reason = (
            "one or more readers could not read this cell"
            if cell["status"] == "contested_unreadable"
            else "readers returned different values"
        )
        lines.append(f"{cell['page_id']} row {cell['row']} · {cell['field']}: {reason} — {readings}")
    return lines
