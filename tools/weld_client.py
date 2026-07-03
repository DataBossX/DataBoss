"""Weld County recorder client — SAFE BY DEFAULT.

Live network fetching is OFF unless explicitly enabled (allow_network=True or
DATABOSSX_ALLOW_NETWORK=1). This prevents accidental hits against the live county
site. All fetched content is treated as UNTRUSTED: it is injection-scanned,
wrapped, and written to quarantine/ — never executed as instructions.

Politeness: a configurable inter-request delay (from settings.toml [site].delay_sec)
and a descriptive User-Agent are enforced on the default fetcher.

For testing and for pluggable transports, a custom `fetcher(url) -> str` may be
injected, bypassing the built-in urllib fetcher (and its network guard).
"""
from __future__ import annotations

import os
import time
import urllib.request
from pathlib import Path
from typing import Callable, Optional

from app.logging_setup import get_logger
from tools import guardrails

ROOT = Path(__file__).resolve().parent.parent
QUARANTINE_DIR = ROOT / "quarantine"

USER_AGENT = "DataBossX/0.1 (title-research; contact: Rodney)"


class NetworkDisabled(RuntimeError):
    """Raised when a live fetch is attempted while network access is disabled."""


class WeldRecorderClient:
    def __init__(
        self,
        base_url: str = "https://weldrecorder.weldgov.com/web/",
        delay_sec: float = 3.5,
        timeout_sec: float = 45,
        allow_network: bool = False,
        fetcher: Optional[Callable[[str], str]] = None,
        quarantine_dir: Optional[Path] = None,
    ) -> None:
        self.base_url = base_url
        self.delay_sec = delay_sec
        self.timeout_sec = timeout_sec
        self.allow_network = allow_network or os.environ.get("DATABOSSX_ALLOW_NETWORK") == "1"
        self.fetcher = fetcher  # injected transport takes precedence over urllib
        self.quarantine_dir = quarantine_dir or QUARANTINE_DIR
        self.log = get_logger("tools.weld_client")
        self._last_request = 0.0

    # --- transport ---------------------------------------------------------
    def _default_fetch(self, url: str) -> str:
        if not self.allow_network:
            raise NetworkDisabled(
                "Live network access is disabled. Set allow_network=True or "
                "DATABOSSX_ALLOW_NETWORK=1 to permit live recorder fetches."
            )
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:  # noqa: S310
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, "replace")

    def _throttle(self) -> None:
        if self.delay_sec <= 0:
            return
        elapsed = time.monotonic() - self._last_request
        if elapsed < self.delay_sec:
            time.sleep(self.delay_sec - elapsed)
        self._last_request = time.monotonic()

    def fetch(self, url: str) -> str:
        self._throttle()
        self.log.info("fetch %s", url)
        return (self.fetcher or self._default_fetch)(url)

    # --- untrusted-safe capture -------------------------------------------
    def fetch_to_quarantine(self, url: str, name: str) -> Path:
        """Fetch *url* and write the wrapped, untrusted content to quarantine/.

        Returns the path written (a _REVIEW_<ts> sibling if the name already
        exists — quarantine files are never overwritten).
        """
        text = self.fetch(url)
        flags = guardrails.scan_for_injection(text)
        self.log.info("quarantine capture %s injection_flags=%d", name, len(flags))
        wrapped = guardrails.wrap_untrusted(text, source=url)
        return guardrails.safe_write(self.quarantine_dir / name, wrapped)
