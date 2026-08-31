"""Canonical DataBossX foundation package."""

from .config import DataBossConfig
from .database import DataBossDatabase
from .intake import (
    create_project,
    inventory_source,
    register_source_connection,
    register_workbook_template,
)
from .orchestrator import seed_project_intake_run
from .title_verifier import (
    LegalDescriptionSTR,
    TitleChainAuditResult,
    TitleDocumentFact,
    TitleVerifier,
    VerificationFinding,
    normalize_party_name,
    parse_legal_description_str,
    parse_recording_references,
    parse_standard_date,
)

__all__ = [
    "DataBossConfig",
    "DataBossDatabase",
    "create_project",
    "inventory_source",
    "register_source_connection",
    "register_workbook_template",
    "seed_project_intake_run",
    "LegalDescriptionSTR",
    "TitleChainAuditResult",
    "TitleDocumentFact",
    "TitleVerifier",
    "VerificationFinding",
    "normalize_party_name",
    "parse_legal_description_str",
    "parse_recording_references",
    "parse_standard_date",
]

__version__ = "0.1.0"
