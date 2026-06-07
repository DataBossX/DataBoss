"""CLI for title_report_factory.

Example:
    python -m title_report_factory run \
        --section 27 --township 11N --range 25W \
        --county Beckham --state OK --target-owner Diversified \
        --source-dir ./sources --out-dir ./output
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from .models import TractKey, SourceFile
from .inventory import inventory_sources
from .excel_reader import read_workbook_documents
from .ocr import extract_pdf_text, extract_image_text
from .classify import extract_document
from .records import collect_records
from .analysis import build_report
from . import qc
from .workbook import build_workbook, verify_workbook


def _process_sources(sources, tract, source_dir):
    """OCR/extract each source into Documents; mutate SourceFile status in place."""
    documents = []
    limitations = []
    for s in sources:
        full = str(Path(s.where_found) / s.file_name)
        if s.source_type == "Excel":
            docs = read_workbook_documents(full, tract_filter=tract.short)
            s.extraction_status = f"workbook rows: {len(docs)}"
            s.confidence = 60 if docs else 20
            if not docs:
                s.limitations = "No recognizable instrument rows found."
            documents.extend(docs)
        elif s.source_type in ("PDF", "Image"):
            res = (extract_pdf_text(full) if s.source_type == "PDF"
                   else extract_image_text(full))
            s.ocr_status = res.status
            s.pages = res.pages or "Unknown"
            s.confidence = res.confidence
            s.important_text = (res.text or "")[:500]
            if res.text.strip():
                s.extraction_status = "extracted"
                d = extract_document(res.text, s.file_name, res.confidence,
                                     tract.section, tract.township, tract.range)
                documents.append(d)
            else:
                s.extraction_status = "no text"
                s.limitations = f"OCR produced no text ({res.status})."
                if res.status == "no-engine":
                    limitations.append(
                        f"{s.file_name}: no OCR engine installed "
                        "(install pdfplumber/PyMuPDF/pytesseract).")
        elif s.source_type == "Text":
            try:
                text = Path(full).read_text(errors="replace")
            except Exception as e:
                s.extraction_status = "read error"
                s.limitations = str(e)
                continue
            s.important_text = text[:500]
            if text.strip():
                s.extraction_status = "extracted"
                s.confidence = 50
                d = extract_document(text, s.file_name, 90,
                                     tract.section, tract.township, tract.range)
                documents.append(d)
            else:
                s.extraction_status = "empty"
        else:
            s.extraction_status = "skipped (unsupported type)"
            s.limitations = "Type not parsed by this pipeline."
    return documents, limitations


def cmd_run(args) -> int:
    tract = TractKey(section=args.section, township=args.township,
                     range=args.range, county=args.county, state=args.state,
                     target_owner=args.target_owner)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.out_dir) / f"title_run_{tract.short}_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1) Inventory
    sources = inventory_sources(args.source_dir) if args.source_dir else []

    # 2) Extract / OCR
    documents, limitations = _process_sources(sources, tract, args.source_dir or "")

    # 3) Optional records collection (gated)
    coll = collect_records(tract, enabled=args.collect_records)
    search_log = coll.search_log
    if not coll.available:
        limitations.append(f"Record collection: {coll.status}")

    if not sources:
        limitations.append(
            f"No source files found in '{args.source_dir}'. The workbook is an "
            "honest empty skeleton; provide inputs and re-run.")

    # 4) Analysis
    rd = build_report(tract, sources, documents, wells=[],
                      search_log=search_log, limitations=limitations)

    # 5) QC passes 1-3
    qc.run_all(rd)

    # 6) Build workbook
    fname = (f"{tract.target_owner}_Section_{tract.section}_{tract.township}_"
             f"{tract.range}_{tract.county}_County_{tract.state}_"
             "Cursory_Title_Report.xlsx")
    out_path = out_dir / fname
    build_workbook(rd, str(out_path))

    # 7) QC pass 4 (Excel Final Check) + persist into the workbook
    final = verify_workbook(str(out_path))
    rd.qc_results.append(final)
    build_workbook(rd, str(out_path))  # rewrite with the final-check result included
    final2 = verify_workbook(str(out_path))

    summary = {
        "final_workbook_path": str(out_path),
        "overall_confidence_score": rd.confidence.get("Overall Confidence Score", "0"),
        "documents_found": len(sources),
        "documents_ocr_processed": sum(1 for s in sources if s.source_type in ("PDF", "Image")),
        "index_rows_created": len(documents),
        "runsheet_rows_created": len(documents),
        "ogl_rows_created": len(rd.leases),
        "well_data_rows_created": len(rd.wells),
        "qc": rd.qc_results + [final2],
        "limitations": limitations,
    }
    (out_dir / "run_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="title_report_factory",
                                     description="Build a cursory title-report workbook for one PLSS tract.")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="Run the full pipeline.")
    run.add_argument("--section", required=True)
    run.add_argument("--township", required=True)
    run.add_argument("--range", required=True)
    run.add_argument("--county", required=True)
    run.add_argument("--state", required=True)
    run.add_argument("--target-owner", required=True)
    run.add_argument("--source-dir", default="sources",
                     help="Directory of input files (workbooks, PDFs, images, text).")
    run.add_argument("--out-dir", default="output",
                     help="Where timestamped run output is written.")
    run.add_argument("--collect-records", action="store_true",
                     help="Attempt authorized public-record collection (needs credentials).")
    run.set_defaults(func=cmd_run)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
