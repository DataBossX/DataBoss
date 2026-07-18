"""Runsheet generator (Move #16) — chronological runsheet rows from the
chain graph, each row carrying its evidence link and open issues.

Output is a list of plain dicts (the same shape ``qa_engine`` checks), so it
can be written to CSV/XLSX by any writer or dropped straight into the
approved template by the report builders.
"""

from __future__ import annotations

import csv
from pathlib import Path

from .chain_graph import ChainGraph

COLUMNS = ["Instrument_Number", "Recorded_Date", "Grantor", "Grantee", "Type",
           "Book_Page", "Legal_Description", "Interest_Conveyed", "Tracts",
           "Evidence_ID", "Notes", "Open_Issues"]


def generate_runsheet(graph: ChainGraph) -> list[dict]:
    """Chronological rows; chain findings are attached to their instrument."""
    findings_by_instrument: dict[str, list[str]] = {}
    for f in graph.analyze():
        if f.instrument_id:
            findings_by_instrument.setdefault(f.instrument_id, []).append(
                f"{f.rule}: {f.message}")

    rows = []
    for n in sorted(graph.instruments, key=lambda n: (n.date or "9999", n.instrument_id)):
        rows.append({
            "Instrument_Number": n.instrument_id,
            "Recorded_Date": n.date,
            "Grantor": "; ".join(n.grantors),
            "Grantee": "; ".join(n.grantees),
            "Type": n.kind,
            "Book_Page": n.book_page,
            "Legal_Description": n.legal_description,
            "Interest_Conveyed": str(n.interest_conveyed) if n.interest_conveyed is not None else "",
            "Tracts": "; ".join(str(t) for t in n.tracts),
            "Evidence_ID": n.evidence_id,
            "Notes": n.notes,
            "Open_Issues": " | ".join(findings_by_instrument.get(n.instrument_id, [])),
        })
    return rows


def write_runsheet_csv(rows: list[dict], path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return p
