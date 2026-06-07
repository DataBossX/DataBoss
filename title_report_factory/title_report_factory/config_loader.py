"""Load and validate run configuration.

Secrets never live in config files -- credentials are read from the
environment (.env) only. The config describes the *subject property* and the
input/output folders.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field

try:  # optional, but recommended
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    def load_dotenv(*_a, **_k):
        return False


class SubjectProperty(BaseModel):
    entity: str = "Unknown"
    county: str = "Unknown"
    state: str = "Unknown"
    section: str = ""
    township: str = ""
    range: str = ""
    search_variations: List[str] = Field(default_factory=list)


class RunConfig(BaseModel):
    project_name: str = "cursory_title_report"
    subject_property: SubjectProperty = Field(default_factory=SubjectProperty)
    input_dirs: List[str] = Field(default_factory=lambda: ["inputs"])
    output_dir: str = "outputs"
    template_workbook: Optional[str] = None
    authoritative_source_workbook: Optional[str] = None
    output_file_name: str = "Cursory_Title_Report.xlsx"
    enable_download: bool = False
    enable_ocr: bool = True
    enable_llm: bool = False
    parallel_workers: int = 4

    # Resolved at load time, not serialized from JSON.
    config_path: str = ""
    base_dir: str = ""

    def resolved_input_dirs(self) -> List[Path]:
        base = Path(self.base_dir)
        return [(base / d).resolve() for d in self.input_dirs]

    def resolved_output_dir(self) -> Path:
        return (Path(self.base_dir) / self.output_dir).resolve()


def load_config(config_path: str) -> RunConfig:
    """Load .env (for secrets), then the JSON run config."""
    load_dotenv()  # pulls credentials into os.environ if a .env exists

    path = Path(config_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    cfg = RunConfig(**data)
    cfg.config_path = str(path)
    # Inputs/outputs are resolved relative to the config file's project root
    # (the directory that contains the configs/ folder), falling back to CWD.
    project_root = path.parent
    if project_root.name == "configs":
        project_root = project_root.parent
    cfg.base_dir = str(project_root)

    # LLM is only enabled when both requested *and* a key is present.
    if cfg.enable_llm and not _any_llm_key():
        cfg.enable_llm = False
    return cfg


def _any_llm_key() -> bool:
    return any(
        os.getenv(k)
        for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "LITELLM_API_KEY")
    )
