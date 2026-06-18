"""
browser_viewer.py
=================
Controlled Playwright browser session for opening county-record preview
pages, clicking the "View" control, waiting for the real document to render,
and capturing the document image(s) IN MEMORY.

Nothing is written to disk unless debug_save_screenshots=true in config.

Public API:
    with BrowserViewer(config) as viewer:
        if not viewer.login_valid():
            ... tell user to rerun login setup ...
        result = viewer.capture_document(url)
        # result.images -> List[bytes] (PNG), result.method, result.error
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import List, Optional

log = logging.getLogger("horizon.browser")


@dataclass
class CaptureResult:
    images: List[bytes] = field(default_factory=list)
    method: str = ""
    error: str = ""
    login_expired: bool = False

    @property
    def ok(self) -> bool:
        return bool(self.images) and not self.error


# Text that usually indicates we were bounced back to a login screen.
LOGIN_HINTS = [
    "sign in",
    "log in",
    "login",
    "username",
    "password",
    "session expired",
    "your session has expired",
    "please authenticate",
    "not authorized",
]

# Ordered list of strategies to find the "View" control.
VIEW_TEXTS = ["View", "View Image", "View Document", "View Doc", "Open", "Image"]


class BrowserViewer:
    def __init__(self, config: dict):
        self.config = config
        self.headless = bool(config.get("browser_headless", False))
        self.auth_state_path = config.get("auth_state_path", ".auth/county_state.json")
        self.timeout_ms = int(config.get("timeout_seconds", 45)) * 1000
        self.max_pages = int(config.get("max_pages_per_document", 3))
        self.debug_save = bool(config.get("debug_save_screenshots", False))
        self._pw = None
        self._browser = None
        self._context = None

    # -- context management --------------------------------------------------
    def __enter__(self) -> "BrowserViewer":
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=self.headless)
        kwargs = {"viewport": {"width": 1600, "height": 1200}}
        if os.path.exists(self.auth_state_path):
            kwargs["storage_state"] = self.auth_state_path
        else:
            log.warning("No auth state at %s - county login likely required.", self.auth_state_path)
        self._context = self._browser.new_context(**kwargs)
        self._context.set_default_timeout(self.timeout_ms)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        for closer in (self._context, self._browser):
            try:
                if closer:
                    closer.close()
            except Exception:
                pass
        try:
            if self._pw:
                self._pw.stop()
        except Exception:
            pass

    # -- login state ---------------------------------------------------------
    def login_valid(self) -> bool:
        """Best-effort check that an auth state file exists."""
        return os.path.exists(self.auth_state_path)

    def _looks_like_login(self, page) -> bool:
        try:
            body = (page.content() or "").lower()
        except Exception:
            return False
        # Require at least two hints to reduce false positives.
        hits = sum(1 for h in LOGIN_HINTS if h in body)
        has_pw_field = False
        try:
            has_pw_field = page.locator("input[type='password']").count() > 0
        except Exception:
            pass
        return has_pw_field and hits >= 1

    # -- main entry ----------------------------------------------------------
    def capture_document(self, url: str, tag: str = "") -> CaptureResult:
        result = CaptureResult()

        # 0. If the link itself is a direct image/PDF, fetch its bytes directly.
        direct = self._fetch_direct(url)
        if direct is not None:
            result.images = [direct]
            result.method = "direct-url"
            self._maybe_debug_save(result.images, tag)
            return result

        page = self._context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded")
            self._wait_idle(page)

            if self._looks_like_login(page):
                result.login_expired = True
                result.error = "login expired"
                return result

            # Click the View control (may open same-tab nav or a popup).
            target_page, method = self._click_view(page)
            result.method = method
            self._wait_idle(target_page)

            # If the View click navigated straight to an image/PDF, grab it.
            direct = self._fetch_direct(target_page.url)
            if direct is not None:
                result.images = [direct]
                result.method = f"{method}->direct-image"
                self._maybe_debug_save(result.images, tag)
                return result

            # Otherwise capture from whatever viewer surfaced.
            images, cap_method = self._capture_from(target_page)
            if images:
                result.images = images
                result.method = f"{method}->{cap_method}"
                self._maybe_debug_save(result.images, tag)
            else:
                result.error = "no document content found after View click"
            return result
        except Exception as exc:  # continue-after-failure philosophy
            log.exception("capture_document failed for %s", url)
            result.error = f"{type(exc).__name__}: {exc}"
            return result
        finally:
            try:
                page.close()
            except Exception:
                pass

    def _fetch_direct(self, url: str) -> Optional[bytes]:
        """If the URL points straight at an image, return its bytes (reuses the
        authenticated session). PDFs are left to the viewer screenshot path."""
        if not url:
            return None
        low = url.split("?")[0].lower()
        if not low.endswith((".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff")):
            return None
        try:
            resp = self._context.request.get(url, timeout=self.timeout_ms)
            if resp.ok:
                ctype = (resp.headers or {}).get("content-type", "")
                if "image" in ctype or low.endswith((".tif", ".tiff")):
                    return resp.body()
        except Exception as exc:
            log.debug("direct image fetch failed: %s", exc)
        return None

    def _maybe_debug_save(self, images: List[bytes], tag: str) -> None:
        """Persist captured images ONLY when debug_save_screenshots is on."""
        if not self.debug_save or not images:
            return
        debug_dir = os.path.join(os.getcwd(), "debug")
        try:
            os.makedirs(debug_dir, exist_ok=True)
            stamp = time.strftime("%Y%m%d_%H%M%S")
            safe = "".join(c if c.isalnum() else "_" for c in (tag or "doc"))[:40]
            for i, img in enumerate(images):
                with open(os.path.join(debug_dir, f"{stamp}_{safe}_p{i+1}.png"), "wb") as fh:
                    fh.write(img)
        except Exception as exc:
            log.debug("debug screenshot save failed: %s", exc)

    # -- helpers -------------------------------------------------------------
    def _wait_idle(self, page) -> None:
        try:
            page.wait_for_load_state("networkidle", timeout=self.timeout_ms)
        except Exception:
            # networkidle can time out on streaming viewers; that's fine.
            try:
                page.wait_for_load_state("load", timeout=5000)
            except Exception:
                pass
        time.sleep(0.5)

    def _click_view(self, page):
        """Try a series of selectors to find and click the View control.

        Returns (page_or_popup, method_str). The returned page is whichever
        surface holds the document (same tab or a new popup tab).
        """
        from playwright.sync_api import TimeoutError as PWTimeout

        strategies = []

        # 1. role=link named View
        for name in VIEW_TEXTS:
            strategies.append(
                (f"role-link:{name}", lambda n=name: page.get_by_role("link", name=n, exact=False).first)
            )
        # 2. role=button named View
        for name in VIEW_TEXTS:
            strategies.append(
                (f"role-button:{name}", lambda n=name: page.get_by_role("button", name=n, exact=False).first)
            )
        # 3. plain text View
        for name in VIEW_TEXTS:
            strategies.append(
                (f"text:{name}", lambda n=name: page.get_by_text(n, exact=False).first)
            )
        # 4. title*=View
        strategies.append(("title*=View", lambda: page.locator("[title*='View' i]").first))
        # 5. alt*=View
        strategies.append(("alt*=View", lambda: page.locator("[alt*='View' i]").first))
        # 6. thumbnail image near text View
        strategies.append(
            ("thumb-near-View", lambda: page.locator("a:has(img), button:has(img)").first)
        )
        # 7. any anchor/button/image inside a result row
        strategies.append(
            (
                "result-row-link",
                lambda: page.locator(
                    "tr a, .result a, .results a, [class*='row'] a, a[href]"
                ).first,
            )
        )

        for method, locator_fn in strategies:
            try:
                loc = locator_fn()
                if loc.count() == 0:
                    continue
                if not loc.is_visible():
                    continue
            except Exception:
                continue

            # Try the click while watching for a popup.
            try:
                with self._context.expect_page(timeout=4000) as popup_info:
                    loc.click()
                popup = popup_info.value
                popup.wait_for_load_state("domcontentloaded", timeout=self.timeout_ms)
                return popup, f"popup:{method}"
            except PWTimeout:
                # No popup; assume same-tab navigation or in-place reveal.
                return page, f"sametab:{method}"
            except Exception as exc:
                log.debug("View strategy %s failed: %s", method, exc)
                continue

        # Nothing matched - maybe the document is already shown.
        return page, "no-view-control"

    def _capture_from(self, page):
        """Capture document content from the current page/viewer.

        Capture priority:
          1. iframe viewer
          2. <img> document element (largest)
          3. <canvas> viewer
          4. viewer container element
          5. full page
        Returns (List[bytes], method).
        """
        # Give viewers a moment to render.
        time.sleep(1.0)
        self._try_fit_width(page)

        # 1. iframe viewer
        try:
            frames = [f for f in page.frames if f != page.main_frame]
            for fr in frames:
                imgs = self._capture_images_in(fr)
                if imgs:
                    return imgs[: self.max_pages], "iframe-image"
        except Exception:
            pass

        # 2. large <img> in main page
        imgs = self._capture_images_in(page)
        if imgs:
            return imgs[: self.max_pages], "image-element"

        # 3. canvas viewer
        try:
            canvases = page.locator("canvas")
            if canvases.count() > 0:
                shots = []
                for i in range(min(canvases.count(), self.max_pages)):
                    c = canvases.nth(i)
                    if c.is_visible():
                        shots.append(c.screenshot())
                if shots:
                    return shots, "canvas"
        except Exception:
            pass

        # 4. viewer container
        for sel in [
            "[class*='viewer']",
            "[id*='viewer']",
            "[class*='document']",
            "[class*='preview']",
            "embed",
            "object",
        ]:
            try:
                loc = page.locator(sel).first
                if loc.count() > 0 and loc.is_visible():
                    return [loc.screenshot()], f"container:{sel}"
            except Exception:
                continue

        # 5. full page fallback
        try:
            return [page.screenshot(full_page=True)], "full-page"
        except Exception as exc:
            log.warning("full-page screenshot failed: %s", exc)
            return [], "none"

    def _capture_images_in(self, frame_or_page) -> List[bytes]:
        """Screenshot the largest visible <img> elements (document scans)."""
        shots: List[bytes] = []
        try:
            images = frame_or_page.locator("img")
            count = min(images.count(), 20)
            sized = []
            for i in range(count):
                img = images.nth(i)
                try:
                    if not img.is_visible():
                        continue
                    box = img.bounding_box()
                    if not box:
                        continue
                    area = box["width"] * box["height"]
                    # Ignore tiny icons / spacers.
                    if box["width"] >= 250 and box["height"] >= 250:
                        sized.append((area, img))
                except Exception:
                    continue
            sized.sort(key=lambda t: t[0], reverse=True)
            for _, img in sized[: self.max_pages]:
                try:
                    shots.append(img.screenshot())
                except Exception:
                    continue
        except Exception:
            pass
        return shots

    def _try_fit_width(self, page) -> None:
        """If a zoom/fit control exists, click it for readability."""
        for name in ["Fit width", "Fit Width", "Fit to width", "Zoom to fit", "Fit"]:
            try:
                loc = page.get_by_role("button", name=name, exact=False).first
                if loc.count() > 0 and loc.is_visible():
                    loc.click()
                    time.sleep(0.4)
                    return
            except Exception:
                continue


# ---------------------------------------------------------------------------
# Login setup (called by RUN_LOGIN_SETUP.bat)
# ---------------------------------------------------------------------------


def run_login_setup(config: dict) -> bool:
    """Open a visible browser, let the user log in, then save storage state."""
    from playwright.sync_api import sync_playwright

    auth_path = config.get("auth_state_path", ".auth/county_state.json")
    os.makedirs(os.path.dirname(auth_path) or ".", exist_ok=True)

    print("\nOpening browser. Log into the county records site, then return here.\n")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context(viewport={"width": 1500, "height": 1000})
        page = context.new_page()
        page.goto("about:blank")
        page.set_content(
            "<h2 style='font-family:sans-serif'>HorizonTitleLinkExtractor login setup</h2>"
            "<p style='font-family:sans-serif'>Navigate to your county records website and log in. "
            "When you can see search results, return to the command window and press ENTER.</p>"
        )
        try:
            input("After you finish logging in, press ENTER here to save your session... ")
        except (EOFError, KeyboardInterrupt):
            pass
        try:
            context.storage_state(path=auth_path)
            print(f"\nSaved login session to {auth_path}")
            ok = True
        except Exception as exc:
            print(f"\n[ERROR] Could not save login session: {exc}")
            ok = False
        context.close()
        browser.close()
    return ok
