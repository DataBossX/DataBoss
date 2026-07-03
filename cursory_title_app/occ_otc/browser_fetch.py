"""Open the OCC/OTC well & production lookups in YOUR connected browser and
capture the pages into the evidence store.

These are portal sources (no API key), so this reuses the CDP browser connector:
it opens each target in your already-logged-in Chrome, captures a full-page
screenshot + page text, and pauses for manual takeover on login/CAPTCHA. You
still read the result (production continuity, form values) — the tool stages the
evidence and records where each fact came from; it never concludes HBP for you.

Run on YOUR machine (portals are egress-blocked from the cloud prep box):
    chrome.exe --remote-debugging-port=9222   (log into OCC/OTC as needed)
    python -m cursory_title_app.occ_otc.browser_fetch            # opens + captures
    python -m cursory_title_app.occ_otc.browser_fetch --list     # just show targets
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .. import config
from ..db import store

TARGETS = Path(__file__).with_name("targets.json")


def load() -> dict:
    return json.loads(TARGETS.read_text())


def targets_flat() -> list[dict]:
    data = load()
    out = []
    for src in ("occ", "otc"):
        for t in data.get(src, []):
            out.append({**t, "_source": src})
    return out


def run(dry_run: bool = False) -> dict:
    data = load()
    well = data["_meta"]["well"]
    items = targets_flat()
    if dry_run:
        return {"well": well, "targets": items}

    from ..browser.connector import session
    from ..browser import doc_worker

    config.ensure_dirs()
    store.init()
    results = []
    with session(config.CDP_URL) as s:
        for i, t in enumerate(items, 1):
            qid = store.upsert_queue({
                "dedup_key": f"occotc::{t['_source']}::{i}",
                "source": t["_source"], "doc_type": t["label"],
                "document_url": t["portal_url"], "status": "pending",
                "diff_kind": "well_production",
            }) or 0
            print(f"  [{i}/{len(items)}] {t['label']} — search: {t['search_for']}")
            try:
                cap = doc_worker.capture_document(s, t["portal_url"], qid)
                status = "takeover" if cap.get("takeover") else "captured"
                store.execute("UPDATE work_queue SET status=? WHERE id=?", (status, qid))
                results.append({"label": t["label"], "status": status,
                                "screenshot": cap.get("screenshot"),
                                "search_for": t["search_for"],
                                "captures": t["captures"]})
                if cap.get("takeover"):
                    print("     -> login/CAPTCHA detected; take over the window, "
                          "search for the API/PUN, then re-run to capture the result page.")
            except Exception as e:
                store.audit("occotc_error", f"{t['label']}: {e}")
                results.append({"label": t["label"], "status": "error", "error": str(e)})
    return {"well": well, "results": results,
            "note": "Read each captured page. HBP and completion facts go into the "
                    "workbook via the normal review/reimport flow; they are legal/"
                    "engineering conclusions reserved to the examiner."}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="show targets, open nothing")
    a = ap.parse_args()
    res = run(dry_run=a.list)
    print(json.dumps(res, indent=2, default=str))


if __name__ == "__main__":
    main()
