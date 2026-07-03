#!/usr/bin/env python3
"""
Batch puller for the Section 31-12N-24W open-item list.

Run this on a machine with normal internet (this cloud session's egress blocks
okcountyrecords.com / OCC / OTC). It reads the open-item CSV produced by
gen_exports.py, pulls each recorded instrument image from the okcountyrecords
API, saves it to ./_pulled_images/, and writes a manifest.

SECURITY: the API key is read from the environment at runtime and is NEVER
printed, logged, or written to any output file. Set it before running:

    # okcountyrecords key lives in the project .env on the operator's machine
    export OKCR_API_KEY="...."        # or load your .env however you normally do
    python pull_okcountyrecords.py exports/open_items_pull_list.csv

Nothing here fabricates title facts — it only fetches images you then read.
"""
import os, sys, csv, time, json, pathlib, urllib.request, urllib.parse

API_KEY = os.environ.get("OKCR_API_KEY") or os.environ.get("OKCOUNTYRECORDS_API_KEY")
COUNTY  = "Roger Mills"
BASE    = "https://okcountyrecords.com/api/v1/images"
OUTDIR  = pathlib.Path("_pulled_images")
PAUSE   = 1.0  # be polite to the API

def pull(instr_number, out_path):
    """Fetch one instrument image. Returns (ok, http_status_or_error)."""
    q = urllib.parse.urlencode({"county": COUNTY, "number": instr_number, "action": "view"})
    req = urllib.request.Request(f"{BASE}?{q}")
    if API_KEY:
        req.add_header("Authorization", f"Bearer {API_KEY}")   # key never printed
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
            out_path.write_bytes(data)
            return True, r.status
    except Exception as e:
        return False, str(e)

def main():
    if not API_KEY:
        print("!! No OKCR_API_KEY in environment. Export it first (see header). "
              "Proceeding will fail auth.", file=sys.stderr)
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "exports/open_items_pull_list.csv"
    OUTDIR.mkdir(exist_ok=True)
    manifest = []
    with open(csv_path, newline="") as f:
        rows = [r for r in csv.DictReader(f)]
    todo = [r for r in rows if r.get("Instrument #")]
    print(f"{len(todo)} instrument images to pull -> {OUTDIR}/")
    for i, r in enumerate(todo, 1):
        num = r["Instrument #"].strip()
        out = OUTDIR / f"{num}.pdf"
        if out.exists():
            print(f"[{i}/{len(todo)}] {num} already present, skip"); continue
        ok, status = pull(num, out)
        manifest.append(dict(instrument=num, party=r.get("Party / subject",""),
                             bkpg=r.get("Bk/Pg",""), category=r.get("Category",""),
                             pulled=ok, status=str(status), file=str(out) if ok else ""))
        print(f"[{i}/{len(todo)}] {num}: {'OK' if ok else 'FAIL '+str(status)}")
        time.sleep(PAUSE)
    with open("_pulled_images/_manifest.json", "w") as m:
        json.dump(manifest, m, indent=2)
    got = sum(1 for x in manifest if x["pulled"])
    print(f"\nDone. {got}/{len(todo)} pulled. Manifest: _pulled_images/_manifest.json")
    print("Next: read each image and enter the conveyed fraction / vesting into the workbook.")

if __name__ == "__main__":
    main()
