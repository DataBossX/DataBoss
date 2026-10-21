"""Section package builder CLI.

  python -m abstract_builder.build --section 6 --twp 47 --rge 76 --county Johnson \
      --county-in <county.xlsx|ods> [--blm-in <WYW-xxxx.xlsx|ods> ...] \
      --prep-date 2026-10-20 --county-thru 2026-10-06 --out <dir> [--profile profile.json] [--donor-letter <docx>] [--srp-date WYW-149799=2026-10-13]

Inputs are existing candidate workbooks; the builder only re-formats, never invents. Every blanked / changed value goes
to QA_INTERNAL/OPEN_ITEMS.csv and CHANGE_LOG.csv (outside the client folder). Output layout:

  <out>/CLIENT/       county index xlsx/ods/pdf, per-case BLM xlsx/ods/pdf, checklist xlsx/pdf, letter docx/pdf
  <out>/QA_INTERNAL/  OPEN_ITEMS.csv, CHANGE_LOG.csv, COUNTS.json, QA_GATES.json, SHA256SUMS.txt
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
from datetime import date
from pathlib import Path

from .census import census_workbook
from .qa import check_index
from .render import (ChecklistData, IndexMeta, LetterData, convert, write_checklist, write_index, write_letter)
from .normalize import is_blank, norm_book_page, normalize_blm_row, normalize_county_row



def load_profile(path: str | None) -> dict:
    """Private operator profile (never committed): preparer, project, client, county_label, file_label, donor_letter."""
    base = {"preparer": "", "project": "", "client": "", "file_label": "Abstract_Index", "donor_letter": None}
    if path:
        base.update(json.loads(Path(path).read_text()))
    return base


def load_patches(path: str | None) -> list[dict]:
    """Evidence-backed cell patches (private file): [{layout, doc_no, book_page, col, value, kind, evidence}].
    kind: fill (value written) | confirmed_blank (face proves nothing to fill) | unresolved (needs a better image)."""
    return json.loads(Path(path).read_text()) if path else []


def _d(s: str | None) -> date | None:
    return date.fromisoformat(s) if s else None


def _long(d: date) -> str:
    return f"{d.strftime('%B')} {d.day}, {d.year}"


def build_section(a) -> dict:
    prof = load_profile(a.profile)
    out = Path(a.out); client = out / "CLIENT"; qa_dir = out / "QA_INTERNAL"
    client.mkdir(parents=True, exist_ok=True); qa_dir.mkdir(parents=True, exist_ok=True)
    prep = _d(a.prep_date); thru = _d(a.county_thru)
    sec, twp, rge = a.section, a.twp, a.rge
    tag = f"{sec}-{twp}N-{rge}W"
    log_rows: list[dict] = []; open_rows: list[dict] = []
    counts: dict = {"section": tag, "county_rows_in": 0, "county_rows_out": 0, "blm": {}}

    # ---------------- county
    c_scs = [s for s in census_workbook(Path(a.county_in)) if s.layout == "county"]
    if not c_scs:
        raise SystemExit(f"no county-layout sheet in {a.county_in}")
    c = c_scs[0]
    counts["county_rows_in"] = c.n_rows
    rows = []
    patches = [pt for pt in load_patches(getattr(a, "patches", None)) if pt.get("layout", "county") == "county"]
    COL = {"doc_type": 0, "grantor": 1, "grantee": 2, "doc_no": 3, "book_page": 4, "date_of_doc": 5, "rec_date": 6, "legal": 7, "comments": 8}
    dispositions: dict[tuple, str] = {}
    for i, r in enumerate(c.rows, start=10):
        r = list(r)
        rbp, rdn = norm_book_page(r[4])[0], str(r[3] or "").strip().lstrip("0")
        for pt in patches:
            if norm_book_page(pt.get("book_page"))[0] == rbp and str(pt.get("doc_no", "")).lstrip("0") in ("", rdn):
                col = COL[pt["col"]]
                dispositions[(i, pt["col"])] = pt["kind"]
                if pt["kind"] == "fill":
                    log_rows.append({"file": "county", "row": i, "note": f"PATCH_FILL:{pt['col']}:{r[col]!r}->{pt['value']!r} | {pt['evidence']}"})
                    r[col] = pt["value"]
                else:
                    log_rows.append({"file": "county", "row": i, "note": f"PATCH_{pt['kind'].upper()}:{pt['col']} | {pt['evidence']}"})
        rr = normalize_county_row(r, sec, twp, rge)
        rows.append(rr.values)
        for n in rr.notes:
            log_rows.append({"file": "county", "row": i, "note": n})
        for n in rr.open_items:
            colname = {"DOC_NO": "doc_no", "BOOK_PAGE": "book_page", "DATE": "date_of_doc", "PARTY": "grantee", "LEGAL": "legal"}
            key = next((v for k, v in colname.items() if n.startswith(k)), None)
            status = {"confirmed_blank": "SOURCE-SUPPORTED BLANK", "unresolved": "UNRESOLVED (better image needed)"}.get(
                next((dv for (rw, cn), dv in dispositions.items() if rw == i and (cn == key or key is None)), ""), "OPEN")
            open_rows.append({"file": "county", "row": i, "item": n, "doc_no": rr.values[3], "book_page": rr.values[4], "status": status})
    counts["county_rows_out"] = len(rows)
    counts["county_missing_image"] = sum(1 for r in rows if r[8] == "missing image")
    counts["county_blank_substantive_after"] = sum(1 for r in rows for k in range(8) if is_blank(r[k]))
    stem = f"{twp}N-{rge}W-{sec}_{a.county}_Co_{prof['file_label']}"
    meta = IndexMeta(a.county, f"T{twp}N-R{rge}W Section {sec}: All", prep, a.starting_date or None, thru, indexed_by=prof["preparer"], project=prof["project"])
    cx = write_index(rows, meta, "county", client / f"{stem}.xlsx")
    gates = {"county": check_index(cx, allow_text_doc_no=True)}
    convert(cx, "ods"); convert(cx, "pdf")

    # ---------------- BLM
    srp_dates = dict(x.split("=") for x in (a.srp_date or []))
    fed_serials = []
    for bpath in (a.blm_in or []):
        for b in census_workbook(Path(bpath)):
            if b.layout != "blm":
                continue
            serial = re.search(r"WYW-?\d+X?|W-?\d{4,6}", Path(bpath).name, re.I)
            serial = (serial.group(0).upper() if serial else Path(bpath).stem)
            serial = re.sub(r"^WYW(\d)", r"WYW-\1", serial)
            brows = []
            for i, r in enumerate(b.rows, start=10):
                rr = normalize_blm_row(r, unnumbered=serial in set(getattr(a, "unnumbered", None) or []))
                brows.append(rr.values)
                for n in rr.notes:
                    log_rows.append({"file": serial, "row": i, "note": n})
                for n in rr.open_items:
                    open_rows.append({"file": serial, "row": i, "item": n, "doc_no": "", "book_page": "", "status": "OPEN"})
            sd = _d(srp_dates.get(serial))
            bmeta = IndexMeta(a.county, serial, prep, a.starting_date or None, sd, indexed_by=prof["preparer"], project=prof["project"])
            bx = write_index(brows, bmeta, "blm", client / f"{serial} {a.county} Co. {prof['file_label'].replace('_', ' ')}.xlsx")
            gates[serial] = check_index(bx)
            convert(bx, "ods"); convert(bx, "pdf")
            counts["blm"][serial] = {"rows_in": b.n_rows, "rows_out": len(brows),
                                     "blank_substantive_after": sum(1 for r in brows for k in (0, 1, 2, 4, 5, 6, 8, 9) if is_blank(r[k])),
                                     "parts": sorted({r[9] for r in brows if r[9] is not None}),
                                     "srp_date": str(sd) if sd else None}
            fed_serials.append(serial)

    # ---------------- checklist + letter
    case_files = [x for x in (a.case_files or []) if x in fed_serials] if getattr(a, "case_files", None) is not None else list(fed_serials)
    srp_have = [x for x in fed_serials if x in srp_dates]
    blm_cell = "\n".join(fed_serials) if fed_serials else "N/A"
    blm_counts = "\n".join(f"{s}: {counts['blm'][s]['rows_out']}" for s in fed_serials) if fed_serials else "N/A"
    def _srp_item(x):
        d_ = _d(srp_dates[x]); return f"{x}: {d_.month}/{d_.day}/{d_.year}"
    srp_info = "\n".join(_srp_item(x) for x in srp_have) if srp_have else "N/A"
    all_srp = bool(fed_serials) and len(srp_have) == len(fed_serials)
    lands = f"T{twp}N-R{rge}W Section {sec}: All"
    cl = ChecklistData(
        ["Yes", "Partial", "Yes", "Yes", "No", blm_cell, ("Yes" if all_srp else "Partial") if fed_serials else "N/A", "N/A", "N/A", "No", "Yes"],
        ["Yes", a.county, lands, prep, a.starting_date or None, prep, prof["preparer"], prof["project"]],
        ["Yes", prof["client"], f"{lands}, {a.county} County, Wyoming",
         f"County index: {len(rows)} entries" + (f"; source cutoff {thru.month}/{thru.day}/{thru.year}" if thru else ""),
         blm_counts, srp_info, prep])
    clx = write_checklist(cl, client / f"Abstract_Checklist_{sec}-{twp}N-{rge}W.xlsx")
    convert(clx, "pdf")
    cutoff_text = (f"{'from ' + a.starting_date if a.starting_date else 'from the earliest indexed instrument'} to last Indexed Instrument Recorded {_long(thru)}."
                   if thru else "from the earliest indexed instrument through the date of the tract-index print supplied.")
    ld = LetterData(twp, rge, sec, a.county, cutoff_text, "N/A", case_files, srp_have,
                    _long(_d(next(iter(srp_dates.values())))) if srp_have and len({srp_dates[x] for x in srp_have}) == 1 else None, prof["client"], prep, prof["preparer"], a.qualified_note)
    donor_letter = a.donor_letter or prof["donor_letter"]
    if donor_letter:
        lx = write_letter(ld, Path(donor_letter), client / f"{sec}-{twp}N-{rge}W_Certification_Letter.docx")
        convert(lx, "pdf")

    # ---------------- QA internal
    def w(name, rows_):
        with open(qa_dir / name, "w", newline="") as f:
            if rows_:
                wr = csv.DictWriter(f, fieldnames=list(rows_[0])); wr.writeheader(); wr.writerows(rows_)
    w("CHANGE_LOG.csv", log_rows); w("OPEN_ITEMS.csv", open_rows)
    counts["open_items"] = len(open_rows)
    (qa_dir / "COUNTS.json").write_text(json.dumps(counts, indent=2, default=str))
    (qa_dir / "QA_GATES.json").write_text(json.dumps({"format_gate_C": gates, "pass": all(not v for v in gates.values())}, indent=2))
    sums = []
    for p in sorted(client.glob("*")):
        sums.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  CLIENT/{p.name}")
    (qa_dir / "SHA256SUMS.txt").write_text("\n".join(sums) + "\n")
    return {"counts": counts, "gates": gates}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--section", type=int, required=True); ap.add_argument("--twp", type=int, default=47); ap.add_argument("--rge", type=int, default=76)
    ap.add_argument("--county", default="Johnson"); ap.add_argument("--county-in", required=True)
    ap.add_argument("--blm-in", nargs="*"); ap.add_argument("--prep-date", required=True); ap.add_argument("--county-thru")
    ap.add_argument("--starting-date", default=None); ap.add_argument("--srp-date", nargs="*")
    ap.add_argument("--case-files", nargs="*", help="serials with a case-file image set in hand (letter claim)")
    ap.add_argument("--unnumbered", nargs="*", help="federal serials whose source file carries no part number (Part stays blank)")
    ap.add_argument("--patches", help="private JSON of evidence-backed cell patches")
    ap.add_argument("--profile", help="private JSON profile (see profile.example.json)")
    ap.add_argument("--qualified-note", default=None); ap.add_argument("--donor-letter"); ap.add_argument("--out", required=True)
    res = build_section(ap.parse_args(argv))
    print(json.dumps(res, indent=2, default=str))


if __name__ == "__main__":
    main()
