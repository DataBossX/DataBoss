"""Build/serve the county instrument database from the OCR'd Unplatted Legal Index PDF."""
from __future__ import annotations
import json, os
from ..ocr.ocr import ocr_pdf
from ..ocr.instrument_parser import parse_index_page


def build_index_db(index_pdf: str, cache_path: str | None = None,
                   tesseract_cmd: str = "") -> list[dict]:
    if cache_path and os.path.exists(cache_path):
        return json.load(open(cache_path))
    pages = ocr_pdf(index_pdf, tesseract_cmd=tesseract_cmd)
    recs: list[dict] = []
    for p, text in pages.items():
        for rec in parse_index_page(text):
            rec["page"] = p
            recs.append(rec)
    if cache_path:
        os.makedirs(os.path.dirname(cache_path) or ".", exist_ok=True)
        json.dump(recs, open(cache_path, "w"), indent=0)
    return recs
