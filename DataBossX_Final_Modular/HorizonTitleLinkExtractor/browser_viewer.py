"""
browser_viewer.py
=================
Controlled Playwright browser session for county-record document viewing.

Responsibilities:
  * Open a preview URL using saved login state (.auth/county_state.json).
  * Detect expired login and stop the run safely.
  * Find and click the "View" control (multiple selector strategies).
  * Follow same-tab navigation, popups/new tabs, iframe/image/canvas/PDF viewers.
  * Capture up to max_pages_per_document screenshots IN MEMORY.
  * Only write images to disk when debug_save_screenshots is true.

This module never permanently saves county document images by default.
"""

from __future__ import annotations

import logging
import os
import re
from contextlib import contextmanager
from typing import Any

from playwright.sync_api import (
    Browser,
    BrowserContext,
    Page,
    TimeoutError as PWTimeoutError,
    sync_playwright,
)

log = logging.getLogger("horizon.browser")


class LoginExpiredError(RuntimeError):
    """Raised when the saved county login is no longer valid."""


# Heuristic markers that a login/SSO page is being shown instead of records.
_LOGIN_MARKERS = re.compile(
    r"(sign[\s-]?in|log[\s-]?in|password|username|session (?:expired|timed out)|"
    r"please authenticate|your session has)",
    re.I,
)

# "View" control selector strategies, tried in order.
_VIEW_TEXT = re.compile(r"view", re.I)


class BrowserViewer:
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.headless = bool(config.get("browser_headless", False))
        self.auth_state_path = config.get("auth_state_path", ".auth/county_state.json")
        self.timeout_ms = int(config.get("timeout_seconds", 45)) * 1000
        self.max_pages = int(config.get("max_pages_per_document", 3))
        self.debug_save = bool(config.get("debug_save_screenshots", False))
        self.debug_dir = config.get("debug_dir", "debug")

        self._pw = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    # --- lifecycle ---------------------------------------------------------
    def __enter__(self) -> "BrowserViewer":
        self.start()
        return self

    def __exit__(self, *exc) -> None:
        self.stop()

    def start(self) -> None:
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=self.headless)
        storage = (self.auth_state_path
                   if os.path.exists(self.auth_state_path) else None)
        if storage is None:
            log.warning("No saved auth state at %s - county pages may require login.",
                        self.auth_state_path)
        self._context = self._browser.new_context(
            storage_state=storage,
            viewport={"width": 1600, "height": 1200},
        )
        self._context.set_default_timeout(self.timeout_ms)

    def stop(self) -> None:
        for closer in (self._context, self._browser):
            try:
                if closer:
                    closer.close()
            except Exception:  # best-effort teardown
                pass
        try:
            if self._pw:
                self._pw.stop()
        except Exception:
            pass
        self._context = self._browser = self._pw = None

    # --- login detection ---------------------------------------------------
    def _looks_like_login(self, page: Page) -> bool:
        try:
            if page.locator("input[type=password]").count() > 0:
                return True
            body = (page.inner_text("body", timeout=3000) or "")[:4000]
        except Exception:
            return False
        return bool(_LOGIN_MARKERS.search(body)) and "grantor" not in body.lower()

    # --- View control discovery -------------------------------------------
    def _find_view_control(self, page: Page):
        """Return a clickable Locator for the document 'View' control, or None."""
        strategies = [
            lambda: page.get_by_role("link", name=_VIEW_TEXT),
            lambda: page.get_by_role("button", name=_VIEW_TEXT),
            lambda: page.get_by_text(_VIEW_TEXT),
            lambda: page.locator("[title*=View i]"),
            lambda: page.locator("[alt*=View i]"),
            lambda: page.locator("a:has(img), button:has(img)").first,
            lambda: page.locator(
                "tr:has-text('View') a, tr:has-text('View') img, "
                "tr:has-text('View') button").first,
        ]
        for build in strategies:
            try:
                loc = build()
                if loc.count() > 0 and loc.first.is_visible():
                    return loc.first
            except Exception:
                continue
        return None

    # --- capture helpers ---------------------------------------------------
    def _maybe_fit_width(self, page: Page) -> None:
        """Best-effort: click any zoom/fit-width control to make text readable."""
        for sel in ('[title*="fit" i]', '[aria-label*="fit" i]',
                    'button:has-text("Fit")', '[title*="zoom in" i]'):
            try:
                ctrl = page.locator(sel)
                if ctrl.count() and ctrl.first.is_visible():
                    ctrl.first.click(timeout=2000)
                    page.wait_for_timeout(400)
                    return
            except Exception:
                continue

    def _capture_target(self, page: Page) -> bytes | None:
        """
        Capture the most specific readable element available, in priority order:
          viewer image element -> viewer container -> canvas -> full page.
        Returns PNG bytes (in memory) or None.
        """
        selectors = [
            "img#viewerImage", "img.document-image", "img.viewer-image",
            "iframe >> img", "#viewer img", ".viewer img",
            "embed[type='application/pdf']", "iframe[src*='pdf']",
            "canvas", "#viewer", ".viewer", ".document-viewer",
        ]
        for sel in selectors:
            try:
                loc = page.locator(sel).first
                if loc.count() and loc.is_visible():
                    return loc.screenshot()
            except Exception:
                continue
        # Fallbacks: iframe content, then full page.
        try:
            for frame in page.frames:
                if frame == page.main_frame:
                    continue
                try:
                    img = frame.locator("img, canvas").first
                    if img.count() and img.is_visible():
                        return img.screenshot()
                except Exception:
                    continue
        except Exception:
            pass
        try:
            return page.screenshot(full_page=True)
        except Exception:
            return None

    def _wait_for_document(self, page: Page) -> None:
        """Wait until real document content (image/canvas/pdf/iframe) is present."""
        try:
            page.wait_for_load_state("networkidle", timeout=self.timeout_ms)
        except PWTimeoutError:
            pass
        candidates = ("img", "canvas", "iframe", "embed",
                      "[class*='viewer']", "[id*='viewer']")
        for sel in candidates:
            try:
                page.wait_for_selector(sel, timeout=4000, state="visible")
                return
            except PWTimeoutError:
                continue

    def _debug_dump(self, idx: int, row: Any, png: bytes) -> None:
        if not (self.debug_save and png):
            return
        try:
            os.makedirs(self.debug_dir, exist_ok=True)
            path = os.path.join(self.debug_dir, f"row{row}_page{idx}.png")
            with open(path, "wb") as fh:
                fh.write(png)
            log.debug("debug screenshot written: %s", path)
        except Exception as exc:
            log.warning("debug dump failed: %s", exc)

    # --- public API --------------------------------------------------------
    @contextmanager
    def _expect_target(self, control, page: Page):
        """
        Click the View control, transparently handling same-tab nav vs popup.
        Yields the page that holds the document.
        """
        popup_page: Page | None = None
        try:
            with page.expect_popup(timeout=4000) as pop:
                control.click()
            popup_page = pop.value
        except Exception:
            popup_page = None
        target = popup_page or page
        try:
            target.wait_for_load_state("domcontentloaded", timeout=self.timeout_ms)
        except Exception:
            pass
        yield target

    def capture_document(self, url: str, row_id: Any = "?") -> dict[str, Any]:
        """
        Open the preview URL, click View, and capture document pages in memory.

        Returns:
          {"images": [png_bytes, ...], "viewer_method": str, "ok": bool,
           "error": str|None}

        Raises LoginExpiredError if the saved login is no longer valid.
        """
        assert self._context is not None, "BrowserViewer not started"
        page = self._context.new_page()
        result: dict[str, Any] = {"images": [], "viewer_method": "none",
                                  "ok": False, "error": None}
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)
            try:
                page.wait_for_load_state("networkidle", timeout=8000)
            except PWTimeoutError:
                pass

            if self._looks_like_login(page):
                raise LoginExpiredError(
                    "County login appears expired. Re-run RUN_LOGIN_SETUP.bat.")

            control = self._find_view_control(page)
            if control is None:
                # Maybe the document is already shown without a View click.
                self._wait_for_document(page)
                png = self._capture_target(page)
                if png:
                    result.update(images=[png], viewer_method="direct_no_view",
                                  ok=True)
                    self._debug_dump(0, row_id, png)
                else:
                    result["error"] = "No View control and no document content found."
                return result

            with self._expect_target(control, page) as target:
                self._wait_for_document(target)
                self._maybe_fit_width(target)
                result["viewer_method"] = self._classify_viewer(target)

                first = self._capture_target(target)
                if first:
                    result["images"].append(first)
                    self._debug_dump(0, row_id, first)

                for idx in range(1, self.max_pages):
                    if not self._go_next_page(target):
                        break
                    target.wait_for_timeout(600)
                    png = self._capture_target(target)
                    if not png:
                        break
                    result["images"].append(png)
                    self._debug_dump(idx, row_id, png)

            result["ok"] = bool(result["images"])
            if not result["ok"]:
                result["error"] = "Document content was not readable."
            return result

        except LoginExpiredError:
            raise
        except PWTimeoutError as exc:
            result["error"] = f"Timeout: {exc}"
            return result
        except Exception as exc:  # continue after failures
            result["error"] = f"{type(exc).__name__}: {exc}"
            return result
        finally:
            try:
                page.close()
            except Exception:
                pass

    def _classify_viewer(self, page: Page) -> str:
        for sel, name in (("canvas", "canvas"),
                          ("embed[type='application/pdf'],iframe[src*='pdf']", "pdf"),
                          ("iframe", "iframe"),
                          ("img", "image")):
            try:
                if page.locator(sel).first.count():
                    return name
            except Exception:
                continue
        return "page"

    def _go_next_page(self, page: Page) -> bool:
        for sel in ('[title*="next" i]', '[aria-label*="next" i]',
                    'button:has-text("Next")', 'a:has-text("Next")'):
            try:
                ctrl = page.locator(sel).first
                if ctrl.count() and ctrl.is_visible():
                    ctrl.click(timeout=2000)
                    return True
            except Exception:
                continue
        return False


# -----------------------------------------------------------------------------
# Login setup helper (used by RUN_LOGIN_SETUP.bat)
# -----------------------------------------------------------------------------
def run_login_setup(auth_state_path: str = ".auth/county_state.json") -> None:
    """
    Open a visible Chromium window, let the user log into the county-records site,
    then save storage state to auth_state_path when the window is closed.
    """
    os.makedirs(os.path.dirname(auth_state_path) or ".", exist_ok=True)
    print("=" * 70)
    print(" COUNTY LOGIN SETUP")
    print("=" * 70)
    print(" A browser window will open.")
    print(" 1. Navigate to your county-records site.")
    print(" 2. Log in completely.")
    print(" 3. When you can see records, CLOSE the browser window.")
    print(" Your login cookies will be saved locally to:")
    print(f"   {auth_state_path}")
    print(" WARNING: that file contains login cookies. Keep it local. Never share.")
    print("=" * 70)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context(viewport={"width": 1500, "height": 1000})
        page = context.new_page()
        page.goto("about:blank")
        try:
            # Block until the user closes the page/window.
            page.wait_for_event("close", timeout=0)
        except Exception:
            pass
        try:
            context.storage_state(path=auth_state_path)
            print(f"\nSaved login state to {auth_state_path}")
        except Exception as exc:
            print(f"\nCould not save login state: {exc}")
        finally:
            try:
                context.close()
                browser.close()
            except Exception:
                pass
