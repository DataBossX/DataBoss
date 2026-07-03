"""Pytest configuration for the DataBossX Validation Agent.

Goals:
  * When this module's own suite runs (its pinned deps are installed), make the
    agent root importable as top-level packages (config, db, core, ...).
  * When an unrelated *repo-level* CI pytest collects this directory without
    the module's deps installed, DO NOT touch sys.path and DO NOT collect this
    module's tests — so we never shadow another project's packages or error a
    CI job that isn't ours.
"""

import importlib.util
import sys
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parent

_REQUIRED = ["lxml", "rapidfuzz", "reportlab", "streamlit", "docx", "markdown",
             "openpyxl", "pandas", "dotenv"]
_missing = [m for m in _REQUIRED if importlib.util.find_spec(m) is None]

if _missing:
    # Not our environment — stay completely inert.
    collect_ignore_glob = ["tests/*"]
else:
    if str(AGENT_ROOT) not in sys.path:
        sys.path.insert(0, str(AGENT_ROOT))
