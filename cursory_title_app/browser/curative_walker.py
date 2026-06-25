"""Walk the 31 curative items through the user's connected browser.

For each item it opens the OKCountyRecords search link in the user's already-
logged-in Chrome (over CDP), captures a full-page screenshot + page text into
the local evidence store, and marks the item for human review. It never bypasses
login/CAPTCHA/paywalls — if it detects one it pauses for manual takeover.

These items NEED a human to identify and pull the right document; the walker
just stages the evidence. It does not auto-fill the workbook.
"""
from __future__ import annotations

import time
from pathlib import Path

from .. import config
from ..db import store
from ..reports.builder import curative_rows


def enqueue_curative(source: Path) -> dict:
    """Load the curative items into the work queue (idempotent by dedup_key)."""
    store.init()
    rows = curative_rows(source)
    added = 0
    for i, row in enumerate(rows):
        dkey = f"curative::{row['tract']}::{(row['owner'] or '')[:30]}::{i}"
        store.upsert_queue({
            "dedup_key": dkey,
            "source": "curative",
            "runsheet_row": None,
            "instrument_number": None,
            "book_page": row["ogl_or_bkpg"],
            "doc_type": "curative",
            "grantor": row["owner"],
            "grantee": None,
            "document_url": row["okcountyrecords_search"],
            "status": "pending",
            "diff_kind": "curative",
        })
        added += 1
    store.audit("curative_enqueued", f"{added} curative items")
    return {"enqueued": added}


def pending_items(limit: int | None = None) -> list[dict]:
    items = store.fetch_all(
        "SELECT id, document_url, grantor, book_page, status FROM work_queue "
        "WHERE source='curative' AND status IN ('pending','takeover') ORDER BY id")
    return items[:limit] if limit else items


def walk_curative(source: Path | None = None, cdp_url: str = config.CDP_URL,
                  delay: float = 2.0, max_items: int | None = None,
                  pause_on_takeover: bool = True, dry_run: bool = False,
                  progress=None) -> dict:
    """Open each pending curative item in the connected browser and capture
    evidence. dry_run=True returns the plan without opening a browser."""
    if source is not None:
        enqueue_curative(source)

    items = pending_items(max_items)
    if dry_run:
        return {"dry_run": True, "planned": len(items),
                "items": [{"id": it["id"], "owner": it["grantor"],
                           "url": it["document_url"]} for it in items]}

    # Import here so the rest of the module works without Playwright installed.
    from .connector import session
    from . import doc_worker

    results = []
    config.ensure_dirs()
    with session(cdp_url) as s:
        for n, it in enumerate(items, 1):
            if progress:
                progress(n, len(items), it["grantor"])
            try:
                cap = doc_worker.capture_document(s, it["document_url"], it["id"])
                status = "takeover" if cap.get("takeover") else "review"
                store.execute("UPDATE work_queue SET status=? WHERE id=?",
                              (status, it["id"]))
                results.append({"id": it["id"], "owner": it["grantor"],
                                "status": status,
                                "screenshot": cap.get("screenshot")})
                if cap.get("takeover") and pause_on_takeover:
                    results[-1]["paused"] = True
                    store.audit("curative_walk_paused",
                                f"manual takeover at item {it['id']}")
                    break
            except Exception as e:  # fail loud, record, keep going
                store.audit("curative_walk_error", str(e), {"id": it["id"]})
                results.append({"id": it["id"], "owner": it["grantor"],
                                "status": "error", "error": str(e)})
            time.sleep(delay)  # be polite to the county site

    captured = sum(1 for r in results if r.get("status") in ("review", "takeover"))
    return {"dry_run": False, "processed": len(results), "captured": captured,
            "results": results}
