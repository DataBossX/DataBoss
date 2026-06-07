"""End-to-end pipeline orchestration.

Order of operations:
  1. inventory local files
  2. (optional) download county records
  3. process documents in parallel: OCR -> classify -> extract
  4. read existing workbook sheets / index
  5. multi-AI tournament review
  6. build index, run sheet (chain of title), OGL, well data
  7. assemble all 10 workbook sheets
  8. write workbook, run QC, export artifacts
  9. second QC pass + light auto-fix, re-export
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List

from . import (
    chain_of_title_builder,
    document_classifier,
    file_inventory,
    index_builder,
    multi_ai_tournament_reviewer as reviewer,
    ogl_analyzer,
    okcounty_browser_downloader as downloader,
    quality_control,
    well_data_collector,
)
from .config_loader import RunConfig
from .excel_template_writer import write_workbook
from .extractors import interest as interest_x
from .extractors import legal_description as legal_x
from .extractors import party_and_date as party_x
from .final_report_exporter import (
    export_completion_summary,
    export_confidence_summary,
    export_curative,
    export_index_json,
    export_ocr_cache,
    export_source_inventory,
)
from .models import Document, PipelineResult, SourceFile
from .ocr_engine import backends_available, extract_text
from .utils import (
    LOG,
    NEEDS_REVIEW,
    NOT_FOUND,
    UNKNOWN,
    clamp_score,
    sha256_text,
    short_date,
)


def _dedupe(names: List[str]) -> List[str]:
    """Case-insensitive de-duplication that preserves first-seen order."""
    seen, out = set(), []
    for n in names:
        key = n.strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append(n.strip())
    return out


def _process_one(sf: SourceFile, cfg: RunConfig, seq: int) -> Document:
    """OCR -> classify -> extract for a single non-Excel document."""
    sp = cfg.subject_property
    extracted = extract_text(Path(sf.path), enable_ocr=cfg.enable_ocr)
    text = extracted.text or ""

    doc_type, cls_conf, _ = document_classifier.classify(text)
    legal = legal_x.extract_legal(text, sp.county, sp.state)
    parties = party_x.extract_parties(text)
    dates = party_x.extract_dates(text)
    recdata = party_x.extract_recording_data(text)
    money = interest_x.extract_interest(text, doc_type)

    grantors = _dedupe(parties.get("grantor", []) + parties.get("lessor", [])
                       + parties.get("assignor", []))
    grantees = _dedupe(parties.get("grantee", []) + parties.get("lessee", [])
                       + parties.get("assignee", []))

    on_subject = legal_x.matches_subject(legal, sp.section, sp.township, sp.range)
    relevance = 90.0 if on_subject else (50.0 if legal.section else 25.0)

    issues: List[str] = []
    if extracted.note:
        issues.append(extracted.note)
    if not legal.section:
        issues.append("Legal description not machine-readable; subject match unconfirmed.")
    if extracted.ocr_used and (extracted.ocr_confidence or 0) < 60:
        issues.append(f"Low OCR confidence ({extracted.ocr_confidence:.0f}).")

    return Document(
        doc_id=f"D{seq:04d}",
        source_file=sf.path,
        matched_document=doc_type,
        document_type=doc_type,
        instrument_no=recdata.get("instrument_no", ""),
        book_page=recdata.get("book_page", ""),
        recording_date=dates.get("recording_date", ""),
        execution_date=dates.get("execution_date", ""),
        effective_date=dates.get("effective_date", ""),
        grantors=grantors,
        grantees=grantees,
        legal=legal,
        interest=money.get("interest", ""),
        lease_terms=money.get("lease_terms", ""),
        royalty=money.get("royalty", ""),
        gross_acres=money.get("gross_acres", ""),
        net_acres="",
        notes="",
        title_effect="",
        source_reference=sf.name,
        text=text,
        text_hash=sha256_text(text),
        ocr_used=extracted.ocr_used,
        ocr_confidence=extracted.ocr_confidence,
        classification_confidence=cls_conf,
        match_confidence=cls_conf,
        relevance_confidence=relevance,
        issues=issues,
    )


def run_pipeline(cfg: RunConfig) -> PipelineResult:
    sp = cfg.subject_property
    out_dir = cfg.resolved_output_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    result = PipelineResult()
    tools = ["file_inventory", "document_classifier", "index_builder",
             "chain_of_title_builder", "excel_template_writer", "quality_control"]
    tools += backends_available()

    # --- 1. inventory ----------------------------------------------------
    files = file_inventory.inventory_files(cfg.resolved_input_dirs())
    export_source_inventory(files, out_dir)

    # --- 2. optional download -------------------------------------------
    download_log = out_dir / "download_log.json"
    dl_entries = downloader.download_records(
        sp.search_variations, sp.county, out_dir / "downloads",
        download_log, enable=cfg.enable_download)
    result.documents_downloaded_count = sum(
        len(e.get("downloaded_files", [])) for e in dl_entries)
    if cfg.enable_download:
        tools.append("okcounty_browser_downloader")
    # Re-inventory to pick up anything downloaded.
    if result.documents_downloaded_count:
        files = file_inventory.inventory_files(
            cfg.resolved_input_dirs() + [out_dir / "downloads"])

    # --- 3. process documents in parallel (skip excel containers) -------
    doc_files = [f for f in files if f.kind in ("pdf", "image", "text") and not f.note.startswith("Duplicate")]
    docs: List[Document] = []
    if doc_files:
        with ThreadPoolExecutor(max_workers=max(1, cfg.parallel_workers)) as ex:
            futs = {ex.submit(_process_one, sf, cfg, i + 1): sf
                    for i, sf in enumerate(doc_files)}
            for fut in as_completed(futs):
                try:
                    docs.append(fut.result())
                except Exception as exc:  # pragma: no cover
                    LOG.error("Processing failed for %s: %s", futs[fut].name, exc)
                    result.errors_or_limitations.append(
                        f"Processing failed for {futs[fut].name}: {exc}")
    docs.sort(key=lambda d: d.doc_id)
    result.documents_reviewed_count = len(docs)
    result.documents_ocr_count = sum(1 for d in docs if d.ocr_used)

    # --- 4. read existing workbooks -------------------------------------
    existing: Dict[str, Dict[str, dict]] = {}
    for f in files:
        if f.kind == "excel" and not f.note.startswith("Duplicate"):
            existing[f.name] = index_builder.read_existing_workbook(Path(f.path))

    # --- 5. multi-AI tournament review ----------------------------------
    consensuses = reviewer.review_all(docs)
    if any(p.engine == "llm" for c in consensuses for p in c.passes):
        tools.append("llm")
    tools.append("multi_ai_tournament_reviewer")
    cons_by_doc = {c.document_id: c for c in consensuses}
    for d in docs:
        c = cons_by_doc.get(d.doc_id)
        if not c:
            continue
        d.title_effect = c.consensus.get("title_effect", NEEDS_REVIEW)
        for iss in c.consensus.get("issues", []):
            if iss not in d.issues:
                d.issues.append(iss)
        if not c.agreed:
            d.issues.append("Review passes disagreed -- flagged, not forced.")
        d.relevance_confidence = clamp_score(
            (d.relevance_confidence or 0) * 0.6 + c.confidence * 0.4)

    # --- 6. build derived tables ----------------------------------------
    well_rows = well_data_collector.collect_well_data(
        existing, sp.section, sp.township, sp.range, cfg.enable_download)
    tools.append("well_data_collector")
    run_rows, chain_issues = chain_of_title_builder.build_run_sheet(docs)
    ogl_rows = ogl_analyzer.build_ogl_rows(docs, well_rows)
    tools.append("ogl_analyzer")
    index_rows = index_builder.build_index(docs, existing)
    result.index_rows_created_count = len(index_rows)

    # Curative issues = chain issues + per-doc red-team issues.
    curative = _collect_curative(chain_issues, docs, files)

    # --- 7. assemble sheets ---------------------------------------------
    sheets = _assemble_sheets(cfg, files, docs, run_rows, ogl_rows,
                              well_rows, index_rows, curative, existing)

    # --- 8. write workbook + QC + export --------------------------------
    out_path = out_dir / cfg.output_file_name
    write_workbook(out_path, sheets, cfg.template_workbook)
    qc = quality_control.run_qc(sheets, out_path, files, download_log)

    # --- 9. second QC pass with light auto-fix --------------------------
    sheets, fixes = _autofix(sheets, qc)
    if fixes:
        write_workbook(out_path, sheets, cfg.template_workbook)
        qc = quality_control.run_qc(sheets, out_path, files, download_log)
        result.errors_or_limitations.extend(fixes)

    # Refresh confidence summary sheet with final QC numbers, rewrite once more.
    sheets["Confidence Summary"] = _confidence_sheet(qc, docs)
    write_workbook(out_path, sheets, cfg.template_workbook)

    # --- exports ---------------------------------------------------------
    export_ocr_cache(docs, out_dir)
    export_index_json(index_rows, out_dir)
    export_confidence_summary(qc, out_dir)
    export_curative([c.model_dump() for c in curative],
                    _missing_documents(docs, curative), out_dir)

    # --- populate result -------------------------------------------------
    result.workbook_path = str(out_path)
    result.overall_confidence_score = qc["overall_confidence"]
    result.major_title_findings = _major_findings(docs, run_rows, ogl_rows, well_rows)
    result.missing_documents = _missing_documents(docs, curative)
    result.curative_issues = [f"[{c.severity}] {c.description}" for c in curative]
    result.tools_used = sorted(set(tools))
    result.errors_or_limitations.extend(_limitations(files, docs))
    export_completion_summary(result, out_dir)
    return result


# --------------------------------------------------------------------------
# Sheet assembly
# --------------------------------------------------------------------------
def _assemble_sheets(cfg, files, docs, run_rows, ogl_rows, well_rows,
                     index_rows, curative, existing) -> Dict[str, dict]:
    sp = cfg.subject_property
    subj = f"Section {sp.section}-{sp.township}-{sp.range}, {sp.county}, {sp.state}"

    overview_rows = [
        {"Field": "Entity / Client", "Value": sp.entity, "Notes": ""},
        {"Field": "Subject Property", "Value": subj, "Notes": ""},
        {"Field": "County / State", "Value": f"{sp.county}, {sp.state}", "Notes": ""},
        {"Field": "Section-Township-Range", "Value": f"{sp.section}-{sp.township}-{sp.range}", "Notes": ""},
        {"Field": "Report Type", "Value": "Cursory Title Report", "Notes": "Automated, attorney review required"},
        {"Field": "Source Files Inventoried", "Value": len(files), "Notes": "See Source Notes sheet"},
        {"Field": "Documents Processed", "Value": len(docs), "Notes": "OCR/classified/extracted"},
        {"Field": "Index Rows", "Value": len(index_rows), "Notes": "See Index Text sheet"},
        {"Field": "Run-Sheet Entries", "Value": len(run_rows), "Notes": "Chain of title"},
        {"Field": "Leases Identified", "Value": len(ogl_rows), "Notes": "See OGL sheet"},
        {"Field": "Curative / Issue Count", "Value": len(curative), "Notes": "See Curative Issues sheet"},
        {"Field": "Disclaimer", "Value":
            "Best-effort automated cursory report. Conclusions labeled apparent unless "
            "fully verified. Not a title opinion or guarantee.", "Notes": "Truth rule enforced"},
    ]

    title_rows = _title_sheet_rows(sp, docs, run_rows, ogl_rows, well_rows)
    plat_rows = _plat_sheet_rows(sp, docs)
    source_rows = _source_notes_rows(files, existing)
    curative_sheet_rows = [{
        "Issue ID": c.issue_id,
        "Category": c.category,
        "Severity": c.severity,
        "Description": c.description,
        "Related Documents": "; ".join(c.related_documents) or "N/A",
        "Recommendation": c.recommendation,
        "Confidence": c.confidence or 0,
    } for c in curative] or [{
        "Issue ID": "none", "Category": "info", "Severity": "low",
        "Description": "No curative issues recorded (note: limited by available source documents).",
        "Related Documents": "N/A", "Recommendation": "N/A", "Confidence": 0,
    }]

    return {
        "Overview": {"title": "Cursory Title Report", "subtitle": subj,
                     "headers": ["Field", "Value", "Notes"], "rows": overview_rows},
        "Title": {"title": "Title Summary", "subtitle": subj,
                  "headers": ["Item", "Determination", "Basis / Source", "Confidence", "Notes"],
                  "rows": title_rows},
        "PLAT": {"title": "Plat / Legal Description", "subtitle": subj,
                 "headers": ["Tract", "Quarter Calls", "Section", "Township", "Range",
                             "County", "Gross Acres", "Source", "Confidence"],
                 "rows": plat_rows},
        "Run Sheet": {"title": "Run Sheet (Chain of Title)", "subtitle": subj,
                      "headers": list(run_rows[0].keys()) if run_rows else
                      ["No.", "Document Type", "Grantor", "Grantee", "Execution Date",
                       "Effective Date", "Recording Date", "Instrument No.", "Book/Page",
                       "Legal Description", "Interest/Lands Affected", "Title Notes",
                       "Source", "Confidence"],
                      "rows": run_rows or [_empty_run_row()]},
        "OGL": {"title": "Oil & Gas Leases", "subtitle": subj,
                "headers": list(ogl_rows[0].keys()) if ogl_rows else _ogl_headers(),
                "rows": ogl_rows or [_empty_ogl_row()]},
        "Well Data": {"title": "Well & Production Data", "subtitle": subj,
                      "headers": list(well_rows[0].keys()) if well_rows else _well_headers(),
                      "rows": well_rows},
        "Index Text": {"title": "Full-Text Index", "subtitle": subj,
                       "headers": list(index_rows[0].keys()) if index_rows else _index_headers(),
                       "rows": index_rows or [_empty_index_row()]},
        "Source Notes": {"title": "Source Document Inventory & Notes", "subtitle": subj,
                         "headers": ["Source File", "Kind", "Size (bytes)", "SHA-256 (short)",
                                     "Pages/Sheets", "Notes"],
                         "rows": source_rows},
        "Confidence Summary": {"title": "Confidence Summary", "subtitle": subj,
                               "headers": ["Scope", "Score (0-100)", "Band", "Notes"],
                               "rows": [{"Scope": "Pending", "Score (0-100)": 0,
                                         "Band": "", "Notes": "computed in QC"}]},
        "Curative Issues": {"title": "Curative Issues & Missing Documents", "subtitle": subj,
                            "headers": ["Issue ID", "Category", "Severity", "Description",
                                        "Related Documents", "Recommendation", "Confidence"],
                            "rows": curative_sheet_rows},
    }


def _title_sheet_rows(sp, docs, run_rows, ogl_rows, well_rows):
    from .utils import confidence_band
    on_subject = [d for d in docs if d.legal.section]
    have_prod = any(str(w.get("Status", "")).lower() in ("active", "producing")
                    for w in well_rows)
    rows = [
        {"Item": "Apparent Current Mineral Owner(s)",
         "Determination": _apparent_owner(run_rows),
         "Basis / Source": "Last conveyance in run sheet" if run_rows else "No conveyances found",
         "Confidence": run_rows[-1]["Confidence"] if run_rows else 0,
         "Notes": "Apparent only; not assumed from name similarity"},
        {"Item": "Lease Status",
         "Determination": (f"{len(ogl_rows)} lease(s) identified" if ogl_rows else NOT_FOUND),
         "Basis / Source": "OGL sheet",
         "Confidence": 60 if ogl_rows else 0,
         "Notes": "HBP not assumed without production data"},
        {"Item": "Held By Production",
         "Determination": ("Possible -- production present" if have_prod else "Undetermined"),
         "Basis / Source": "Well Data sheet",
         "Confidence": 50 if have_prod else 10,
         "Notes": "Verify lease/unit linkage"},
        {"Item": "Documents On Subject Lands",
         "Determination": f"{len(on_subject)} of {len(docs)} with readable legal",
         "Basis / Source": "Legal description extractor",
         "Confidence": 70 if on_subject else 20,
         "Notes": ""},
        {"Item": "Root of Title",
         "Determination": NEEDS_REVIEW,
         "Basis / Source": "Not established from available records",
         "Confidence": 10,
         "Notes": "Patent / base deed not located"},
    ]
    for r in rows:
        r["Notes"] = (r["Notes"] + "; " if r["Notes"] else "") + confidence_band(r["Confidence"])
    return rows


def _apparent_owner(run_rows):
    if not run_rows:
        return NOT_FOUND
    last = run_rows[-1]
    return last.get("Grantee") or NOT_FOUND


def _plat_sheet_rows(sp, docs):
    calls = []
    for d in docs:
        for q in d.legal.quarter_calls:
            calls.append(q)
    seen = []
    for c in calls:
        if c.lower() not in (x.lower() for x in seen):
            seen.append(c)
    return [{
        "Tract": 1,
        "Quarter Calls": "; ".join(seen) if seen else (UNKNOWN + " (full section assumed if no calls)"),
        "Section": sp.section,
        "Township": sp.township,
        "Range": sp.range,
        "County": sp.county,
        "Gross Acres": "640 (nominal full section)" if not seen else NEEDS_REVIEW,
        "Source": "Aggregated from document legal descriptions",
        "Confidence": 70 if seen else 30,
    }]


def _source_notes_rows(files, existing):
    rows = []
    for f in files:
        pages = f.pages
        if f.name in existing:
            pages = len(existing[f.name])
        rows.append({
            "Source File": f.name,
            "Kind": f.kind,
            "Size (bytes)": f.size_bytes,
            "SHA-256 (short)": f.sha256[:16],
            "Pages/Sheets": pages if pages is not None else "",
            "Notes": f.note or "",
        })
    if not rows:
        rows.append({
            "Source File": NOT_FOUND, "Kind": "", "Size (bytes)": "",
            "SHA-256 (short)": "", "Pages/Sheets": "",
            "Notes": "No source documents were present in the inputs folder for this run.",
        })
    return rows


def _confidence_sheet(qc, docs):
    from .utils import confidence_band
    rows = [{"Scope": "OVERALL", "Score (0-100)": qc["overall_confidence"],
             "Band": confidence_band(qc["overall_confidence"]),
             "Notes": f"{qc['checks_passed']}/{qc['checks_total']} QC checks passed"}]
    for sheet, score in qc["per_sheet_confidence"].items():
        rows.append({"Scope": f"Sheet: {sheet}", "Score (0-100)": score,
                     "Band": confidence_band(score), "Notes": ""})
    for d in docs:
        rows.append({"Scope": f"Doc: {d.doc_id} ({d.document_type})",
                     "Score (0-100)": clamp_score(d.relevance_confidence) or 0,
                     "Band": confidence_band(d.relevance_confidence),
                     "Notes": "; ".join(d.issues[:2])})
    for c in qc["checks"]:
        rows.append({"Scope": f"QC: {c['check']}",
                     "Score (0-100)": 100 if c["passed"] else 0,
                     "Band": "PASS" if c["passed"] else "FAIL",
                     "Notes": c["detail"]})
    return {"title": "Confidence Summary", "subtitle": "Per-sheet, per-document, and QC scores",
            "headers": ["Scope", "Score (0-100)", "Band", "Notes"], "rows": rows}


# --------------------------------------------------------------------------
# Curative / findings / limitations
# --------------------------------------------------------------------------
def _collect_curative(chain_issues, docs, files):
    from .models import CurativeIssue
    issues = list(chain_issues)
    for d in docs:
        for note in d.issues:
            if any(k in note.lower() for k in
                   ("ocr", "not machine-readable", "disagreed", "no parties",
                    "no recording", "no instrument")):
                issues.append(CurativeIssue(
                    issue_id=f"doc-{d.doc_id}-{abs(hash(note)) % 9999:04d}",
                    category="ambiguity" if "disagree" in note.lower() else "ocr"
                    if "ocr" in note.lower() else "ambiguity",
                    severity="medium",
                    description=f"{d.doc_id} ({d.document_type}): {note}",
                    related_documents=[d.doc_id],
                    recommendation="Re-examine source document; obtain a clearer copy if needed.",
                    confidence=55.0,
                ))
    if not files:
        issues.append(CurativeIssue(
            issue_id="no-sources",
            category="missing_doc", severity="high",
            description="No source documents were available in the run environment "
                        "(known input workbooks/PDFs were not present).",
            recommendation="Place the county records, runsheet, and prior workbooks in the "
                           "inputs/ folder, then re-run the pipeline.",
            confidence=95.0,
        ))
    return issues


def _missing_documents(docs, curative):
    missing = []
    if not any("patent" in d.document_type.lower() for d in docs):
        missing.append("Base patent / root of title for the subject lands")
    if not any("lease" in d.document_type.lower() for d in docs):
        missing.append("Current oil & gas lease(s) covering the subject interest")
    if not docs:
        missing.append("All primary source instruments (none were available this run)")
    for c in curative:
        if c.category == "missing_doc" and c.description not in missing:
            missing.append(c.description)
    return missing


def _major_findings(docs, run_rows, ogl_rows, well_rows):
    findings = []
    if not docs:
        findings.append("No source documents were available; no title conclusions could be "
                        "drawn. The workbook is a fully-structured template ready for inputs.")
        return findings
    findings.append(f"{len(docs)} document(s) processed; {len(run_rows)} conveyance(s) "
                    f"placed in the chain of title.")
    if ogl_rows:
        findings.append(f"{len(ogl_rows)} oil & gas lease(s) identified.")
    on_subj = [d for d in docs if d.legal.section]
    findings.append(f"{len(on_subj)} document(s) carried a machine-readable legal description.")
    if not any(str(w.get('Status', '')).lower() in ('active', 'producing') for w in well_rows):
        findings.append("No production data found; held-by-production status is undetermined.")
    return findings


def _limitations(files, docs):
    lim = []
    from .ocr_engine import backends_available
    backends = backends_available()
    if "tesseract" not in backends:
        lim.append("OCR backend (tesseract) not installed; image-only PDFs cannot be read.")
    if not files:
        lim.append("Inputs folder was empty; the run produced an honest empty-state workbook.")
    if files and not docs:
        lim.append("Only container/Excel files were present; no primary instruments to OCR.")
    from .llm import llm_available
    if not llm_available():
        lim.append("LLM tournament ran in deterministic heuristic-only mode (no API key set).")
    return lim


# --- empty-row helpers -----------------------------------------------------
def _ogl_headers():
    return ["Lease No.", "Lessor", "Lessee", "Lease Date", "Effective Date",
            "Recording Date", "Instrument No.", "Book/Page", "Legal Description",
            "Gross Acres", "Net Acres", "Royalty", "Primary Term", "Extension/Option",
            "Assignments", "Current Lessee/Operator if Determinable", "HBP Notes",
            "Source", "Confidence"]


def _well_headers():
    return ["Well Name", "API", "Operator", "Location", "Section-Township-Range",
            "Formation", "Status", "Spud Date", "Completion Date", "First Production",
            "Last Production Found", "Lease/Unit", "HBP Relevance", "Source", "Notes",
            "Confidence"]


def _index_headers():
    return ["Index No.", "Source File", "Matched Document", "Document Type",
            "Instrument No.", "Book/Page", "Recording Date", "Execution Date",
            "Effective Date", "Grantor/Lessor/Assignor", "Grantee/Lessee/Assignee",
            "Legal Description", "Interest Conveyed/Reserved/Affected",
            "Oil & Gas Lease Terms", "Royalty", "Gross Acres", "Net Acres",
            "Important Notes", "Title Effect", "Source Reference", "OCR Confidence",
            "Document Match Confidence", "Title Relevance Confidence"]


def _empty_run_row():
    return {h: NOT_FOUND for h in
            ["No.", "Document Type", "Grantor", "Grantee", "Execution Date",
             "Effective Date", "Recording Date", "Instrument No.", "Book/Page",
             "Legal Description", "Interest/Lands Affected", "Title Notes",
             "Source", "Confidence"]} | {"No.": 1, "Confidence": 0,
             "Title Notes": "No conveyances available to build a chain of title."}


def _empty_ogl_row():
    return {h: NOT_FOUND for h in _ogl_headers()} | {"Lease No.": 1, "Confidence": 0,
            "HBP Notes": "No leases found in available records."}


def _empty_index_row():
    return {h: NOT_FOUND for h in _index_headers()} | {"Index No.": 1,
            "Important Notes": "No documents indexed (no source files available)."}


def _autofix(sheets, qc):
    """Light, honest auto-fixes: never invent facts, only fill structural gaps."""
    fixes = []
    for name, payload in sheets.items():
        for row in payload.get("rows", []):
            for k, v in list(row.items()):
                if v is None or (isinstance(v, str) and v.strip() == ""):
                    if "confidence" in k.lower():
                        row[k] = 0
                    elif k.lower() in ("notes", "important notes", "title notes",
                                       "extension/option", "net acres", "gross acres",
                                       "royalty", "oil & gas lease terms"):
                        row[k] = ""  # legitimately blank optional fields
                    else:
                        row[k] = NEEDS_REVIEW
    failed = [c for c in qc["checks"] if not c["passed"]]
    if failed:
        fixes.append("Second QC pass found "
                     f"{len(failed)} check(s) needing attention: "
                     + "; ".join(c["check"] for c in failed))
    return sheets, fixes
