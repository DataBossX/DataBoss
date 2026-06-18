"""
provenance.py
=============
Production hardening helpers:

  * sha256_file        - integrity hashes for source + review workbooks.
  * append_event       - structured JSONL event log (logs/events.jsonl) that sits
                         alongside the human CSV logs for machine consumption.
  * build_manifest     - a run_manifest.json snapshot (config, versions, hashes,
                         counts, cost, models) so any run is fully reproducible
                         and auditable.
  * redact / scan_file_for_secrets - never let an API key, token, or cookie reach
                         a log or get uploaded. Outputs are scanned before upload
                         and refused if anything secret-shaped is found.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import platform
import re
from typing import Any

__version__ = "2.0.0"

# Keys we must never persist in a manifest/log even if present in the config dict.
_SECRET_CONFIG_KEYS = re.compile(
    r"(key|secret|token|password|cookie|credential)", re.I)

# Secret-shaped patterns. Conservative to avoid flagging ordinary URLs/CSV data.
_SECRET_PATTERNS = {
    "openai_key": re.compile(r"sk-[A-Za-z0-9_\-]{20,}"),
    "anthropic_key": re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"),
    "google_api_key": re.compile(r"AIza[0-9A-Za-z_\-]{30,}"),
    "bearer_token": re.compile(r"Bearer\s+[A-Za-z0-9._\-]{20,}"),
    "private_key_block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "oauth_refresh": re.compile(r"\"refresh_token\"\s*:\s*\"[^\"]{20,}\""),
}


def sha256_file(path: str) -> str | None:
    if not path or not os.path.exists(path):
        return None
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def redact(text: str) -> str:
    """Mask anything secret-shaped in a string before it is logged."""
    out = text
    for pat in _SECRET_PATTERNS.values():
        out = pat.sub("[REDACTED]", out)
    return out


def _redact_config(config: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for k, v in config.items():
        if _SECRET_CONFIG_KEYS.search(k):
            safe[k] = "[REDACTED]"
        elif isinstance(v, str):
            safe[k] = redact(v)
        else:
            safe[k] = v
    return safe


def append_event(path: str, event: dict[str, Any]) -> None:
    """Append one JSON object per line. Values are redacted defensively."""
    event = {**event, "ts": _dt.datetime.now().isoformat(timespec="seconds")}
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(redact(json.dumps(event, default=str)) + "\n")
    except Exception:
        pass  # logging must never crash the run


def scan_file_for_secrets(path: str) -> list[str]:
    """Return the names of secret patterns found in a TEXT file (skips binaries
    like .xlsx). Used to refuse uploading anything sensitive."""
    if not path or not os.path.exists(path):
        return []
    if os.path.splitext(path)[1].lower() in (".xlsx", ".xls", ".png", ".jpg",
                                             ".jpeg", ".pdf", ".zip"):
        return []
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            text = fh.read()
    except Exception:
        return []
    return [name for name, pat in _SECRET_PATTERNS.items() if pat.search(text)]


def safe_upload_list(files: list[str]) -> tuple[list[str], list[tuple[str, list[str]]]]:
    """Split files into (safe_to_upload, blocked) where blocked contains
    (path, [secret_names]). Binary outputs are always considered safe."""
    safe: list[str] = []
    blocked: list[tuple[str, list[str]]] = []
    for f in files:
        if not f or not os.path.exists(f):
            continue
        hits = scan_file_for_secrets(f)
        if hits:
            blocked.append((f, hits))
        else:
            safe.append(f)
    return safe, blocked


def build_manifest(path: str, *, config: dict[str, Any], offline: bool,
                   source_path: str, review_path: str,
                   summary: dict[str, Any], cost_usd: float,
                   models: dict[str, Any], started: str, ended: str,
                   outputs: list[str]) -> str:
    manifest = {
        "tool": "HorizonTitleLinkExtractor",
        "version": __version__,
        "offline_mode": offline,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "started": started,
        "ended": ended,
        "source_workbook": os.path.basename(source_path or ""),
        "source_sha256": sha256_file(source_path),
        "review_workbook": os.path.basename(review_path or ""),
        "review_sha256": sha256_file(review_path),
        "summary": summary,
        "estimated_cost_usd": round(cost_usd, 4),
        "models": models,
        "outputs": [os.path.basename(o) for o in outputs if o],
        "config_snapshot": _redact_config(config),
    }
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, default=str)
    return path
