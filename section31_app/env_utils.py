"""Secure .env loading and secret masking.

Rules enforced here:
  * Load a local .env if present (via python-dotenv when available, else a tiny
    built-in parser so the app still works with zero dependencies).
  * NEVER print, log, or surface a secret value. :func:`mask` redacts any value
    whose key looks sensitive, and :func:`safe_env_summary` gives the UI a
    presence/absence view only ("set" / "not set"), never the value.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Optional

from .config import SECRET_TOKENS


def _is_secret_key(key: str) -> bool:
    up = key.upper()
    return any(tok in up for tok in SECRET_TOKENS)


def mask(key: str, value: str) -> str:
    """Return a display-safe representation of ``value`` for ``key``.

    Sensitive keys are fully redacted; everything else is returned unchanged.
    """
    if value is None:
        return ""
    if _is_secret_key(key):
        return "********" if value else ""
    return value


def load_env(env_path: Optional[Path] = None) -> Dict[str, bool]:
    """Load environment variables from a .env file if present.

    Returns a dict of ``{key: is_secret}`` describing which keys were loaded --
    never the values. Existing process env vars are not overwritten.
    """
    loaded: Dict[str, bool] = {}
    path = Path(env_path) if env_path else _find_env()
    if not path or not path.exists():
        return loaded

    try:
        from dotenv import dotenv_values  # type: ignore

        values = dotenv_values(str(path))
    except Exception:
        values = _parse_env(path)

    for key, value in values.items():
        if key and key not in os.environ and value is not None:
            os.environ[key] = value
        if key:
            loaded[key] = _is_secret_key(key)
    return loaded


def _find_env() -> Optional[Path]:
    """Look for a .env next to the app, in the CWD, or a parent."""
    here = Path(__file__).resolve().parent
    candidates = [here / ".env", here.parent / ".env", Path.cwd() / ".env"]
    for c in candidates:
        if c.exists():
            return c
    return None


def _parse_env(path: Path) -> Dict[str, str]:
    """Minimal KEY=VALUE parser used when python-dotenv is unavailable."""
    out: Dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key:
            out[key] = val
    return out


def safe_env_summary(keys: Dict[str, bool]) -> Dict[str, str]:
    """Presence-only summary for display: ``{key: 'set'|'not set'}``.

    Values are never included -- this is the only env view the UI should show.
    """
    summary: Dict[str, str] = {}
    for key in keys:
        summary[key] = "set" if os.environ.get(key) else "not set"
    return summary
