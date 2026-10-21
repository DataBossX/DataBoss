"""PDF checks on the real PDF geometry: page size/orientation, clipping, row splits, text parity with workbook."""
from __future__ import annotations

import re

import pdfplumber

from .findings import Report
from .model import Sheet

PT = 72.0
EDGE_TOL_PT = 1.0


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def pdf_summary(path: str) -> dict:
    with pdfplumber.open(path) as pdf:
        p0 = pdf.pages[0]
        return {"pages": len(pdf.pages), "width_in": round(float(p0.width) / PT, 3), "height_in": round(float(p0.height) / PT, 3)}


def check_pdf(path: str, rep: Report, *, expect_orientation: str | None = None, expect_pages: int | None = None,
              margins_in: tuple[float, float, float, float] | None = None, sheet: Sheet | None = None,
              header_row_text: list[str] | None = None) -> None:
    rep.inputs.setdefault("files", []).append(path)
    with pdfplumber.open(path) as pdf:
        if expect_pages and len(pdf.pages) != expect_pages:
            rep.add("page_count", "error", path, "page count differs", expected=str(expect_pages), actual=str(len(pdf.pages)))
        all_text = []
        for i, pg in enumerate(pdf.pages, 1):
            w, h = float(pg.width), float(pg.height)
            orient = "landscape" if w > h else "portrait"
            if expect_orientation and orient != expect_orientation:
                rep.add("orientation", "error", path, "page orientation differs", cell=f"page {i}", expected=expect_orientation, actual=orient)
            words = pg.extract_words(keep_blank_chars=False, use_text_flow=False)
            all_text.append(" ".join(x["text"] for x in words))
            for wd in words:
                if wd["x0"] < -EDGE_TOL_PT or wd["x1"] > w + EDGE_TOL_PT or wd["top"] < -EDGE_TOL_PT or wd["bottom"] > h + EDGE_TOL_PT:
                    rep.add("clipped_text", "error", path, "text extends beyond page edge", cell=f"page {i}", actual=wd["text"][:40])
                if margins_in:
                    t, b, l, r = (m * PT for m in margins_in)
                    if wd["x0"] < l - EDGE_TOL_PT or wd["x1"] > w - r + EDGE_TOL_PT:
                        rep.add("outside_margin", "warn", path, "text outside left/right margin", cell=f"page {i}", actual=wd["text"][:40])
            # rows cut by page break: last line bottom nearly touching bottom margin with text continuing next page is
            # detected via row-text parity below; here flag text overlapping bottom edge
            if margins_in and words:
                bottom_limit = h - margins_in[1] * PT
                for wd in words:
                    if wd["bottom"] > bottom_limit + 2:
                        rep.add("page_break_overflow", "error", path, "text runs into bottom margin", cell=f"page {i}", actual=wd["text"][:40])
                        break
            if header_row_text and i > 1:
                first = _norm(" ".join(x["text"] for x in words[:30]))
                for token in header_row_text:
                    if _norm(token) in first:
                        rep.add("repeated_heading", "warn", path, "heading row repeats on later page (donor does not repeat)", cell=f"page {i}", actual=token)
                        break
    blob = _norm(" ".join(all_text))
    if sheet is not None:
        missing = 0
        for (r, c), cell in sorted(sheet.cells.items()):
            if cell.kind == "empty" or not cell.text.strip():
                continue
            for seg in cell.text.split("\n"):
                tokens = [t for t in _norm(seg).split(" ") if t]
                probes = {tokens[0], tokens[-1]} if tokens else set()   # wrapped cells interleave with neighbours, so test edges only
                if any(pr not in blob for pr in probes):
                    missing += 1
                    if missing <= 200:
                        rep.add("cell_text_missing_in_pdf", "error", path, "workbook cell text not found in PDF", cell=cell.ref, expected=seg[:60])
        if missing > 200:
            rep.add("cell_text_missing_in_pdf", "error", path, f"... plus {missing - 200} more cells not found", actual=str(missing))
