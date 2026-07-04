"""Horizon configuration.

Centralises every path and tunable the Command Center uses. Defaults mirror the
mission spec (``D:\\Desktop\\Horizon`` on the operator's Windows box) but every
value is overridable via the constructor, environment variables, or CLI flags,
so the exact same code is unit-testable inside a Linux CI sandbox.

Nothing here touches the filesystem at import time.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# The canonical reference workbooks named in the mission. These are treated as
# the "Golden Source of Truth" (project_notes_updated.xlsx) and the canonical
# column/template authority (the Roger Mills cursory report).
GOLDEN_SOURCE_NAME = "project_notes_updated.xlsx"
TEMPLATE_REPORT_NAME = "31-12N-24W Roger Mills Co. Cursory Title Report (7-3-26) - NHE.xlsx"

# Default Windows root from the mission spec. Used only as a *default*; it is
# never required to exist for imports or tests.
DEFAULT_WINDOWS_ROOT = r"D:\Desktop\Horizon"

MAX_IMPROVEMENT_LOOPS = 5


@dataclass
class HorizonConfig:
    """Resolved configuration for one Horizon run."""

    root: Path
    temp_raw: Path = field(init=False)
    trash: Path = field(init=False)
    final_reports: Path = field(init=False)
    backups: Path = field(init=False)
    audit_log: Path = field(init=False)

    golden_source_name: str = GOLDEN_SOURCE_NAME
    template_report_name: str = TEMPLATE_REPORT_NAME
    max_loops: int = MAX_IMPROVEMENT_LOOPS
    section: str = "31-12N-24W"

    def __post_init__(self) -> None:
        self.root = Path(self.root)
        self.temp_raw = self.root / "temp_raw"
        self.trash = self.root / "trash"
        self.final_reports = self.root / "rogermillsfinalreports"
        # Snapshot rule: a sibling backups tree so a rogue run can be undone.
        self.backups = self.root.parent / (self.root.name + "_Backups")
        self.audit_log = self.root / "horizon_audit.log"

    # -- factory helpers ----------------------------------------------------
    @classmethod
    def from_env(cls, root: Optional[str] = None) -> "HorizonConfig":
        """Build config from an explicit root, the ``HORIZON_ROOT`` env var, or
        the Windows default -- in that order of precedence."""
        resolved = root or os.environ.get("HORIZON_ROOT") or DEFAULT_WINDOWS_ROOT
        return cls(root=Path(resolved))

    def ensure_workspace(self) -> None:
        """Create the working subfolders (idempotent). Never touches sources."""
        for folder in (self.temp_raw, self.trash, self.final_reports):
            folder.mkdir(parents=True, exist_ok=True)

    def is_managed(self, path: Path) -> bool:
        """True if ``path`` is one of Horizon's own working folders -- used to
        avoid ever treating our own churn as source data."""
        path = Path(path)
        for managed in (self.temp_raw, self.trash, self.final_reports, self.backups):
            try:
                path.relative_to(managed)
                return True
            except ValueError:
                continue
        return False
