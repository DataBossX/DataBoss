"""Import and reconcile CSV image index against the download queue."""

import json
import uuid
from datetime import datetime
from pathlib import Path

import pandas as pd

from core.database import insert_many, fetch_all
from core.audit import record
from processors.pull_list import (
    _normalize_col_name, _normalize_county,
    _normalize_instrument_type, _normalize_book_page,
)


def import_image_index(file_path: str) -> dict:
    """
    Load a CSV image index, normalize, store, and cross-reference against queue.
    Returns reconciliation summary.
    """
    path = Path(file_path)
    batch_id = f"IDX-{datetime.now().strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:6].upper()}"

    df = pd.read_csv(path, dtype=str)
    df.columns = [str(c) for c in df.columns]

    col_map = {}
    for col in df.columns:
        canonical = _normalize_col_name(col)
        if canonical:
            col_map[col] = canonical
    df = df.rename(columns=col_map)
    df = df.dropna(how="all")

    from processors.pull_list import _COL_ALIASES
    for c in _COL_ALIASES.keys():
        if c not in df.columns:
            df[c] = ""

    df["county"] = df["county"].apply(_normalize_county)
    df["instrument_type"] = df["instrument_type"].apply(_normalize_instrument_type)
    for c in ("book", "page", "instrument_number", "image_number", "section", "township", "range_val"):
        df[c] = df[c].apply(_normalize_book_page)

    rows = []
    for _, row in df.iterrows():
        rows.append({
            "batch_id": batch_id,
            "county": row.get("county", ""),
            "book": row.get("book", ""),
            "page": row.get("page", ""),
            "instrument_number": row.get("instrument_number", ""),
            "image_number": row.get("image_number", ""),
            "instrument_type": row.get("instrument_type", ""),
            "file_name": row.get("file_name", ""),
            "raw_data": json.dumps(row.to_dict()),
        })

    if rows:
        insert_many("image_index_items", rows)

    # Cross-reference: find queue items already covered by the index
    queue = fetch_all(
        "SELECT id, dedup_key, county, book, page, instrument_number, image_number "
        "FROM image_queue WHERE status='pending'"
    )

    def make_key(r):
        return "|".join([
            str(r.get("county", "") or "").strip().upper(),
            str(r.get("book", "") or "").strip().upper(),
            str(r.get("page", "") or "").strip().upper(),
            str(r.get("instrument_number", "") or "").strip().upper(),
            str(r.get("image_number", "") or "").strip().upper(),
        ])

    index_keys = {make_key(r) for r in rows}
    matched = []
    for q in queue:
        if q["dedup_key"] in index_keys or make_key(q) in index_keys:
            matched.append(q["id"])

    already_indexed = len(matched)

    record("import_image_index",
           f"Loaded {len(rows)} index rows; {already_indexed} already in queue",
           data={"batch_id": batch_id, "file": path.name})

    return {
        "batch_id": batch_id,
        "file": path.name,
        "total_rows": len(rows),
        "matched_in_queue": already_indexed,
    }
