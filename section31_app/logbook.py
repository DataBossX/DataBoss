"""Append-only, secret-safe logging for the Section 31 pipeline.

Every pipeline step routes human-readable progress through :class:`LogBook`.
Messages are scrubbed of anything that looks like a secret before being written
to disk or returned to the UI, so a log file can be shared without leaking keys.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from .config import SECRET_TOKENS


def _secret_values() -> List[str]:
    vals = []
    for key, val in os.environ.items():
        up = key.upper()
        if val and len(val) >= 6 and any(tok in up for tok in SECRET_TOKENS):
            vals.append(val)
    return vals


_URL_CRED = re.compile(r"(https?://)([^/\s:@]+):([^/\s@]+)@")


def scrub(message: str) -> str:
    """Redact known secret values and URL credentials from ``message``."""
    text = str(message)
    for val in _secret_values():
        text = text.replace(val, "********")
    text = _URL_CRED.sub(r"\1********:********@", text)
    return text


class LogBook:
    """Collects timestamped, scrubbed log lines; mirrors them to a file."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path else None
        self.lines: List[str] = []

    def log(self, message: str, level: str = "INFO") -> str:
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
        line = f"[{stamp}] {level:<5} {scrub(message)}"
        self.lines.append(line)
        if self.path:
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with self.path.open("a", encoding="utf-8") as fh:
                    fh.write(line + "\n")
            except OSError:
                pass
        return line

    def info(self, message: str) -> str:
        return self.log(message, "INFO")

    def warn(self, message: str) -> str:
        return self.log(message, "WARN")

    def error(self, message: str) -> str:
        return self.log(message, "ERROR")

    def text(self) -> str:
        return "\n".join(self.lines)
