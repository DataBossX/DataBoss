"""Utilities: logging, paths, security (secret redaction), hashing."""
from __future__ import annotations
import hashlib
import logging
import re
from pathlib import Path

_SECRET_RE = re.compile(
    r"(sk-[A-Za-z0-9]{8,}|api[_-]?key['\"=:\s]+[A-Za-z0-9\-_]{8,}|Bearer\s+[A-Za-z0-9\.\-_]+)",
    re.I)


def redact(text: str) -> str:
    """Strip anything resembling a secret before logging."""
    return _SECRET_RE.sub("[REDACTED]", text or "")


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact(record.msg)
        return True


def get_logger(name: str = "title_report_builder", logfile: str | None = None) -> logging.Logger:
    log = logging.getLogger(name)
    if log.handlers:
        return log
    log.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    sh.addFilter(RedactingFilter())
    log.addHandler(sh)
    if logfile:
        Path(logfile).parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(logfile)
        fh.setFormatter(fmt)
        fh.addFilter(RedactingFilter())
        log.addHandler(fh)
    return log


def sha256_file(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ensure_dirs(*paths: str | Path) -> None:
    for p in paths:
        Path(p).mkdir(parents=True, exist_ok=True)
