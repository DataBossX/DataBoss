"""
config_schema.py
================
Typed, validated configuration. Catches bad config.yaml values up front with a
clear message instead of a confusing crash 200 rows into a run.
"""

from __future__ import annotations

from typing import Any

import yaml
from pydantic import BaseModel, Field, ValidationError, model_validator


class Config(BaseModel):
    # Drive
    drive_folder_url: str = ""
    source_workbook_strategy: str = "latest_non_ai_review_title_report"
    source_workbook_name_override: str | None = None
    output_folder_strategy: str = "create_timestamped_ai_folder"
    output_folder_prefix: str = "_AI_Updated_Reports"

    # Browser
    browser_headless: bool = False
    auth_state_path: str = ".auth/county_state.json"

    # Range / limits
    start_row: int | None = None
    end_row: int | None = None
    max_rows: int | None = None
    test_mode_rows: int = Field(5, ge=1)
    max_pages_per_document: int = Field(3, ge=1, le=20)

    # File handling
    save_documents: bool = False
    save_screenshots: bool = False
    debug_save_screenshots: bool = False
    delete_temp_after_each_row: bool = True

    # AI models
    openai_model: str = "gpt-5.2"
    gemini_model: str = "gemini-2.5-pro"
    claude_model: str = "claude-sonnet-4"

    # Validation / consensus
    always_validate: bool = False
    validate_changed_rows: bool = True
    validate_low_confidence_rows: bool = True
    ai_confidence_auto_safe_threshold: float = Field(0.97, ge=0.0, le=1.0)
    ai_confidence_review_threshold: float = Field(0.85, ge=0.0, le=1.0)

    # Fuzzy matching thresholds (new)
    match_same_threshold: float = Field(0.97, ge=0.0, le=1.0)
    match_minor_threshold: float = Field(0.85, ge=0.0, le=1.0)

    # Image preprocessing (new)
    preprocess_images: bool = True
    flag_poor_image_quality: bool = True

    # Caching / cost (new)
    use_cache: bool = True
    cache_dir: str = ".cache"

    # Offline demo / dry-run mode (no browser, no AI, no network)
    offline_mode: bool = False

    # Production hardening
    checkpoint_every: int = Field(10, ge=1)   # save review workbook every N rows
    scan_outputs_for_secrets: bool = True     # refuse to upload secret-shaped files
    write_run_manifest: bool = True
    domain_checks: bool = True                # PLSS + sanity flags on extractions

    # Timing / retries
    request_delay_seconds: float = Field(1.0, ge=0.0)
    max_retries_per_row: int = Field(3, ge=1)
    timeout_seconds: int = Field(45, ge=5)

    # Resume / output
    resume_from_log: bool = True
    force_reprocess: bool = False
    apply_corrections: bool = False
    write_review_columns: bool = True
    highlight_changed_cells: bool = True
    generate_html_report: bool = True

    # Allow forward-compatible extra keys without crashing.
    input_dir: str | None = None
    debug_dir: str | None = None

    @model_validator(mode="after")
    def _safe_ge_review(self) -> "Config":
        if self.ai_confidence_auto_safe_threshold < self.ai_confidence_review_threshold:
            raise ValueError(
                "ai_confidence_auto_safe_threshold must be >= "
                "ai_confidence_review_threshold")
        return self

    model_config = {"extra": "allow"}


def load_validated(path: str) -> dict[str, Any]:
    """Load config.yaml, validate it, and return a plain dict (with defaults).

    Raises ValueError with a readable message on invalid config.
    """
    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    try:
        cfg = Config(**raw)
    except ValidationError as exc:
        lines = [f"  - {'.'.join(str(p) for p in e['loc'])}: {e['msg']}"
                 for e in exc.errors()]
        raise ValueError("Invalid config.yaml:\n" + "\n".join(lines)) from exc
    return cfg.model_dump()
