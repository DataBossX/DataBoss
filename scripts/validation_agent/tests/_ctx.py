"""Helper to assemble a validator context from a workbook path."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from config.settings import Settings
from ingestion.sheet_classifier import classify_workbook
from ingestion.workbook_ingestor import ingest_workbook


def make_context(
    workbook: Path, settings: Optional[Settings] = None, source_index: Optional[Dict] = None
) -> Dict[str, Any]:
    structure = ingest_workbook(workbook)
    classification = classify_workbook(structure)
    return {
        "structure": structure,
        "classification": classification,
        "manifest": {},
        "settings": settings,
        "workbook_path": workbook,
        "source_index": source_index or {},
    }
