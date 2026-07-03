"""Centralized logging setup for DataBossX (stdlib-only).

Writes to logs/databossx.log and to the console. Keeps a single configured
root so every module shares one audit trail — 'every action leaves proof'.
"""
from __future__ import annotations

import logging
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = ROOT / "logs"
LOG_FILE = LOG_DIR / "databossx.log"

_FMT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
_configured = False


def setup_logging(level: int = logging.INFO) -> None:
    global _configured
    if _configured:
        return
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    handlers = [logging.StreamHandler(), logging.FileHandler(LOG_FILE, encoding="utf-8")]
    logging.basicConfig(level=level, format=_FMT, handlers=handlers)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(name)
