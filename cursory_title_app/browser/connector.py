"""Connect to the user's ALREADY-OPEN, logged-in Chrome/Edge over CDP.

We do NOT launch a fresh hidden browser and we do NOT touch the user's
credentials. The user starts their own Chrome with remote debugging enabled:

    chrome.exe --remote-debugging-port=9222 --user-data-dir="%LOCALAPPDATA%\\CTA\\chrome"

(or reuse their normal profile at their own discretion). Then this attaches to
that visible session via Playwright's connect_over_cdp. The human can take over
the same window at any time — manual takeover is just "use the window".
"""
from __future__ import annotations

from contextlib import contextmanager

from .. import config
from ..db import store


class BrowserSession:
    def __init__(self, cdp_url: str = config.CDP_URL):
        self.cdp_url = cdp_url
        self._pw = None
        self.browser = None
        self.context = None

    def connect(self):
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        # Attach to the visible, user-controlled browser.
        self.browser = self._pw.chromium.connect_over_cdp(self.cdp_url)
        if not self.browser.contexts:
            raise RuntimeError(
                "Connected to CDP but found no open browser context. "
                "Make sure Chrome/Edge is running with --remote-debugging-port "
                f"matching {self.cdp_url}, and you are logged in."
            )
        self.context = self.browser.contexts[0]
        store.audit("browser_connected", self.cdp_url)
        return self

    def new_page(self):
        if self.context is None:
            raise RuntimeError("Not connected. Call connect() first.")
        return self.context.new_page()

    def close(self):
        # We DO NOT close the user's browser. Only detach Playwright.
        try:
            if self._pw:
                self._pw.stop()
        finally:
            self.browser = None
            self.context = None
            self._pw = None
        store.audit("browser_detached", self.cdp_url)


@contextmanager
def session(cdp_url: str = config.CDP_URL):
    s = BrowserSession(cdp_url).connect()
    try:
        yield s
    finally:
        s.close()
