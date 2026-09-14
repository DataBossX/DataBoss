"""Canonical DataBossX foundation package."""

from .config import DataBossConfig
from .database import DataBossDatabase
from .engine import execute_capability
from .intake import (
    create_project,
    inventory_source,
    register_source_connection,
    register_workbook_template,
)
from .orchestrator import claim_intake_batch, seed_project_intake_run

__all__ = [
    "DataBossConfig",
    "DataBossDatabase",
    "claim_intake_batch",
    "create_project",
    "execute_capability",
    "inventory_source",
    "register_source_connection",
    "register_workbook_template",
    "seed_project_intake_run",
]

__version__ = "0.1.1"
