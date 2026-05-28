"""Import and normalize XLSX pull lists."""

import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from core.config import config
from core.database import insert_many, execute
from core.audit import record


# Column name aliases - maps various header spellings to canonical names
_COL_ALIASES = {
    "county": ["county", "co", "cnty"],
    "book": ["book", "bk", "vol", "volume"],
    "page": ["page", "pg", "p"],
    "instrument_number": [
        "instrument_number", "instrument no", "instrument#", "inst no",
        "inst_no", "doc no", "doc_no", "document number", "doc number",
        "instrument", "instr no", "instr_no",
    ],
    "image_number": [
        "image_number", "image no", "image#", "img no", "img_no", "image",
        "image number",
    ],
    "instrument_type": [
        "instrument_type", "type", "doc type", "document type",
        "instrument type", "instr type",
    ],
    "section": ["section", "sec", "sect"],
    "township": ["township", "twp", "twn", "t"],
    "range_val": ["range", "rng", "r"],
    "recording_date": [
        "recording_date", "recording date", "rec date", "filed date",
        "date filed", "date recorded",
    ],
}


def _normalize_col_name(name: str) -> Optional[str]:
    clean = re.sub(r"[^a-z0-9 _]", "", str(name).lower().strip())
    for canonical, aliases in _COL_ALIASES.items():
        if clean in aliases or clean.replace(" ", "_") in aliases:
            return canonical
    return None


def _normalize_county(val: str) -> str:
    if not val:
        return ""
    val = str(val).strip().title()
    for county in config.OK_COUNTIES:
        if county.lower() == val.lower():
            return county
    return val


def _normalize_instrument_type(val: str) -> str:
    if not val:
        return ""
    key = str(val).lower().strip()
    return config.INSTRUMENT_TYPE_MAP.get(key, str(val).strip().title())


def _normalize_book_page(val) -> str:
    if val is None or (isinstance(val, float) and str(val) == "nan"):
        return ""
    s = str(val).strip()
    # Remove trailing .0 from numeric reads
    if s.endswith(".0"):
        s = s[:-2]
    return s.upper()


def _build_dedup_key(row: dict) -> str:
    parts = [
        row.get("county", ""),
        row.get("book", ""),
        row.get("page", ""),
        row.get("instrument_number", ""),
        row.get("image_number", ""),
    ]
    return "|".join(p.strip().upper() for p in parts)


def import_pull_list(file_path: str, filters: dict = None) -> dict:
    """
    Import an XLSX pull list, normalize fields, and upsert into image_queue.
    filters: optional dict with keys county, section, township, range_val,
             date_from, date_to, instrument_type
    Returns summary dict.
    """
    path = Path(file_path)
    batch_id = f"PL-{datetime.now().strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:6].upper()}"

    df = pd.read_excel(path, dtype=str)
    df.columns = [str(c) for c in df.columns]

    # Map columns
    col_map: dict[str, str] = {}
    for col in df.columns:
        canonical = _normalize_col_name(col)
        if canonical:
            col_map[col] = canonical

    df = df.rename(columns=col_map)
    df = df.dropna(how="all")

    canonical_cols = list(_COL_ALIASES.keys())
    for c in canonical_cols:
        if c not in df.columns:
            df[c] = ""

    # Normalize
    df["county"] = df["county"].apply(_normalize_county)
    df["instrument_type"] = df["instrument_type"].apply(_normalize_instrument_type)
    for c in ("book", "page", "instrument_number", "image_number",
              "section", "township", "range_val"):
        df[c] = df[c].apply(_normalize_book_page)

    # Apply filters
    filters = filters or {}
    if filters.get("county"):
        df = df[df["county"].str.lower() == filters["county"].lower()]
    if filters.get("instrument_type"):
        df = df[df["instrument_type"].str.lower().str.contains(
            filters["instrument_type"].lower(), na=False)]
    if filters.get("section"):
        df = df[df["section"] == str(filters["section"]).upper()]
    if filters.get("township"):
        df = df[df["township"].str.upper() == str(filters["township"]).upper()]
    if filters.get("range_val"):
        df = df[df["range_val"].str.upper() == str(filters["range_val"]).upper()]

    # Build pull_list_items rows
    import json
    pl_rows = []
    for _, row in df.iterrows():
        pl_rows.append({
            "batch_id": batch_id,
            "county": row.get("county", ""),
            "book": row.get("book", ""),
            "page": row.get("page", ""),
            "instrument_number": row.get("instrument_number", ""),
            "image_number": row.get("image_number", ""),
            "instrument_type": row.get("instrument_type", ""),
            "section": row.get("section", ""),
            "township": row.get("township", ""),
            "range_val": row.get("range_val", ""),
            "recording_date": row.get("recording_date", ""),
            "raw_data": json.dumps(row.to_dict()),
        })

    if pl_rows:
        insert_many("pull_list_items", pl_rows)

    # Upsert into image_queue (deduplication by key)
    queued = 0
    skipped = 0
    for r in pl_rows:
        key = _build_dedup_key(r)
        if not key.strip("|"):
            skipped += 1
            continue
        from core.database import fetch_one
        existing = fetch_one("SELECT id FROM image_queue WHERE dedup_key=?", (key,))
        if existing:
            skipped += 1
        else:
            execute(
                """INSERT INTO image_queue
                   (dedup_key, county, book, page, instrument_number, image_number,
                    instrument_type, section, township, range_val, recording_date,
                    estimated_cost, status)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (key, r["county"], r["book"], r["page"], r["instrument_number"],
                 r["image_number"], r["instrument_type"], r["section"],
                 r["township"], r["range_val"], r["recording_date"],
                 config.OKCOUNTY_COST_PER_IMAGE, "pending"),
            )
            queued += 1

    record("import_pull_list",
           f"Imported {len(pl_rows)} rows from {path.name}; queued {queued}, skipped {skipped}",
           data={"batch_id": batch_id, "file": path.name, "filters": filters})

    return {
        "batch_id": batch_id,
        "file": path.name,
        "total_rows": len(pl_rows),
        "queued": queued,
        "skipped_duplicates": skipped,
    }
