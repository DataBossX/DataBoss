"""final_report_exporter -- write the machine-readable output artifacts."""
from __future__ import annotations

import json
import os

from ..model import ReportContext


def export_artifacts(ctx: ReportContext, qc: dict, out_dir: str, workbook_path: str) -> dict:
    paths = {}

    def dump(name, obj):
        p = os.path.join(out_dir, name)
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, indent=2, ensure_ascii=False, default=str)
        paths[name] = p

    dump("source_inventory.json", [s.to_dict() for s in ctx.source_files])
    dump("index_text.json", [i.to_dict() for i in ctx.instruments])
    dump("confidence_summary.json", {
        "overall_confidence": qc["overall_confidence"],
        "overall_band": qc["overall_band"],
        "checks_passed": qc["checks_passed"],
        "checks_total": qc["checks_total"],
        "sheet_scores": qc["sheet_scores"],
        "checks": qc["checks"],
        "per_document": [
            {"instrument": i.instrument_no or i.book_page, "doc_type": i.doc_type,
             "match_confidence": i.match_confidence, "relevance_confidence": i.relevance_confidence}
            for i in ctx.instruments
        ],
    })
    dump("curative_issues.json", [c.to_dict() for c in ctx.curative])
    dump("ocr_cache.json", ctx.ocr_cache)
    dump("sources_used.json", ctx.sources_used)

    # Plain-text full index (the "full text index sheet" as text cache).
    idx_txt = os.path.join(out_dir, "index_text.txt")
    with open(idx_txt, "w", encoding="utf-8") as fh:
        for i in ctx.instruments:
            fh.write(f"[{i.index_no}] {i.doc_type} | Inst {i.instrument_no} | Bk/Pg {i.book_page} | "
                     f"{i.recording_date} | {i.grantor} -> {i.grantee} | {i.legal_description} | "
                     f"{i.title_effect} | match={i.match_confidence} rel={i.relevance_confidence}\n")
    paths["index_text.txt"] = idx_txt

    paths["workbook"] = workbook_path
    return paths
