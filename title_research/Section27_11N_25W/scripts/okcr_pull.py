#!/usr/bin/env python3
"""
okcr_pull.py — Section 27-11N-25W OKCountyRecords.com pull / OCR / parse pipeline.

RUN THIS ON A MACHINE WITH NETWORK ACCESS TO okcountyrecords.com
(the managed cloud sandbox blocks that host via an egress allowlist).

Security:
  - Reads the API key ONLY from env var OKCR_API_KEY (or OKCOUNTYRECORDS_API_KEY).
  - Never prints, logs, or writes the key anywhere.
  - Honors APPROVE_OKCR_DOWNLOADS=true before any PAID image download.
  - Dry-run cost estimate first; writes a manifest; stops if not approved.

Usage:
  export OKCR_API_KEY=********           # do NOT hard-code
  export APPROVE_OKCR_DOWNLOADS=true     # only when you accept the cost
  python scripts/okcr_pull.py --dry-run  # estimate only
  python scripts/okcr_pull.py            # download Priority-1, OCR, parse
"""
import os, sys, json, base64, time, pathlib, csv
import requests  # pip install requests

API = "https://okcountyrecords.com/api/v1"
KEY = os.environ.get("OKCR_API_KEY") or os.environ.get("OKCOUNTYRECORDS_API_KEY")
APPROVED = os.environ.get("APPROVE_OKCR_DOWNLOADS", "").lower() == "true"
ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW, OCRD, PARSED, LOGS = (ROOT/"records_raw"), (ROOT/"records_ocr"), (ROOT/"records_parsed"), (ROOT/"logs")
for d in (RAW, OCRD, PARSED, LOGS): d.mkdir(parents=True, exist_ok=True)

# Priority-1 instruments to verify the carried Diversified chain + depth
TARGETS = [
    ("2017-004597","2266/194","Assignment N&G->FourPoint"),
    ("2019-002937","2307/894","EnerVest->FourPoint"),
    ("2019-002988","2308/123","EnerVest->FourPoint"),
    ("2020-004390","2340/218","FourPoint->Unbridled name change"),
    ("2025-001808","2451/4","Maverick/Diversified merger"),
    ("2026-001031","2480/824","Diversified support affidavit"),
    ("2001-008828","1719/304","Partial release - depth limit proof"),
    ("2023-000993","2401/214","Teocalli wellbore-only (Exhibit A)"),
]

def auth_header():
    if not KEY:
        sys.exit("ERROR: OKCR_API_KEY not set. export it first (never hard-code).")
    tok = base64.b64encode(f"{KEY}:".encode()).decode()  # Basic auth: key as username, blank pw
    return {"Authorization": f"Basic {tok}", "Accept": "application/json"}

def session():
    s = requests.Session(); s.headers.update(auth_header()); return s

def search_instrument(s, instr):
    # adjust param names to match the live API docs if needed
    r = s.get(f"{API}/search", params={"county":"Beckham","instrument":instr}, timeout=60)
    r.raise_for_status(); return r.json()

def estimate(s):
    rows=[]
    for instr, bp, why in TARGETS:
        try:
            res = search_instrument(s, instr)
            hits = res.get("results", res if isinstance(res,list) else [])
            pages = sum(int(h.get("page_count", h.get("pages", 1)) or 1) for h in hits) or 1
        except Exception as e:
            hits, pages = [], 0
            print(f"  ! search failed {instr}: {e}")
        rows.append({"instrument":instr,"book_page":bp,"reason":why,
                     "result_count":len(hits),"est_pages":pages})
        time.sleep(0.5)
    (PARSED/"download_estimate.json").write_text(json.dumps(rows,indent=2))
    tot=sum(r["est_pages"] for r in rows)
    print(f"\nDRY-RUN: {len(rows)} instruments, ~{tot} pages. See records_parsed/download_estimate.json")
    return rows

def download(s, rows):
    if not APPROVED:
        sys.exit("STOP: APPROVE_OKCR_DOWNLOADS != true. Set it to proceed with paid downloads.")
    man=[]
    for r in rows:
        instr=r["instrument"]
        try:
            res=search_instrument(s, instr)
            hits=res.get("results", res if isinstance(res,list) else [])
            for h in hits:
                doc_id=h.get("id") or h.get("document_id") or h.get("image_id")
                if not doc_id: continue
                out=RAW/f"{instr.replace('/','_')}_{doc_id}.pdf"
                if out.exists():  # idempotent
                    man.append((instr,doc_id,str(out),"cached")); continue
                img=s.get(f"{API}/images/{doc_id}", timeout=180)
                img.raise_for_status()
                out.write_bytes(img.content)
                man.append((instr,doc_id,str(out),"downloaded"))
                time.sleep(1.0)
        except Exception as e:
            man.append((instr,"","",f"ERROR {e}"))
    with open(PARSED/"download_manifest_actual.csv","w",newline="") as f:
        csv.writer(f).writerows([("instrument","doc_id","path","status")]+man)
    print(f"Downloaded {sum(1 for m in man if m[3]=='downloaded')} new files -> records_raw/")
    print("Next: OCR with `pdftoppm -r 300` + tesseract or visual review, then re-run build_final.py")

if __name__=="__main__":
    s=session(); rows=estimate(s)
    if "--dry-run" not in sys.argv:
        download(s, rows)
