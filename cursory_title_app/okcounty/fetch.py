"""Fetch the Section 31 open-item documents from OKCountyRecords, then hand them
to the vision-extraction + re-import pipeline.

SAFETY: pulling images may incur per-image charges. This runs a DRY RUN by
default (lists what it would fetch + a cost estimate) and only downloads when you
pass --confirm. Nothing is fetched without your explicit go-ahead.

Run on YOUR machine (the API host is egress-blocked from the cloud prep box):
    setx OKCOUNTY_API_KEY <key>        # or put it in .env
    python -m cursory_title_app.okcounty.fetch                # dry run
    python -m cursory_title_app.okcounty.fetch --confirm      # actually pull
    python -m cursory_title_app.okcounty.fetch --confirm --group source_in_roots
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from .. import config
from ..db import store
from .client import OkCountyClient, OkCountyError

TARGETS = Path(__file__).with_name("section31_targets.json")
COST_PER_IMAGE = float(__import__("os").getenv("OKCOUNTY_COST_PER_IMAGE", "0.50"))
GROUPS = ("source_in_roots", "mineral_balance_candidates", "conveyed_fraction_instruments")


def load_targets(groups) -> list[dict]:
    data = json.loads(TARGETS.read_text())
    out = []
    for g in groups:
        for item in data.get(g, []):
            out.append({**item, "_group": g})
    return out


def fetch(groups=GROUPS, confirm=False, out_dir: Path | None = None,
          delay: float = 1.0, max_items: int | None = None) -> dict:
    out_dir = Path(out_dir or (config.DATA_DIR / "okcounty_pdfs"))
    targets = load_targets(groups)
    if max_items:
        targets = targets[:max_items]
    est = len(targets) * COST_PER_IMAGE

    if not confirm:
        return {"dry_run": True, "would_fetch": len(targets),
                "estimated_cost_usd": round(est, 2),
                "note": "Re-run with --confirm to download. Charges may apply.",
                "items": [{"number": t["number"], "group": t["_group"],
                           "party": t.get("party", "")} for t in targets]}

    config.ensure_dirs()
    store.init()
    client = OkCountyClient()
    client.preflight()  # raises OkCountyError with a clear reason if unreachable

    fetched, errors = [], []
    for i, t in enumerate(targets, 1):
        num = t["number"]
        try:
            path = client.save_image(num, out_dir)
            # Don't regress a row already advanced past download (e.g. extracted).
            existing = store.fetch_one(
                "SELECT status FROM work_queue WHERE dedup_key=?", (f"okc::{num}",))
            status = existing["status"] if existing and existing["status"] in (
                "extracted", "review", "done") else "downloaded"
            qid = store.upsert_queue({
                "dedup_key": f"okc::{num}", "source": "okcounty",
                "instrument_number": num, "book_page": t.get("bkpg"),
                "doc_type": t.get("type"), "grantor": t.get("party"),
                "document_url": f"{client.base_url}/images?county={config.TARGET_COUNTY}&number={num}",
                "status": status, "diff_kind": t["_group"],
            })
            if qid:
                store.add_evidence(qid, "pdf", source_url=num, file_path=str(path))
            fetched.append({"number": num, "path": str(path)})
            print(f"  [{i}/{len(targets)}] {num} -> {path.name}")
        except OkCountyError as e:
            errors.append({"number": num, "error": str(e)})
            store.audit("okcounty_fetch_error", f"{num}: {e}")
            print(f"  [{i}/{len(targets)}] {num} ERROR: {e}")
        time.sleep(delay)

    store.audit("okcounty_fetch_done",
                f"fetched={len(fetched)} errors={len(errors)}",
                {"groups": list(groups)})
    return {"dry_run": False, "fetched": len(fetched), "errors": errors,
            "out_dir": str(out_dir), "cost_estimate_usd": round(len(fetched) * COST_PER_IMAGE, 2)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--confirm", action="store_true", help="actually download (may incur charges)")
    ap.add_argument("--group", action="append", choices=GROUPS,
                    help="limit to one or more target groups (default: all)")
    ap.add_argument("--max", type=int, default=None)
    ap.add_argument("--delay", type=float, default=1.0)
    a = ap.parse_args()
    groups = tuple(a.group) if a.group else GROUPS
    res = fetch(groups=groups, confirm=a.confirm, delay=a.delay, max_items=a.max)
    print(json.dumps(res, indent=2))
    if res.get("dry_run"):
        print("\nDRY RUN. Add --confirm to download. Estimated cost: "
              f"${res['estimated_cost_usd']} at ${COST_PER_IMAGE}/image.")


if __name__ == "__main__":
    main()
