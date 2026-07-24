"""Canonical DataBossX foundation package."""

from .config import DataBossConfig
from .database import DataBossDatabase
from .executor import (
    FollowUpTask,
    Orchestrator,
    RunSummary,
    TaskContext,
    TaskExecutionError,
    TaskOutcome,
    WorkerRegistry,
)
from .intake import (
    create_project,
    inventory_source,
    register_source_connection,
    register_workbook_template,
)
from .orchestrator import seed_project_intake_run
from .workers import register_intake_workers, run_project_intake

__all__ = [
    "DataBossConfig",
    "DataBossDatabase",
    "FollowUpTask",
    "Orchestrator",
    "RunSummary",
    "TaskContext",
    "TaskExecutionError",
    "TaskOutcome",
    "WorkerRegistry",
    "create_project",
    "inventory_source",
    "register_intake_workers",
    "register_source_connection",
    "register_workbook_template",
    "run_project_intake",
    "seed_project_intake_run",
]

__version__ = "0.1.0"
