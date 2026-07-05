"""Section 31 app configuration.

Centralises every path, constant and tunable used by the Section 31 automation
app. Defaults mirror the mission spec for the operator's Windows box
(``D:\\Desktop\\Horizon\\Roger Mills``) but every value is overridable via the
constructor, environment variables, or CLI/UI, so the identical code is
unit-testable inside a Linux sandbox. Nothing here touches the filesystem at
import time.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# --- Section identity --------------------------------------------------------
SECTION = "31"
TOWNSHIP = "12N"
RANGE = "24W"
COUNTY = "Roger Mills"
STATE = "Oklahoma"
SECTION_LABEL = f"Section {SECTION}-{TOWNSHIP}-{RANGE}"

# The single product: the final workbook that lives, alone, in the main folder.
FINAL_WORKBOOK_NAME = (
    "SECTION31_12N_24W_ROGER_MILLS_FINAL_OWNERSHIP_TITLE_REPORT.xlsx"
)

# Default Windows root from the mission spec. Used only as a default; never
# required to exist for imports or tests.
DEFAULT_WINDOWS_ROOT = r"D:\Desktop\Horizon\Roger Mills"

# Managed subfolders created inside the main Roger Mills folder.
SUBFOLDERS = {
    "app": "_section31_app",
    "candidates": "_candidate_workbooks",
    "images": "_source_images",
    "archive": "_archive",
    "qa": "_qa",
    "logs": "_logs",
    "exports": "_exports",
}

# Image-purchase spend cap (hard ceiling, in USD).
IMAGE_SPEND_CAP = 100.00

# Keys that must never be printed/echoed. Any env var whose name contains one
# of these tokens is masked in every log / UI surface.
SECRET_TOKENS = (
    "KEY", "SECRET", "TOKEN", "PASSWORD", "PASS", "CREDENTIAL", "PRIVATE",
)

# Fuzzy-match threshold for legal-description crosswalking (0-100).
LEGAL_MATCH_THRESHOLD = 82


@dataclass
class Section31Config:
    """Resolved configuration for one Section 31 run."""

    root: Path
    app_dir: Path = field(init=False)
    candidates_dir: Path = field(init=False)
    images_dir: Path = field(init=False)
    archive_dir: Path = field(init=False)
    qa_dir: Path = field(init=False)
    logs_dir: Path = field(init=False)
    exports_dir: Path = field(init=False)
    final_workbook: Path = field(init=False)

    section_label: str = SECTION_LABEL
    image_spend_cap: float = IMAGE_SPEND_CAP
    legal_match_threshold: int = LEGAL_MATCH_THRESHOLD

    def __post_init__(self) -> None:
        self.root = Path(self.root)
        self.app_dir = self.root / SUBFOLDERS["app"]
        self.candidates_dir = self.root / SUBFOLDERS["candidates"]
        self.images_dir = self.root / SUBFOLDERS["images"]
        self.archive_dir = self.root / SUBFOLDERS["archive"]
        self.qa_dir = self.root / SUBFOLDERS["qa"]
        self.logs_dir = self.root / SUBFOLDERS["logs"]
        self.exports_dir = self.root / SUBFOLDERS["exports"]
        self.final_workbook = self.root / FINAL_WORKBOOK_NAME

    # -- factory ------------------------------------------------------------
    @classmethod
    def from_env(cls, root: Optional[str] = None) -> "Section31Config":
        """Build config from an explicit root, ``SECTION31_ROOT`` /
        ``HORIZON_ROOT`` env vars, or the Windows default -- in that order."""
        resolved = (
            root
            or os.environ.get("SECTION31_ROOT")
            or os.environ.get("HORIZON_ROOT")
            or DEFAULT_WINDOWS_ROOT
        )
        return cls(root=Path(resolved))

    @property
    def managed_dirs(self):
        return (
            self.app_dir, self.candidates_dir, self.images_dir,
            self.archive_dir, self.qa_dir, self.logs_dir, self.exports_dir,
        )

    def ensure_workspace(self) -> None:
        """Create the working subfolders (idempotent). Never deletes sources."""
        self.root.mkdir(parents=True, exist_ok=True)
        for folder in self.managed_dirs:
            folder.mkdir(parents=True, exist_ok=True)

    def is_managed(self, path: Path) -> bool:
        """True if ``path`` lives under one of the app's own working folders."""
        path = Path(path)
        for managed in self.managed_dirs:
            try:
                path.relative_to(managed)
                return True
            except ValueError:
                continue
        return False
