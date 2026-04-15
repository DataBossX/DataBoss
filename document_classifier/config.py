"""
Centralised configuration for the Document Classifier app.

All environment variables and tuneable constants live here so every other
module imports from one place.  Change a value here; it propagates everywhere.
"""

import os
from pathlib import Path


class Config:
    # ── Anthropic ─────────────────────────────────────────────────────────────
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    MODEL: str = "claude-opus-4-6"
    MAX_TOKENS: int = 700           # classification JSON is always short

    # ── Document processing ────────────────────────────────────────────────────
    # Characters sent to the AI.  ~4 000 chars ≈ 1 000 tokens — enough for
    # classification without busting the budget on huge documents.
    MAX_TEXT_CHARS: int = 4_000
    SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({".pdf", ".docx"})

    # ── Output ────────────────────────────────────────────────────────────────
    EXCEL_OUTPUT_PATH: Path = Path("document_classifications.xlsx")

    EXCEL_COLUMNS: list[str] = [
        "Timestamp",
        "Filename",
        "Extension",
        "Document Category",
        "Confidence",
        "Summary",
        "Key Topics",
        "Reasoning",
    ]

    # ── Logging ───────────────────────────────────────────────────────────────
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = "document_classifier.log"

    # ── Document categories (also injected into the AI prompt) ────────────────
    DOCUMENT_CATEGORIES: list[str] = [
        "Invoice",
        "Contract",
        "Resume / CV",
        "Report",
        "Letter",
        "Form",
        "Presentation",
        "Manual / Guide",
        "Legal Document",
        "Financial Statement",
        "Medical Record",
        "Email / Correspondence",
        "Academic Paper",
        "News / Article",
        "Technical Specification",
        "Other",
    ]
