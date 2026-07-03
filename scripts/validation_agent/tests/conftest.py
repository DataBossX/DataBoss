"""Pytest bootstrap: isolate the agent's filesystem + import path.

Runs before any test module is imported so that the ``config`` singleton is
instantiated against a throwaway temp root (no repo pollution, no shared DB
with a developer's real runs).
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

# Point the whole agent (outputs dir + SQLite DB) at a throwaway root.
os.environ.setdefault("DATABOSSX_ROOT", tempfile.mkdtemp(prefix="dbx_test_"))

# Make ``import validation_agent`` resolve from the scripts/ directory.
_SCRIPTS_DIR = Path(__file__).resolve().parents[2]
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
