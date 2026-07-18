"""Canonical DataBossX package.

Combines the **foundation** layer (SQLite-backed content-addressed vault,
project intake, hashing) with the **Command Center** layer (project
orchestration, exact mineral/WI/NRI economics, Excel/PDF/dashboard reporting,
self-check, backups).

The Command Center reuses the sibling engines that live at the repository root
(``horizon`` and ``grocery_report_pipeline``). Because this package ships under
``src/``, those siblings are not on the import path by default, so we add the
repository root here -- making ``import databossx`` self-sufficient however it
is launched (tests, ``python -m databossx``, or the launchers).
"""

from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path

# Ensure the repository root is importable so the Command Center can reach the
# root-level engines (horizon/, grocery_report_pipeline.py). For
# src/databossx/__init__.py, parents[2] is the repository root.
_REPO_ROOT = _Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_REPO_ROOT))

# -- foundation layer --------------------------------------------------------
from .config import DataBossConfig
from .database import DataBossDatabase
from .intake import (
    create_project,
    inventory_source,
    register_source_connection,
    register_workbook_template,
)
from .orchestrator import seed_project_intake_run

__all__ = [
    "DataBossConfig",
    "DataBossDatabase",
    "create_project",
    "inventory_source",
    "register_source_connection",
    "register_workbook_template",
    "seed_project_intake_run",
]

__version__ = "1.0.0"
