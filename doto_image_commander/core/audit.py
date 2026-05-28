"""Append-only file-based audit log (in addition to DB audit_log table)."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import config

_log_path: Path = config.AUDIT_LOG_PATH
logging.basicConfig(
    filename=_log_path,
    level=logging.INFO,
    format="%(asctime)s\t%(levelname)s\t%(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
_audit = logging.getLogger("doto.audit")


def record(event_type: str, description: str, data: Any = None,
           api_called: str = None, cost: float = None) -> None:
    payload = {"event": event_type, "desc": description}
    if data:
        payload["data"] = data
    if api_called:
        payload["api"] = api_called
    if cost is not None:
        payload["cost"] = cost
    _audit.info(json.dumps(payload))

    # Mirror to DB (import here to avoid circular)
    try:
        from .database import log_audit
        log_audit(event_type, description, data, api_called, cost)
    except Exception:
        pass
