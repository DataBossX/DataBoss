"""Process fetched OKCountyRecords PDFs into reimport-ready rows.

For each downloaded instrument PDF: render pages -> vision-extract the title
fields (needs a vision key: ANTHROPIC_API_KEY or OPENAI_API_KEY) -> emit a CSV in
the re-import template format (action=add, approve=no) so you review each one,
set approve=yes, and write it into the workbook with the format-preserving
writer. Low-confidence reads are flagged, never trusted silently.

Run on YOUR machine after `fetch --confirm`:
    python -m cursory_title_app.okcounty.process
    # -> edit the CSV, set approve=yes on verified rows, then:
    python -c "from cursory_title_app.reports import reimport; from pathlib import Path; \
               print(reimport.apply_csv(Path('WORKBOOK.xlsx'), Path('okcounty_reimport.csv')))"
"""
from __future__ import annotations

import csv
from pathlib import Path

from .. import config
from ..db import store
from ..index import render
from ..browser import doc_worker
from ..reports import reimport


def process(pdf_dir: Path | None = None, out_csv: Path | None = None) -> dict:
    pdf_dir = Path(pdf_dir or (config.DATA_DIR / "okcounty_pdfs"))
    out_csv = Path(out_csv or (config.OUTPUT_DIR / "okcounty_reimport.csv"))
    config.ensure_dirs()
    store.init()

    pdfs = sorted(pdf_dir.glob("*.pdf"))
    if not pdfs:
        return {"error": f"No PDFs in {pdf_dir}. Run `fetch --confirm` first."}

    rows, done, errors = [], 0, []
    for pdf in pdfs:
        number = pdf.stem.replace("_", "-")
        q = store.fetch_one(
            "SELECT id FROM work_queue WHERE instrument_number=? ORDER BY id DESC",
            (number,))
        qid = q["id"] if q else 0
        try:
            imgs = render.render_pdf(pdf, out_dir=config.PAGES_DIR / pdf.stem)
            ext = doc_worker.extract_from_images([str(p) for p in imgs], qid,
                                                 source_url=number)
            row = {c: "" for c in reimport.CSV_COLUMNS}
            row.update(
                action="add", approve="no",
                confidence=f"{ext.confidence:.2f}",
                instrument_number=ext.instrument_number or number,
                doc_type=ext.doc_type or ext.doc_type_original or "",
                book_page=ext.book_page or "",
                effective_date=ext.effective_date or "",
                recorded_date=ext.recorded_date or "",
                grantor=ext.grantor or "", grantee=ext.grantee or "",
                legal_description=ext.legal_description or "",
                tracts=ext.tracts or "",
                conveyance_type=ext.conveyance_type or ext.classification or "",
                conveyance_amount_dec=(ext.conveyance_amount_dec
                                       if ext.conveyance_amount_dec is not None else ""),
                document_link=number,
                notes=ext.notes or "",
                review="; ".join(ext.review_flags),
                need_action="; ".join(ext.need_flags),
            )
            rows.append(row)
            done += 1
            if q:
                store.execute("UPDATE work_queue SET status='extracted' WHERE id=?", (qid,))
            print(f"  {pdf.name}: conf {ext.confidence:.2f} {ext.grantor or '?'} -> {ext.grantee or '?'}")
        except Exception as e:
            errors.append({"pdf": pdf.name, "error": str(e)})
            store.audit("okcounty_process_error", f"{pdf.name}: {e}")
            print(f"  {pdf.name}: ERROR {e}")

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=reimport.CSV_COLUMNS)
        w.writeheader()
        w.writerows(rows)
    return {"processed": done, "errors": errors, "csv": str(out_csv),
            "next": "Edit the CSV, set approve=yes on verified rows, then run reimport.apply_csv."}


if __name__ == "__main__":
    import json
    print(json.dumps(process(), indent=2, default=str))
