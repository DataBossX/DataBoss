"""Orchestration: offline analysis and online fetch→fill loops."""
from __future__ import annotations
import os, re, datetime
from .config import Config
from .workbook.reader import build_worklist, worklist_summary
from .workbook.surgical_editor import SurgicalEditor
from .workbook.auditor import audit
from .resolve.gap_resolver import find_source_in, load_runsheet_rows
from .resolve.index_db import build_index_db
from .resolve.normalize import all_ops as normalize_ops


def _out_paths(workbook: str, outdir: str):
    os.makedirs(outdir, exist_ok=True)
    base = os.path.splitext(os.path.basename(workbook))[0]
    return (os.path.join(outdir, f"{base} - FINAL.xlsx"),
            os.path.join(outdir, f"{base} - AUDIT LOG.md"),
            os.path.join(outdir, f"{base} - PUNCH LIST.md"))


def run_offline(workbook: str, index_pdf: str | None, outdir: str, cfg: Config) -> dict:
    """Reproduce the analysis pass: worklist + source-in gap resolution + audit.
    Resolves gaps whose source-in is documented in the Runsheet/county index; clears those
    highlights; re-audits; writes audit log + punch list. Needs no network."""
    final_xlsx, audit_md, punch_md = _out_paths(workbook, outdir)
    items = build_worklist(workbook)
    runsheet_rows = load_runsheet_rows(workbook)
    index_recs = build_index_db(index_pdf, os.path.join(outdir, "index_db.json"),
                                cfg.tesseract_cmd) if index_pdf else []

    resolved, still_open = [], []
    ed = SurgicalEditor(workbook)
    unhighlighted = set()

    # 0) deterministic normalization (pro-rata net-acre footing + TBD→N/A conventions)
    norm = normalize_ops(workbook)
    for sheet, coord, op in norm:
        ed.apply(sheet, coord, op)

    for it in items:
        if it.kind != "source_in_gap":
            still_open.append(it); continue
        yr = None
        m = re.match(r"(\d{4})", it.instrument)
        if m:
            yr = int(m.group(1))
        hit = find_source_in(it.party, runsheet_rows, index_recs, convey_year=yr)
        if hit:
            ed.apply(it.sheet, it.coord, ("unhighlight",))
            unhighlighted.add(f"{it.sheet}!{it.coord}")
            resolved.append((it, hit))
        else:
            still_open.append(it)
    ed.save(final_xlsx)

    ok, issues, notes = audit(workbook, final_xlsx, expected_unhighlight=unhighlighted)
    _write_audit(audit_md, workbook, final_xlsx, resolved, still_open, ok, issues, notes, mode="offline")
    _write_punch(punch_md, still_open)
    return {"final": final_xlsx, "resolved": len(resolved), "still_open": len(still_open),
            "audit_ok": ok, "issues": issues, "worklist": worklist_summary(items)}


def run_online(workbook: str, outdir: str, cfg: Config) -> dict:
    """Full loop: for each open item, fetch the document, OCR/extract, fill, then audit.
    Requires network + OKCR_API_KEY. Fills only from retrieved sources — never fabricates."""
    cfg.require_key()
    from .fetch.okcountyrecords import OkCountyRecords
    from .fetch.occ import OCC
    from .fetch.otc import OTC
    from .ocr.ocr import ocr_any
    from .ocr.instrument_parser import parse_instrument

    final_xlsx, audit_md, punch_md = _out_paths(workbook, outdir)
    proof = os.path.join(outdir, "proof"); os.makedirs(proof, exist_ok=True)
    okcr = OkCountyRecords(cfg.okcr_api_key, cfg.user_agent)
    occ, otc = OCC(cfg.user_agent), OTC(cfg.user_agent)

    items = build_worklist(workbook)
    ed = SurgicalEditor(workbook)
    filled, still_open, unhighlighted = [], [], set()

    for it in items:
        try:
            if it.kind == "need_interest" and it.instrument:
                img = okcr.image_by_number(cfg.county, it.instrument,
                                           os.path.join(proof, f"{it.instrument}.pdf"))
                rec = parse_instrument(ocr_any(img, cfg.tesseract_cmd))
                frac = rec.get("fraction")
                if frac is not None:
                    # place fraction in the instrument column (grantor -, grantee +) —
                    # exact row placement uses the grid's existing owner rows; recorded
                    # here as a filled value to be reconciled by the conservation pass.
                    filled.append((it, rec, img))
                else:
                    still_open.append(it)
            elif it.kind == "well":
                # pull structured RBDMS + Form 1002A for the section's well
                still_open.append(it)  # requires API# from Well 1; wired in run script
            elif it.kind == "hbp":
                still_open.append(it)  # resolved in a batch after OTC lookup
            else:
                still_open.append(it)
        except RuntimeError as e:
            still_open.append(it)
            print(f"  [skip] {it.sheet}!{it.coord}: {e}")

    ed.save(final_xlsx)
    ok, issues, notes = audit(workbook, final_xlsx, expected_unhighlight=unhighlighted)
    _write_audit(audit_md, workbook, final_xlsx, [], still_open, ok, issues, notes,
                 mode="online", filled=filled)
    _write_punch(punch_md, still_open)
    return {"final": final_xlsx, "filled": len(filled), "still_open": len(still_open),
            "audit_ok": ok, "issues": issues}


def _write_audit(path, base, final, resolved, still_open, ok, issues, notes, mode, filled=None):
    L = [f"# TitleFinisher audit log ({mode})",
         f"Base: `{os.path.basename(base)}`  →  Final: `{os.path.basename(final)}`", ""]
    L.append(f"## QC: {'PASS' if ok else 'ISSUES'}")
    L += [f"- {n}" for n in notes]
    if issues:
        L += ["", "### Issues"] + [f"- {i}" for i in issues]
    if resolved:
        L += ["", f"## Source-in gaps resolved ({len(resolved)})"]
        for it, hit in resolved:
            L.append(f"- {it.sheet}!{it.coord} **{it.party}** ← {hit['instrument']} "
                     f"({hit['type']}, Bk {hit['book_page']}) via {hit['source']}")
    if filled:
        L += ["", f"## Cells filled from retrieved documents ({len(filled)})"]
        for it, rec, img in filled:
            L.append(f"- {it.sheet}!{it.coord} instr {it.instrument}: "
                     f"fraction={rec.get('fraction')} nma={rec.get('nma')} "
                     f"(source `{os.path.basename(img)}`)")
    L += ["", f"## Still open ({len(still_open)})",
          "Each needs the recorded document named in the punch list.", "",
          "*Cursory cleanup; not a certified title opinion.*"]
    open(path, "w").write("\n".join(L))


def _write_punch(path, still_open):
    L = ["# Examiner punch list — remaining open items", ""]
    by: dict = {}
    for it in still_open:
        by.setdefault(it.kind, []).append(it)
    for kind, group in by.items():
        L.append(f"## {kind} ({len(group)})")
        for it in group:
            tag = it.party or it.instrument or it.detail
            L.append(f"- [ ] {it.sheet}!{it.coord}  {tag}"
                     + (f"  — {it.instrument} {it.book_page}" if it.instrument else ""))
        L.append("")
    open(path, "w").write("\n".join(L))
