"""Logging helpers with secret redaction for the DataBossX backend.

Provides a single :func:`redact` function and a logging filter so that API
keys and other obvious secrets never reach log sinks, plus a small helper to
configure logging consistently whether or not ``loguru`` is installed.
"""
from __future__ import annotations

import logging
import re
from typing import Iterable, Optional

# Patterns that should never appear in logs in cleartext.
_SECRET_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9_-]{6,}"),          # Anthropic
    re.compile(r"sk-[A-Za-z0-9]{6,}"),                # OpenAI-style
    re.compile(r"AIza[0-9A-Za-z_\-]{10,}"),           # Google API key
    re.compile(r"AKIA[0-9A-Z]{16}"),                  # AWS access key id
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]{10,}"),  # bearer tokens
]

_REDACTION = "***REDACTED***"


def redact(message: str, extra_secrets: Optional[Iterable[str]] = None) -> str:
    """Return ``message`` with known secret shapes and provided values masked."""
    if not message:
        return message
    text = str(message)
    for value in extra_secrets or ():
        if value and len(value) >= 4:
            text = text.replace(value, _REDACTION)
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(_REDACTION, text)
    return text


class RedactionFilter(logging.Filter):
    """A stdlib logging filter that redacts secrets from formatted messages."""

    def __init__(self, extra_secrets: Optional[Iterable[str]] = None):
        super().__init__()
        self._extra = [s for s in (extra_secrets or ()) if s]

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        try:
            record.msg = redact(record.getMessage(), self._extra)
            record.args = ()
        except Exception:
            pass
        return True


def configure_logging(
    log_path: str,
    level: str = "INFO",
    extra_secrets: Optional[Iterable[str]] = None,
):
    """Configure logging, preferring loguru when available.

    Returns the logger object to use (loguru logger or a stdlib logger). Always
    installs secret redaction.
    """
    secrets = [s for s in (extra_secrets or ()) if s]
    try:
        from loguru import logger as _loguru_logger

        _loguru_logger.remove()

        def _patcher(record):
            record["message"] = redact(record["message"], secrets)

        _loguru_logger = _loguru_logger.patch(_patcher)
        import sys

        _loguru_logger.add(sys.stderr, level=level)
        try:
            _loguru_logger.add(log_path, rotation="10 MB", retention="10 days",
                               level=level)
        except Exception:
            pass  # log dir may be unavailable in some environments
        return _loguru_logger
    except Exception:
        logger = logging.getLogger("databossx")
        logger.setLevel(level)
        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(
                logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
            )
            logger.addHandler(handler)
        logger.addFilter(RedactionFilter(secrets))
        return logger
