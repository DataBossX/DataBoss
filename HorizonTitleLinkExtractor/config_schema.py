"""
config_schema.py
================
Typed validation for config.yaml using pydantic.

Loading config through `validate_config()` turns silent typos and wrong types
(e.g. a string where a number is expected) into a clear, actionable error
*before* a long automation run starts. Unknown keys are preserved (extra=allow)
so the file can carry notes/future settings without breaking.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AppConfig(BaseModel):
    """Validated view of config.yaml. All fields have safe defaults."""

    model_config = ConfigDict(extra="allow")

    # Drive
    drive_folder_url: str = ""
    source_workbook_strategy: str = "latest_non_ai_review_title_report"
    source_workbook_name_override: Optional[str] = None
    output_folder_strategy: str = "create_timestamped_ai_folder"
    output_folder_prefix: str = "_AI_Updated_Reports"

    # Browser
    browser_headless: bool = False
    auth_state_path: str = ".auth/county_state.json"

    # Row range / limits
    start_row: Optional[int] = None
    end_row: Optional[int] = None
    max_rows: Optional[int] = None
    test_mode_rows: int = 5
    max_pages_per_document: int = 3

    # Saving / temp
    save_documents: bool = False
    save_screenshots: bool = False
    debug_save_screenshots: bool = False
    delete_temp_after_each_row: bool = True

    # Models
    openai_model: str = "gpt-5.2"
    openai_fallback_models: List[str] = Field(default_factory=list)
    gemini_model: str = "gemini-2.5-pro"
    claude_model: str = "claude-sonnet-4"

    # Validation / consensus
    always_validate: bool = False
    validate_changed_rows: bool = True
    validate_low_confidence_rows: bool = True
    ai_confidence_auto_safe_threshold: float = 0.97
    ai_confidence_review_threshold: float = 0.85

    # Timing / retries
    request_delay_seconds: float = 1.0
    request_jitter_seconds: float = 0.0
    max_retries_per_row: int = 3
    timeout_seconds: int = 45

    # Resume / output
    resume_from_log: bool = True
    force_reprocess: bool = False
    apply_corrections: bool = False
    write_review_columns: bool = True
    highlight_changed_cells: bool = True

    # New in v2 (all optional, safe defaults)
    dry_run: bool = False
    enable_ai_cache: bool = True
    cache_dir: str = ".cache"
    generate_html_report: bool = True

    @field_validator(
        "ai_confidence_auto_safe_threshold", "ai_confidence_review_threshold"
    )
    @classmethod
    def _check_threshold(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("confidence thresholds must be between 0 and 1")
        return v

    @field_validator("max_pages_per_document", "test_mode_rows", "max_retries_per_row")
    @classmethod
    def _check_positive(cls, v: int) -> int:
        if v is not None and v < 0:
            raise ValueError("must be zero or positive")
        return v


def validate_config(raw: dict) -> dict:
    """Validate a raw config dict and return it normalized (as a dict).

    Raises pydantic.ValidationError with a readable message on bad input.
    """
    model = AppConfig.model_validate(raw or {})
    # Return a plain dict so the rest of the codebase keeps using dict access.
    return model.model_dump()
