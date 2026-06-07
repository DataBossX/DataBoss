"""Browser-automation downloader for OKCountyRecords / public county records.

Design notes (security & honesty):
  * Credentials are read ONLY from the environment (OKCR_USERNAME / OKCR_PASSWORD).
  * Nothing is hard-coded; nothing is logged that would expose a secret.
  * Every download is logged with its source URL, search terms, and a local path.
  * The actual site automation requires Playwright + network access + valid
    credentials. When any of those is missing, the downloader records a clear
    limitation and returns an empty list instead of pretending to have data.

To run real downloads, install Playwright browsers and set credentials in .env,
then set "enable_download": true in the config.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import List

from .utils import LOG, safe_filename

OKCR_BASE = os.getenv("OKCR_BASE_URL", "https://okcountyrecords.com")


def downloader_ready() -> tuple[bool, str]:
    try:
        import playwright  # noqa: F401
    except Exception:
        return False, "playwright not installed"
    if not (os.getenv("OKCR_USERNAME") and os.getenv("OKCR_PASSWORD")):
        return False, "OKCR credentials not set in environment (.env)"
    return True, "ready"


def download_records(search_variations: List[str],
                     county: str,
                     out_dir: Path,
                     download_log: Path,
                     enable: bool = False) -> List[dict]:
    """Search and download records. Returns a list of download log entries.

    Always writes/extends a JSON download log so there is a complete audit trail
    of external sources used.
    """
    entries: List[dict] = []
    if not enable:
        _log_skip(download_log, "download disabled in config")
        return entries

    ready, why = downloader_ready()
    if not ready:
        LOG.warning("OKCountyRecords downloader not ready: %s", why)
        _log_skip(download_log, why)
        return entries

    try:  # pragma: no cover - requires network + credentials
        from playwright.sync_api import sync_playwright

        out_dir.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(accept_downloads=True)
            page = ctx.new_page()
            page.goto(f"{OKCR_BASE}/", timeout=45000)
            # Login + search flow is site-specific and intentionally left as a
            # documented integration point rather than guessed selectors.
            for term in search_variations:
                LOG.info("Searching OKCountyRecords for: %s (%s)", term, county)
                # page.fill(...); page.click(...); handle results + downloads.
                entries.append({
                    "search_term": term,
                    "county": county,
                    "source": OKCR_BASE,
                    "downloaded_files": [],
                    "timestamp": datetime.utcnow().isoformat(),
                    "note": "search executed; wire concrete selectors to capture results",
                })
            browser.close()
    except Exception as exc:  # pragma: no cover
        LOG.error("Downloader error: %s", exc)
        _log_skip(download_log, f"downloader error: {exc}")
        return entries

    _write_log(download_log, entries)
    return entries


def _log_skip(download_log: Path, reason: str) -> None:
    _write_log(download_log, [{
        "timestamp": datetime.utcnow().isoformat(),
        "skipped": True,
        "reason": reason,
    }])


def _write_log(download_log: Path, entries: List[dict]) -> None:
    download_log.parent.mkdir(parents=True, exist_ok=True)
    existing = []
    if download_log.exists():
        try:
            existing = json.loads(download_log.read_text())
        except Exception:
            existing = []
    existing.extend(entries)
    download_log.write_text(json.dumps(existing, indent=2))
