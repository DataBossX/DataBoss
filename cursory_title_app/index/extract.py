"""Extract index rows from rendered handwritten-index pages via the vision model.

This reads a HANDWRITTEN cursive numerical index. Every value is uncertain by
default. We force the model to return per-row confidence and we mark anything
below threshold needs_review=True. We never coerce or "clean up" names.
"""
from __future__ import annotations

from pathlib import Path

from .. import config
from ..db import store
from ..models import registry
from ..schemas import IndexRow

INDEX_INSTRUCTION = f"""You are reading a HANDWRITTEN cursive county numerical
index page for Section {config.TARGET_SECTION}, Township {config.TARGET_TOWNSHIP},
Range {config.TARGET_RANGE} in {config.TARGET_COUNTY} County, Oklahoma.

This is old (early-1900s onward) cursive handwriting. Read each row of the
ledger. Do NOT invent or normalize names — transcribe what is written, even if
unsure. If a cell is illegible, use null and lower the confidence.

Return ONLY a JSON object of this exact shape:
{{
  "rows": [
    {{
      "grantor": "string or null",
      "grantee": "string or null",
      "instrument_kind": "string as written, e.g. 'O/L','WD','MD','ASGT' or null",
      "book": "string or null",
      "page": "string or null",
      "date_filed": "string as written or null",
      "legal_note": "string of subdivision/lot marks or null",
      "remarks": "string or null",
      "confidence": 0.0
    }}
  ],
  "page_confidence": 0.0
}}

Set each row's confidence 0.0-1.0 honestly based on legibility. It is better to
return low confidence than to guess."""


def extract_page(image_path: Path, page_number: int) -> list[IndexRow]:
    result = registry.extract_json([str(image_path)], INDEX_INSTRUCTION)
    provider = result.get("_provider")
    rows_raw = result.get("rows", []) or []
    out: list[IndexRow] = []
    for r in rows_raw:
        conf = float(r.get("confidence", 0.0) or 0.0)
        row = IndexRow(
            page_number=page_number,
            grantor=r.get("grantor"),
            grantee=r.get("grantee"),
            instrument_kind=r.get("instrument_kind"),
            book=r.get("book"),
            page=r.get("page"),
            date_filed=r.get("date_filed"),
            legal_note=r.get("legal_note"),
            remarks=r.get("remarks"),
            confidence=conf,
            needs_review=conf < config.CONFIDENCE_REVIEW_THRESHOLD,
            raw_cells=r,
        )
        out.append(row)
        store.insert("index_rows", {
            "page_number": page_number,
            "grantor": row.grantor, "grantee": row.grantee,
            "instrument_kind": row.instrument_kind,
            "book": row.book, "page": row.page, "date_filed": row.date_filed,
            "legal_note": row.legal_note, "remarks": row.remarks,
            "confidence": row.confidence,
            "needs_review": int(row.needs_review),
            "raw_json": None,
        })
    store.audit("index_page_extracted",
                f"page {page_number}: {len(out)} rows via {provider}",
                {"provider": provider, "rows": len(out)})
    return out
