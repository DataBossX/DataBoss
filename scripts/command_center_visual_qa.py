#!/usr/bin/env python3
"""Visual QA for the Command Center PWA.

Drives a real headless Chromium over the DevTools Protocol (see
``cdp_client.py`` -- Playwright cannot be installed here, so CDP is spoken
directly). Every check loads the actual page, measures the actual layout, and
captures a screenshot, so the evidence is a rendered page rather than an
assertion about one.

Checks performed:
  * iPhone SE / 13 / Pro Max, a 320px narrow case, and landscape
  * reduced-motion rendering, and a run with the Command Core disabled
  * horizontal overflow (the body must never scroll sideways)
  * touch-target sizing (44px minimum)
  * the hold banner, bottom nav, push-to-talk, and Best Next Move must all be
    present and visible in every case
  * the withheld Section 32 move must be visible as withheld, not hidden
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cdp_client import HeadlessPage  # noqa: E402

CASES = [
    {"name": "iphone-se", "w": 375, "h": 667},
    {"name": "iphone-13", "w": 390, "h": 844},
    {"name": "iphone-pro-max", "w": 430, "h": 932},
    {"name": "narrow-320", "w": 320, "h": 640},
    {"name": "landscape", "w": 844, "h": 390},
    {"name": "reduced-motion", "w": 390, "h": 844, "reduced": True},
    {"name": "low-power-no-core", "w": 390, "h": 844, "disable_core": True},
]

PROBE = r"""
(() => {
  const doc = document.documentElement;
  const box = (sel) => {
    const n = document.querySelector(sel);
    if (!n) return null;
    const r = n.getBoundingClientRect();
    const cs = getComputedStyle(n);
    return {
      w: Math.round(r.width), h: Math.round(r.height),
      top: Math.round(r.top), left: Math.round(r.left),
      visible: r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none',
      text: (n.innerText || '').trim().slice(0, 120),
    };
  };
  const undersized = [];
  document.querySelectorAll('button, a[href], summary, input').forEach((n) => {
    const r = n.getBoundingClientRect();
    const cs = getComputedStyle(n);
    if (r.width > 0 && r.height > 0 && cs.visibility !== 'hidden'
        && (r.height < 44 || r.width < 24)) {
      undersized.push({ tag: n.tagName, cls: String(n.className).slice(0, 40),
                        w: Math.round(r.width), h: Math.round(r.height) });
    }
  });
  const clipped = [];
  document.querySelectorAll('.six-card, .best-move, .card').forEach((n) => {
    const r = n.getBoundingClientRect();
    if (r.right > window.innerWidth + 1 || r.left < -1) {
      clipped.push({ cls: String(n.className).slice(0, 40),
                     left: Math.round(r.left), right: Math.round(r.right) });
    }
  });
  /* Withheld moves sit inside a collapsed <details>, so innerText is empty by
     design. Read textContent for presence, and separately confirm the count is
     visible in the always-rendered summary -- a hold must never be hidden. */
  const vetoText = (document.querySelector('#vetoMoves') || {}).textContent || '';
  const vetoCountNode = document.querySelector('#vetoCount');
  const vetoCountVisible = !!(vetoCountNode
    && vetoCountNode.getBoundingClientRect().height > 0
    && /\(\s*[1-9]/.test(vetoCountNode.textContent || ''));
  /* The dock sits over scrolling content. If it is not opaque where the
     controls live, card text bleeds through them. */
  const dock = document.querySelector('.ptt-dock');
  const pttRect = document.querySelector('#pttBtn').getBoundingClientRect();
  const hitTarget = document.elementFromPoint(pttRect.left + pttRect.width / 2,
                                              pttRect.top + pttRect.height / 2);
  /* In landscape the dock returns to normal flow and can sit below the fold,
     so the hit test only applies while it is pinned inside the viewport. */
  const dockIsFixed = getComputedStyle(dock).position === 'fixed';
  const pttInViewport = pttRect.top >= 0 && pttRect.bottom <= window.innerHeight;
  const dockHitTestApplies = dockIsFixed && pttInViewport;
  const dockOpaqueUnderButton = !dockHitTestApplies
    || !!(hitTarget && hitTarget.closest('.ptt-dock'));
  const dockBlurred = getComputedStyle(dock).backdropFilter !== 'none';

  /* Elements carrying the `hidden` attribute must actually be invisible.
     An author `display` rule can otherwise beat the UA [hidden] rule. */
  const wronglyVisible = [];
  document.querySelectorAll('[hidden]').forEach((n) => {
    if (getComputedStyle(n).display !== 'none') {
      wronglyVisible.push(n.id || String(n.className).slice(0, 40) || n.tagName);
    }
  });

  return {
    viewport: { w: window.innerWidth, h: window.innerHeight },
    dock_opaque_under_button: dockOpaqueUnderButton,
    dock_blurred: dockBlurred,
    wrongly_visible_hidden_elements: wronglyVisible,
    horizontal_overflow_px: doc.scrollWidth - doc.clientWidth,
    hold_banner: box('#holdBanner'),
    bottom_nav: box('.bottom-nav'),
    ptt: box('#pttBtn'),
    best_move: box('.best-move'),
    best_move_title: (document.querySelector('.best-move h3') || {}).innerText || '',
    core_canvas: box('#commandCore'),
    core_fallback_visible: (() => {
      const n = document.querySelector('#coreFallback');
      return !!(n && !n.hidden);
    })(),
    six_cards: document.querySelectorAll('.six-card').length,
    nav_buttons: document.querySelectorAll('.nav-btn').length,
    veto_mentions_section32: vetoText.toLowerCase().includes('section 32'),
    veto_count_visible: vetoCountVisible,
    undersized_targets: undersized,
    clipped_cards: clipped,
    document_title: document.title,
  };
})()
"""


def run_case(case, url, outdir):
    extra = []
    if case.get("disable_core"):
        # Exercise the same path a device without usable canvas takes.
        extra.append("--disable-accelerated-2d-canvas")

    with HeadlessPage(width=case["w"], height=case["h"],
                      reduced_motion=case.get("reduced", False),
                      extra_flags=extra) as page:
        page.call("Emulation.setDeviceMetricsOverride", {
            "width": case["w"], "height": case["h"],
            "deviceScaleFactor": 2, "mobile": True,
        })
        # Ready means the app has authenticated, fetched posture and moves, and
        # rendered them -- not merely that the document loaded.
        ready = ("document.querySelector('#pttBtn')"
                 " && document.querySelectorAll('.six-card').length === 6"
                 " && document.querySelector('.best-move h3')")

        if case.get("disable_core"):
            # Persisted low-power preference, then reload so boot honours it.
            page.goto(url, settle_seconds=1.0)
            page.wait_for(ready)
            page.evaluate("localStorage.setItem('dbx.core','off')")
            page.goto(url, settle_seconds=1.0)
        else:
            page.goto(url, settle_seconds=1.0)

        if not page.wait_for(ready):
            raise RuntimeError("app did not become ready within the timeout")

        data = page.evaluate(PROBE)
        shot = os.path.join(outdir, f"{case['name']}.png")
        data["screenshot_bytes"] = page.screenshot(shot)
        data["screenshot"] = shot
        data["case"] = case["name"]
        data["reduced_motion"] = case.get("reduced", False)
        data["core_disabled"] = case.get("disable_core", False)
        return data


def check(data, failures):
    name = data["case"]

    def fail(message):
        failures.append(f"{name}: {message}")

    if data["horizontal_overflow_px"] > 0:
        fail(f"body scrolls horizontally by {data['horizontal_overflow_px']}px")
    if data["screenshot_bytes"] < 5000:
        fail(f"screenshot only {data['screenshot_bytes']} bytes")
    if data["document_title"] != "DataBossX Command Center":
        fail(f"unexpected title {data['document_title']!r}")

    for key in ("hold_banner", "bottom_nav", "ptt", "best_move"):
        node = data.get(key)
        if not node or not node["visible"]:
            fail(f"{key} is missing or not visible")

    banner = data.get("hold_banner") or {}
    if "FOR REVIEW" not in (banner.get("text") or "").upper():
        fail("hold banner does not display the FOR REVIEW / HOLD text")
    if banner.get("top", -1) != 0:
        fail(f"hold banner is not pinned to the top (top={banner.get('top')})")

    if data["six_cards"] != 6:
        fail(f"expected 6 executive cards, found {data['six_cards']}")
    if data["nav_buttons"] != 5:
        fail(f"expected 5 nav buttons, found {data['nav_buttons']}")
    if not data["best_move_title"].strip():
        fail("Best Next Move card has no title")
    if not data["veto_mentions_section32"]:
        fail("withheld Section 32 move is absent from the withheld list")
    if not data["veto_count_visible"]:
        fail("withheld-move count is not visible without expanding a disclosure")
    if not data["dock_opaque_under_button"]:
        fail("push-to-talk control is not the hit target at its own centre")
    if not data["dock_blurred"]:
        fail("push-to-talk dock has no backdrop; page content shows through it")
    if data["wrongly_visible_hidden_elements"]:
        fail("elements marked hidden are still displayed: "
             f"{data['wrongly_visible_hidden_elements']}")
    if data["undersized_targets"]:
        fail(f"{len(data['undersized_targets'])} undersized touch targets: "
             f"{data['undersized_targets'][:3]}")
    if data["clipped_cards"]:
        fail(f"{len(data['clipped_cards'])} clipped cards: {data['clipped_cards'][:3]}")

    if data["core_disabled"]:
        canvas = data.get("core_canvas")
        if not data["core_fallback_visible"] and canvas and canvas["visible"]:
            fail("Command Core fallback did not engage when disabled")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8787/")
    parser.add_argument("--out", default="evidence/command_center/screenshots")
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)
    results, failures = [], []

    for case in CASES:
        # One retry: launching seven browsers in sequence can starve a slow
        # runner, and a harness timeout is not a product defect.
        data = None
        for attempt in (1, 2):
            try:
                data = run_case(case, args.url, args.out)
                break
            except Exception as exc:
                if attempt == 2:
                    failures.append(
                        f"{case['name']}: harness error {type(exc).__name__}: {exc}")
                else:
                    print(f"{case['name']:<20} retrying after {type(exc).__name__}")
                    time.sleep(3)
        if data is None:
            continue
        results.append(data)
        check(data, failures)
        core = "fallback" if data["core_fallback_visible"] else "canvas"
        print(f"{data['case']:<20} {data['viewport']['w']}x{data['viewport']['h']:<5} "
              f"overflow={data['horizontal_overflow_px']:<3} cards={data['six_cards']} "
              f"nav={data['nav_buttons']} core={core:<8} "
              f"shot={data['screenshot_bytes']:>7}B  best='{data['best_move_title'][:32]}'")

    report = {"url": args.url, "cases": results, "failures": failures,
              "passed": not failures, "case_count": len(results)}
    path = os.path.join(args.out, "visual_qa_report.json")
    with open(path, "w") as handle:
        json.dump(report, handle, indent=2)

    print("-" * 78)
    if failures:
        print(f"VISUAL QA FAILED ({len(failures)} finding(s)):")
        for failure in failures:
            print(f"  - {failure}")
    else:
        print(f"VISUAL QA PASSED - {len(results)} viewport cases, 0 findings")
    print(f"report: {path}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
