#!/usr/bin/env python3
"""Repository-local DataBossX launcher; no package installation required."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from databossx.cli import main  # noqa: E402

raise SystemExit(main())
