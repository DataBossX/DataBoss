"""Path setup so this suite is collectable by pytest as well as unittest.

The test modules import ``command_center`` at module scope, which resolves only
when ``services/control_api`` is on ``sys.path``. Running via
``python -m unittest`` supplies that through ``PYTHONPATH``; pytest does not, and
conftest is imported before any test module, so it is the right place to fix it.

The repository's top-level ``tests/conftest.py`` performs the same job for
``src/``. This file deliberately does not touch that one.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVICE_ROOT = REPO_ROOT / "services" / "control_api"

if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))
