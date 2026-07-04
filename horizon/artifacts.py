"""Human-facing review artifacts.

The audit log is a machine trail; a title examiner needs a *punch list*. These
writers produce two CSVs next to the final report so a person knows exactly what
must be resolved before the cursory report is signed off:

* ``examiner_review_worklist.csv`` -- every row tagged Needs Examiner Review /
  ESCALATED, with the reason and the instrument to pull.
* ``chain_breaks.csv`` -- every instrument number that fails to match across the
  OGL register and the runsheet (the classic break the mission warns about).

Nothing here changes the report; it only reports what could not be tied out.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import TYPE_CHECKING, List, Tuple

from .models import ESCALATED_TAG, REVIEW_TAG, ReportModel

if TYPE_CHECKING:  # avoid a runtime import cycle
    from .pipeline import ChainedBuild


def write_review_worklist(report: ReportModel, path: Path) -> int:
    """Write the examiner worklist CSV. Returns the number of rows written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [r for r in report.rows if r.needs_review
            or ESCALATED_TAG.lower() in (r.remarks or "").lower()]
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["instrument_number", "grantor", "grantee",
                    "legal_description", "conveyed_interest", "retained_interest",
                    "net_mineral_acres", "status", "reason"])
        for r in rows:
            tag = ESCALATED_TAG if ESCALATED_TAG.lower() in (r.remarks or "").lower() \
                else REVIEW_TAG
            w.writerow([
                r.instrument_number, r.grantor, r.grantee, r.legal_description,
                r.conveyed_interest or "", r.retained_interest or "",
                r.net_mineral_acres or "", tag, r.remarks,
            ])
    return len(rows)


def write_chain_breaks(build: "ChainedBuild", path: Path) -> int:
    """Write the chain-breaks CSV from a ChainedBuild. Returns rows written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["instrument_number", "status", "detail"])
        for c in build.chain_breaks:
            detail = {
                "orphan_note": "runsheet note references an instrument with no OGL record",
                "unreferenced_ogl": "OGL instrument never referenced in the runsheet",
            }.get(c.status, c.status)
            w.writerow([c.key, c.status, detail])
    return len(build.chain_breaks)


def write_all(build: "ChainedBuild", folder: Path) -> List[Tuple[str, int]]:
    """Write both artifacts into ``folder``. Returns [(filename, rows), ...]."""
    folder.mkdir(parents=True, exist_ok=True)
    n_review = write_review_worklist(build.report, folder / "examiner_review_worklist.csv")
    n_breaks = write_chain_breaks(build, folder / "chain_breaks.csv")
    return [("examiner_review_worklist.csv", n_review),
            ("chain_breaks.csv", n_breaks)]
