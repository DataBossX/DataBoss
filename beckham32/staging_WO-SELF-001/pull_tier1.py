#!/usr/bin/env python3
"""Tier 1 copy-pull executor - DBX-OK-BECKHAM-32-11N-25W (approved 2026-07-11).

Run this on a machine that can reach okcountyrecords.com (the cloud session
cannot - its network policy blocks the host).

    set OKCOUNTY_API_KEY=<key>            (Windows)   or  export ... (mac/linux)
    set OKCOUNTY_BASE_URL=https://okcountyrecords.com/api/v1
    py pull_tier1.py --out "D:\\Desktop\\Horizon\\32-11N-25W OKCR Tier1"

The key is read from the environment only. It is never written to disk,
never printed, and never embedded in this file. Total estimated spend:
22 x $0.40 = $8.80 (watermarked API rate). The script stops at 22 items.

NOTE: the exact endpoint path/params below follow the pattern of the OKCR
detail URLs in the project register. The cloud session could not read the
API documentation (host blocked), so if the API returns 404 on the first
item, check the docs for the correct download route and adjust ENDPOINT -
nothing else needs to change.
"""
import argparse
import hashlib
import json
import os
import sys
import time
import urllib.request

TIER1 = [
    # (instrument_id, book-page label, okcr_record_id or None)
    ("2022-000152", "2371-470", "27093726"),
    ("2022-003506", "2389-500", "28108427"),
    ("2022-004838", "2395-415", "28268306"),
    ("2023-000796", "2400-551", "28512407"),
    ("2025-001808", "2451-4", "34086362"),
    ("2026-000211", "2475-943", "34968244"),
    ("2026-000212", "2476-1", "34968246"),
    ("2026-000213", "2476-67", "34968243"),
    ("2026-000214", "2476-109", "34968245"),
    ("2026-000215", "2476-121", "34968247"),
    ("2023-000993", "2401-214", None),
    ("2023-004455", "2415-328", None),
    ("2023-004457", "2415-410", None),
    ("2023-004458", "2415-515", None),
    ("2023-004459", "2415-617", None),
    ("2020-001596", "2328-269", None),
    ("2021-004510", "2365-743", None),
    ("2023-004424", "2415-1", None),
    ("2025-004873", "2470-153", None),
    ("2025-005515", "2474-292", None),
    ("2020-001026", "2327-1", None),
    ("2020-001027", "2327-108", None),
]

COUNTY = "beckham"
# Adjust this one line if the API docs use a different download route:
ENDPOINT = "{base}/counties/{county}/instruments/{instrument}/download?format=pdf"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="OKCR_Tier1_Pulls")
    ap.add_argument("--dry-run", action="store_true",
                    help="show what would be purchased; no requests, no spend")
    args = ap.parse_args()

    key = os.environ.get("OKCOUNTY_API_KEY")
    base = os.environ.get("OKCOUNTY_BASE_URL", "https://okcountyrecords.com/api/v1")
    if not key and not args.dry_run:
        sys.exit("ERROR: set OKCOUNTY_API_KEY in the environment first "
                 "(never paste it into files or chat logs).")

    os.makedirs(args.out, exist_ok=True)
    manifest = []
    spent = 0
    for iid, bp, rec in TIER1:
        fname = f"I-{iid}__{bp}.pdf"
        dest = os.path.join(args.out, fname)
        if os.path.exists(dest):
            print(f"SKIP (already downloaded): {fname}")
            continue
        url = ENDPOINT.format(base=base.rstrip("/"), county=COUNTY, instrument=iid)
        if args.dry_run:
            print(f"WOULD PULL: {fname}  <-  {url}")
            continue
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {key}",
            "X-Api-Key": key,
            "User-Agent": "DataBossX-Tier1-Pull/1.0",
        })
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = resp.read()
        except Exception as exc:
            print(f"FAILED {fname}: {exc}")
            print("  If this is a 404, adjust ENDPOINT per the API docs and rerun; "
                  "already-downloaded files are skipped.")
            manifest.append({"file": fname, "instrument": f"I-{iid}",
                             "status": f"FAILED: {exc}"})
            continue
        if not data.startswith(b"%PDF"):
            print(f"WARNING {fname}: response is not a PDF "
                  f"({len(data)} bytes) - saved as .bin for inspection")
            dest += ".bin"
        with open(dest, "wb") as f:
            f.write(data)
        sha = hashlib.sha256(data).hexdigest()
        spent += 0.40
        print(f"OK {fname}  {len(data):,} bytes  sha256 {sha[:16]}...  "
              f"(running est. ${spent:.2f})")
        manifest.append({"file": os.path.basename(dest), "instrument": f"I-{iid}",
                         "book_page": bp, "okcr_record_id": rec,
                         "bytes": len(data), "sha256": sha,
                         "retrieved_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                         "status": "DOWNLOADED_UNVERIFIED"})
        time.sleep(1)  # be polite to the API
    with open(os.path.join(args.out, "PULL_MANIFEST.json"), "w") as f:
        json.dump({"project_id": "DBX-OK-BECKHAM-32-11N-25W",
                   "approval": "Rodney 2026-07-11", "est_spend_usd": round(spent, 2),
                   "items": manifest}, f, indent=1)
    print(f"\nDone. Manifest written. Upload the whole '{args.out}' folder to the "
          "Drive folder 05_OKCOUNTYRECORDS_CONTINUATION and tell the agent to ingest.")


if __name__ == "__main__":
    main()
