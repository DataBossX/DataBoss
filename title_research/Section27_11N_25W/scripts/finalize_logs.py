#!/usr/bin/env python3
"""
finalize_logs.py - after build+OCR+verify, refresh the standalone logs and
copy all deliverables into ./deliverables/. No network, no secrets.

Updates:
  output/SECTION_27_API_AND_OCR_LOG.md      (download + OCR status)
  output/NEEDS_APPROVAL_TO_DOWNLOAD_RECORDS.md (approval manifest status)
Then mirrors output/* -> deliverables/*.
"""
import os, json, csv, glob, shutil, pathlib, datetime
ROOT=pathlib.Path(__file__).resolve().parent.parent
OUT, DELIV, PARSED, RAW, OCRD = (ROOT/"output"),(ROOT/"deliverables"),(ROOT/"records_parsed"),(ROOT/"records_raw"),(ROOT/"records_ocr")
DELIV.mkdir(parents=True, exist_ok=True)
today=datetime.date.today().isoformat()

verif={}
vp=PARSED/"chain_verification.json"
if vp.exists():
    try: verif=json.loads(vp.read_text())
    except Exception: verif={}
chain_ok=bool(verif.get("chain_verified"))
summary=verif.get("summary","no verification run")

dl=[]
mp=PARSED/"download_manifest_actual.csv"
if mp.exists():
    with open(mp) as f: dl=list(csv.reader(f))[1:]
n_dl=sum(1 for r in dl if len(r)>3 and r[3] in ("downloaded","cached"))

status = "COMPLETE (local run)" if chain_ok else ("DOWNLOADED, chain not fully verified" if n_dl else "NOT RUN / no downloads")

api=OUT/"SECTION_27_API_AND_OCR_LOG.md"
api.write_text(f"""# Section 27 - API & OCR Log

## OKCountyRecords.com pull - status: {status} (updated {today})
- API key read from env var only; never printed, logged, written, or committed.
- Records downloaded/cached this run: {n_dl}
- Chain verification: {summary}
- chain_verified = {chain_ok}

## OCR pipeline
- records_raw/*.pdf rendered at 300 DPI (poppler pdftoppm, or PyMuPDF fallback).
- tesseract OCR -> records_ocr/<instrument>.txt (images saved even if tesseract absent).
- verify_chain.py compares OCR text to expected book/page + party keywords for the
  8 Priority-1 instruments and writes records_parsed/chain_verification.json.

## Priority-1 instruments
2266/194, 2307/894, 2308/123, 2340/218, 2451/4, 2480/824, 1719/304, 2401/214.

## Confidence rule
NRI/WI decimals remain UNRESOLVED/ESTIMATE-ONLY regardless of chain verification;
chain verification only confirms the ownership succession, not the WI decimal
(which still needs per-lessor NMA + ORRI netting).
""", encoding="utf-8")

man=OUT/"NEEDS_APPROVAL_TO_DOWNLOAD_RECORDS.md"
prev = man.read_text(encoding="utf-8") if man.exists() else "# Records pending download (approval required)\n"
stamp=(f"\n\n---\n## Local-run status ({today})\n"
       f"- Status: **{status}**\n"
       f"- Records downloaded/cached: {n_dl}\n"
       f"- Chain verification: {summary}\n"
       f"- chain_verified = {chain_ok}\n")
if "## Local-run status" in prev:
    prev=prev.split("\n## Local-run status")[0].rstrip()
man.write_text(prev+stamp, encoding="utf-8")

# mirror output -> deliverables
copied=0
for f in glob.glob(str(OUT/"*")):
    if os.path.isfile(f):
        shutil.copy2(f, DELIV/pathlib.Path(f).name); copied+=1
print(f"finalize_logs: status={status}; mirrored {copied} files to deliverables/")
