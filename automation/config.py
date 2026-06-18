"""Typed configuration loader for the automation bot.

Reads ``config/settings.toml`` (stdlib ``tomllib``) with robust fallbacks so the
bot keeps working even if the file is missing or partial. This replaces the
constants that were previously hardcoded in ``playwright_bot.py``.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

try:  # Python 3.11+
    import tomllib  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - older interpreters
    tomllib = None  # type: ignore

DEFAULT_SETTINGS_PATH = (
    Path(__file__).resolve().parent.parent / "config" / "settings.toml"
)


@dataclass(frozen=True)
class AutomationConfig:
    base_url: str = "https://weldrecorder.weldgov.com/web/"
    delay_sec: float = 3.5
    workbook: str = "Black_Tip_Notice_List_verified_updated_20251028_v7.xlsx"
    sheet_dsu: str = "DSU NOTICE LIST"
    sheet_offset: str = "OFFSET NOTICE LIST"
    json_out: str = "data/json_traces"
    log_dir: str = "data/logs"
    export_dir: str = "data/exports"
    extractor_model: str = "anthropic:claude-3-5-sonnet"
    reasoner_model: str = "openai:gpt-4o"
    max_concurrent: int = 6
    timeout_sec: int = 45
    retries: int = 3

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AutomationConfig":
        site = data.get("site", {}) or {}
        paths = data.get("paths", {}) or {}
        llms = data.get("llms", {}) or {}
        execn = data.get("execution", {}) or {}
        d = cls()  # defaults
        return cls(
            base_url=str(site.get("base_url", d.base_url)),
            delay_sec=float(site.get("delay_sec", d.delay_sec)),
            workbook=str(paths.get("workbook", d.workbook)),
            sheet_dsu=str(paths.get("sheet_dsu", d.sheet_dsu)),
            sheet_offset=str(paths.get("sheet_offset", d.sheet_offset)),
            json_out=str(paths.get("json_out", d.json_out)),
            log_dir=str(paths.get("log_dir", d.log_dir)),
            export_dir=str(paths.get("export_dir", d.export_dir)),
            extractor_model=str(llms.get("extractor", d.extractor_model)),
            reasoner_model=str(llms.get("reasoner", d.reasoner_model)),
            max_concurrent=int(execn.get("max_concurrent", d.max_concurrent)),
            timeout_sec=int(execn.get("timeout_sec", d.timeout_sec)),
            retries=int(execn.get("retries", d.retries)),
        )


def load_config(path: Optional[Path] = None) -> AutomationConfig:
    """Load configuration, falling back to defaults on any problem."""
    settings_path = Path(path) if path else DEFAULT_SETTINGS_PATH
    if tomllib is None or not settings_path.exists():
        return AutomationConfig()
    try:
        with open(settings_path, "rb") as fh:
            data = tomllib.load(fh)
        return AutomationConfig.from_dict(data)
    except Exception:
        return AutomationConfig()
