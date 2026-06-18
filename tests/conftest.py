"""Shared pytest configuration: make the repo root and backend importable."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
for _p in (ROOT, BACKEND):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
