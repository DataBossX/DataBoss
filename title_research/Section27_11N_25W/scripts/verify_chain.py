#!/usr/bin/env python3
"""
verify_chain.py - check OCR'd assignment text against the expected 2017-2026
corporate chain and write records_parsed/chain_verification.json.

build_final.py reads that file and ONLY upgrades chain/QA confidence when
chain_verified == true. NRI/WI decimals always stay UNRESOLVED/ESTIMATE-ONLY
(those need NMA + ORRI netting, not just chain confirmation).

Verification is conservative: an instrument counts as verified only if its
OCR text contains its book/page (in either '2266/194' or '2266 194' form)
AND at least one expected party/keyword for that instrument.
"""
import os, re, json, glob, pathlib, datetime
ROOT=pathlib.Path(__file__).resolve().parent.parent
OCRD=ROOT/"records_ocr"; OUT=ROOT/"records_parsed"; OUT.mkdir(parents=True, exist_ok=True)

# instrument -> (book, page, [expected keywords, lowercase])
TARGETS={
 "2017-004597":("2266","194",["assignment","fourpoint","oil"]),
 "2019-002937":("2307","894",["enervest","fourpoint","assignment"]),
 "2019-002988":("2308","123",["enervest","fourpoint","assignment"]),
 "2020-004390":("2340","218",["unbridled","fourpoint","name change","name"]),
 "2025-001808":("2451","4",  ["diversified","maverick","merger"]),
 "2026-001031":("2480","824",["diversified","affidavit"]),
 "2001-008828":("1719","304",["release","partial","sanguine"]),
 "2023-000993":("2401","214",["teocalli","unbridled","wellbore","exhibit"]),
}

def load_text():
    blob={}
    for f in glob.glob(str(OCRD/"*.txt")):
        blob[pathlib.Path(f).stem]=pathlib.Path(f).read_text(encoding="utf-8",errors="ignore").lower()
    return blob

def find_text_for(instr, book, page, blob):
    # match by instrument number in filename, else by book/page appearing in any txt
    for stem,txt in blob.items():
        if instr.replace("-","") in stem.replace("-","") or instr in stem:
            return txt
    bp1=f"{book}/{page}"; bp2=f"{book} {page}"
    for txt in blob.values():
        if bp1 in txt or bp2 in txt: return txt
    return ""

def main():
    blob=load_text()
    results={}
    for instr,(book,page,kws) in TARGETS.items():
        txt=find_text_for(instr,book,page,blob)
        has_bp = bool(re.search(rf"{book}\s*[/\- ]\s*{page}\b", txt))
        has_kw = any(k in txt for k in kws)
        verified = bool(txt) and has_bp and has_kw
        results[instr]={"book_page":f"{book}/{page}","verified":verified,
                        "book_page_found":has_bp,"keyword_found":has_kw,
                        "text_len":len(txt)}
    ok=sum(1 for v in results.values() if v["verified"])
    # require the core succession instruments to all verify before flipping the gate
    core=["2017-004597","2019-002937","2019-002988","2020-004390","2025-001808"]
    chain_verified = all(results[c]["verified"] for c in core)
    out={"chain_verified":chain_verified,
         "verified_on":datetime.date.today().isoformat(),
         "summary":f"{ok}/{len(results)} instruments verified; core succession {'ALL OK' if chain_verified else 'INCOMPLETE'}",
         "instruments":results}
    (OUT/"chain_verification.json").write_text(json.dumps(out,indent=2))
    print(json.dumps({k:out[k] for k in ("chain_verified","verified_on","summary")},indent=2))
    print("Wrote records_parsed/chain_verification.json")
    if not chain_verified:
        print("NOTE: chain NOT fully verified -> report keeps NRI/WI UNRESOLVED. "
              "Check records_ocr/*.txt; handwritten/low-quality scans may need manual review.")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
