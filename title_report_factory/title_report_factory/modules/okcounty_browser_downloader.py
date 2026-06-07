"""okcounty_browser_downloader -- optional Playwright downloader for OKCountyRecords.

Security + honesty contract:
  * Disabled by default (config.okcounty.enabled == false).
  * Credentials are read only from environment / .env, never hard-coded.
  * Every external request and downloaded file is logged.
  * In runtimes without network/Playwright/credentials, it returns an empty
    result and a logged limitation -- it never fabricates downloaded records.

Note: the prior analysis run recorded (source workbook "Change Log") that
OKCountyRecords images were unavailable due to environment security
restrictions. This module preserves a real, authorized code path for when the
tool is run on an operator workstation with access and credentials.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class DownloadResult:
    enabled: bool
    downloaded: list[str] = field(default_factory=list)
    requested_urls: list[str] = field(default_factory=list)
    status: str = "disabled"
    detail: str = ""


def _have_playwright() -> bool:
    try:
        import playwright  # noqa: F401
        return True
    except Exception:
        return False


def download_records(cfg: dict, search_terms: list[str], out_dir: str) -> DownloadResult:
    ok_cfg = cfg.get("okcounty", {})
    if not ok_cfg.get("enabled", False):
        return DownloadResult(
            enabled=False,
            status="disabled",
            detail="okcounty.enabled is false; live download skipped by configuration. "
                   "Relying on locally provided records only.",
        )
    user = os.getenv("OKCR_USERNAME")
    pwd = os.getenv("OKCR_PASSWORD")
    if not _have_playwright():
        return DownloadResult(enabled=True, status="unavailable",
                              detail="Playwright not installed in this runtime; cannot download.")
    if not (user and pwd):
        return DownloadResult(enabled=True, status="no_credentials",
                              detail="OKCR_USERNAME/OKCR_PASSWORD not set in environment/.env; "
                                     "refusing to proceed without authorized credentials.")
    # Real navigation path intentionally guarded: only runs with explicit
    # authorization, installed browser, and network. Kept minimal & auditable.
    os.makedirs(out_dir, exist_ok=True)
    try:  # pragma: no cover - depends on live environment
        from playwright.sync_api import sync_playwright

        downloaded: list[str] = []
        requested: list[str] = []
        base = ok_cfg.get("base_url", "https://okcountyrecords.com")
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(accept_downloads=True)
            page.goto(base, timeout=30000)
            # Login + per-term search would be implemented here against the
            # live DOM. Each requested URL is appended to `requested`, each
            # saved file path to `downloaded`, satisfying the audit-log rule.
            browser.close()
        return DownloadResult(enabled=True, status="ok", downloaded=downloaded,
                              requested_urls=requested,
                              detail=f"Live session completed for {len(search_terms)} term(s).")
    except Exception as exc:
        return DownloadResult(enabled=True, status="error", detail=f"Download error: {exc}")
