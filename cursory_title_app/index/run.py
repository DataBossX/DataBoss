"""End-to-end index pipeline (resumable):

    render handwritten index PDF  ->  vision-extract each page  ->  store rows
    ->  diff against the existing Runsheet  ->  missing-instruments report

Usage:
    python -m cursory_title_app.index.run INDEX.pdf WORKBOOK.xlsx [--reset]
                                          [--pages 1-10] [--provider claude]

Needs a vision provider configured (ANTHROPIC_API_KEY or OPENAI_API_KEY).
For an offline wiring test:  CTA_MODEL_ORDER=mock python -m cursory_title_app.index.run ...
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .. import config
from ..db import store
from . import render, extract
from ..runsheet import analyzer


def _already_extracted_pages() -> set[int]:
    rows = store.fetch_all("SELECT DISTINCT page_number FROM index_rows")
    return {r["page_number"] for r in rows}


def _parse_pages(spec: str | None, n: int) -> list[int]:
    if not spec:
        return list(range(1, n + 1))
    out: list[int] = []
    for part in spec.split(","):
        if "-" in part:
            a, b = part.split("-")
            out += list(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return [p for p in out if 1 <= p <= n]


def missing_report() -> dict:
    missing = store.fetch_all(
        "SELECT id,book_page,doc_type,grantor,grantee FROM work_queue "
        "WHERE diff_kind='missing' ORDER BY id")
    conflict = store.fetch_all(
        "SELECT id,book_page,doc_type,grantor,grantee,runsheet_row FROM work_queue "
        "WHERE diff_kind='conflict' ORDER BY id")
    present = store.fetch_all("SELECT COUNT(*) c FROM work_queue WHERE diff_kind='present'")
    return {"missing": missing, "conflict": conflict,
            "present_count": present[0]["c"] if present else 0}


def run(pdf: Path, workbook: Path, pages_spec=None, reset=False) -> dict:
    config.ensure_dirs()
    store.init()
    if reset:
        store.execute("DELETE FROM index_rows")
        store.execute("DELETE FROM work_queue WHERE source='index'")

    n = render.page_count(pdf)
    targets = _parse_pages(pages_spec, n)

    # Render only pages we still need (resume-friendly).
    done = _already_extracted_pages()
    todo = [p for p in targets if p not in done]
    print(f"[index] {n} pages total; {len(targets)} targeted; "
          f"{len(done)} already extracted; {len(todo)} to do.")

    # Render the whole PDF once (cheap) then extract only needed pages.
    imgs = render.render_pdf(pdf)
    for p in todo:
        img = imgs[p - 1]
        try:
            rows = extract.extract_page(img, p)
            print(f"  page {p}: {len(rows)} rows extracted")
        except Exception as e:  # fail loud, keep going, resume later
            store.audit("index_page_error", f"page {p}: {e}")
            print(f"  page {p}: ERROR {e}")

    diff = analyzer.analyze(workbook)
    rep = missing_report()
    from ..reports import export as pull_export
    exported = pull_export.export()
    summary = {
        "pages_total": n,
        "pages_extracted": len(_already_extracted_pages()),
        "diff": diff,
        "missing_instruments": len(rep["missing"]),
        "conflicts": len(rep["conflict"]),
        "present": rep["present_count"],
        "pull_list_csv": exported["csv"],
        "pull_list_xlsx": exported["xlsx"],
    }

    out_json = config.DATA_DIR / "index_missing_report.json"
    out_json.write_text(json.dumps({"summary": summary, **rep}, indent=2, default=str))
    print(json.dumps(summary, indent=2))
    print(f"[written] {out_json}")
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("workbook")
    ap.add_argument("--pages", default=None)
    ap.add_argument("--provider", default=None,
                    help="override CTA_MODEL_ORDER, e.g. claude / openai / mock")
    ap.add_argument("--reset", action="store_true")
    a = ap.parse_args()
    if a.provider:
        os.environ["CTA_MODEL_ORDER"] = a.provider
        config.MODEL_PROVIDER_ORDER = [a.provider]
    run(Path(a.pdf), Path(a.workbook), a.pages, a.reset)


if __name__ == "__main__":
    main()
