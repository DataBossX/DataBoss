"""Automatic, non-destructive backup of a prior output folder.

Before a run overwrites deliverables in the output folder, the previous run's
files are copied into a timestamped ``_backups`` subfolder. Nothing is ever
deleted -- this is the zero-destruction safety net a non-programmer relies on to
recover an earlier report.
"""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

BACKUP_DIRNAME = "_backups"

# Deliverable files a run regenerates; these are what we protect.
_PROTECTED = (
    "DataBossX_Report.xlsx",
    "DataBossX_Report.pdf",
    "dashboard.html",
    "run_manifest.json",
)


def backup_prior_output(output_dir: Path) -> Optional[str]:
    """Copy existing deliverables into ``_backups/<timestamp>/``.

    Returns a short human note describing what was backed up, or ``None`` when
    there was nothing to protect (a first run). Never raises for an I/O problem
    -- a backup failure must not stop the run, only be reported.
    """
    output_dir = Path(output_dir)
    existing = [output_dir / name for name in _PROTECTED
                if (output_dir / name).exists()]
    if not existing:
        return None
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    dest = output_dir / BACKUP_DIRNAME / stamp
    try:
        dest.mkdir(parents=True, exist_ok=True)
        for f in existing:
            shutil.copy2(f, dest / f.name)
    except OSError as exc:
        return f"backup skipped ({exc})"
    return f"backed up {len(existing)} prior deliverable(s) to {dest}"
