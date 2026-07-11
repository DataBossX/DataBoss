"""Logging for the Foundry.

Two channels:

* Human logs — standard :mod:`logging` to stderr, configured once per CLI run.
* Structured logs — :class:`JsonlLogger` writes one JSON object per line so the
  runner's task logs are machine-parseable (timing, exit codes, rollbacks).
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict

LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"


def setup_logging(verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format=LOG_FORMAT,
        stream=sys.stderr,
        force=True,
    )


def utc_now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="milliseconds")


class JsonlLogger:
    """Append-only structured event log (one JSON object per line).

    Append-only by construction — consistent with the Zero-Destruction law:
    events are never rewritten, only added.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def event(self, kind: str, **fields: Any) -> Dict[str, Any]:
        record: Dict[str, Any] = {"ts": utc_now_iso(), "event": kind}
        record.update(fields)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, default=str) + "\n")
        return record
