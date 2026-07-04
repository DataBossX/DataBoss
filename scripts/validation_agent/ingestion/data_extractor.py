"""Structured data extractor.

Turns a classified workbook into the validation *context* the gates consume
(tract acreages, interest conveyance rows, chain-of-title links, OGL records,
WI/depth assignments, instrument references, well/HBP rows).

Design principle — CONSERVATIVE, NEVER GUESS:
  * A field is only extracted when its column can be mapped to a header with
    high fuzzy confidence.
  * When a sheet or a required column can't be confidently located, the
    corresponding context key is left ABSENT so the validator ESCALATES rather
    than the extractor inventing data.
  * The extractor reads values only; it never writes to the workbook.

Anything the extractor cannot confidently produce simply falls through to the
safe default (escalation), which is exactly what the mission requires.
"""

from __future__ import annotations

import re
from typing import Any, Optional

import openpyxl
from rapidfuzz import fuzz

from sources.source_finder import extract_references

# Confidence threshold for mapping a header string to a target field.
_HEADER_MATCH = 80.0

# Field alias tables per sheet category.
_ACREAGE_ALIASES = ["acreage", "acres", "gross acres", "net acres", "acre",
                    "gross ac", "net ac"]
_INTEREST_ALIASES = {
    "subject": ["tract", "parcel", "subject", "conveyance"],
    "grantor_interest": ["grantor interest", "interest owned",
                         "starting interest", "owned interest"],
    "conveyed": ["conveyed", "interest conveyed", "granted interest"],
    "retained": ["retained", "reserved", "reservation"],
}
_CHAIN_ALIASES = {
    "grantor": ["grantor", "seller", "assignor"],
    "grantee": ["grantee", "buyer", "assignee"],
    "vested_root": ["vested root", "root", "patent", "sovereign"],
}
_OGL_ALIASES = {
    "lessor": ["lessor", "landowner", "mineral owner"],
    "lessee": ["lessee", "operator", "company"],
    "date": ["date", "lease date", "effective date", "recorded"],
    "book_page": ["book/page", "book page", "bk/pg", "recording", "reference"],
    "royalty": ["royalty", "rry", "nra", "royalty rate"],
}
_WI_ALIASES = {
    "party": ["party", "owner", "working interest owner", "name"],
    "wi": ["wi", "working interest", "wrkg int", "w.i."],
    "depth_top": ["depth top", "top", "from depth", "top depth", "shallow"],
    "depth_base": ["depth base", "base", "to depth", "base depth", "deep",
                   "bottom"],
}
_WELL_ALIASES = {
    "api": ["api", "api number", "api no", "well api"],
    "status": ["status", "well status", "producing", "state"],
}


def _alias_score(alias: str, header: str) -> float:
    """Score an alias against a normalized header.

    Uses exact match (100) and whole-word containment (95) before falling back
    to a FULL-string ratio (never ``partial_ratio``, which false-matches short
    aliases like 'to' inside 'gran-to-r'). This keeps column mapping precise.
    """
    if alias == header:
        return 100.0
    if re.search(rf"\b{re.escape(alias)}\b", header):
        return 95.0
    return float(fuzz.ratio(alias, header))


def _best_column(headers_norm: list[str], alias_list: list[str]) -> int:
    best_idx, best_score = -1, 0.0
    for i, h in enumerate(headers_norm):
        if not h:
            continue
        for alias in alias_list:
            score = _alias_score(alias, h)
            if score > best_score:
                best_score, best_idx = score, i
    return best_idx if best_score >= _HEADER_MATCH else -1


def _match_columns(headers: list[str], aliases) -> dict[str, int]:
    """Map field -> column index for the best header match above threshold."""
    norm = [str(h or "").strip().lower() for h in headers]
    result: dict[str, int] = {}
    for field, alias_list in aliases.items():
        idx = _best_column(norm, alias_list)
        if idx >= 0:
            result[field] = idx
    return result


def _acreage_column(headers: list[str]) -> int:
    norm = [str(h or "").strip().lower() for h in headers]
    return _best_column(norm, _ACREAGE_ALIASES)


class DataExtractor:
    def __init__(self, workbook_path, classification: dict):
        self.path = workbook_path
        self.classification = classification
        self._sheet_rows: dict[str, list[list[Any]]] = {}
        self._category_sheets: dict[str, list[str]] = \
            classification.get("found_categories", {})

    # ------------------------------------------------------------------ #
    def _load(self) -> None:
        wb = openpyxl.load_workbook(self.path, read_only=True, data_only=False)
        try:
            for ws in wb.worksheets:
                rows = []
                for r in ws.iter_rows(values_only=True):
                    rows.append(list(r))
                self._sheet_rows[ws.title] = rows
        finally:
            wb.close()

    def _sheets_for(self, category: str) -> list[str]:
        return self._category_sheets.get(category, [])

    @staticmethod
    def _find_header(rows: list[list[Any]]) -> tuple[int, list[str]]:
        for i, row in enumerate(rows[:10]):
            strings = [c for c in row if isinstance(c, str) and c.strip()]
            if len(strings) >= 2:
                return i, [str(c) if c is not None else "" for c in row]
        return -1, []

    # ------------------------------------------------------------------ #
    def extract(self) -> dict:
        self._load()
        ctx: dict[str, Any] = {}
        self._extract_acreage(ctx)
        self._extract_interest(ctx)
        self._extract_chain(ctx)
        self._extract_ogl(ctx)
        self._extract_wi(ctx)
        self._extract_wells(ctx)
        self._extract_instruments(ctx)
        return ctx

    def _extract_acreage(self, ctx: dict) -> None:
        for name in self._sheets_for("tracts"):
            rows = self._sheet_rows.get(name, [])
            hidx, headers = self._find_header(rows)
            if hidx < 0:
                continue
            col = _acreage_column(headers)
            if col < 0:
                continue
            acreages = []
            for row in rows[hidx + 1:]:
                if col >= len(row):
                    continue
                v = row[col]
                if isinstance(v, (int, float)):
                    acreages.append(v)
            if acreages:
                ctx["tract_acreages"] = acreages
                return

    def _candidate_sheets(self, *preferred_categories: str) -> list[str]:
        """Return sheet names to scan: preferred categories first, then every
        other sheet. Being column-driven means a mis-classified runsheet (a
        common fuzzy tie) is still found by its columns, not its label."""
        order: list[str] = []
        for cat in preferred_categories:
            for name in self._sheets_for(cat):
                if name not in order:
                    order.append(name)
        for name in self._sheet_rows:
            if name not in order:
                order.append(name)
        return order

    def _extract_interest(self, ctx: dict) -> None:
        # Interest rows may live on a runsheet or a dedicated conveyance sheet;
        # scan by columns across all sheets so classification ties don't hide it.
        for name in self._candidate_sheets("runsheets", "working_interest"):
            rows = self._sheet_rows.get(name, [])
            hidx, headers = self._find_header(rows)
            if hidx < 0:
                continue
            cols = _match_columns(headers, _INTEREST_ALIASES)
            # Require the three interest columns to be confidently present.
            if not all(k in cols for k in
                       ("grantor_interest", "conveyed", "retained")):
                continue
            interest_rows = []
            for row in rows[hidx + 1:]:
                def cell(field):
                    idx = cols.get(field, -1)
                    return row[idx] if 0 <= idx < len(row) else None
                gi, cv, rt = (cell("grantor_interest"), cell("conveyed"),
                              cell("retained"))
                if gi is None and cv is None and rt is None:
                    continue
                interest_rows.append({
                    "subject": cell("subject") or f"{name} row",
                    "grantor_interest": gi, "conveyed": cv, "retained": rt,
                })
            if interest_rows:
                ctx["interest_rows"] = interest_rows
                return

    def _extract_chain(self, ctx: dict) -> None:
        for name in self._candidate_sheets("runsheets"):
            rows = self._sheet_rows.get(name, [])
            hidx, headers = self._find_header(rows)
            if hidx < 0:
                continue
            cols = _match_columns(headers, _CHAIN_ALIASES)
            if "grantor" not in cols or "grantee" not in cols:
                continue
            links = []
            for row in rows[hidx + 1:]:
                def cell(field):
                    idx = cols.get(field, -1)
                    return row[idx] if 0 <= idx < len(row) else None
                gr, ge = cell("grantor"), cell("grantee")
                if not gr and not ge:
                    continue
                root = cell("vested_root")
                links.append({
                    "grantor": gr, "grantee": ge,
                    "vested_root": bool(root) and str(root).strip().lower() not in
                    {"", "0", "false", "no"},
                })
            if links:
                ctx["chain_links"] = links
                return

    def _extract_ogl(self, ctx: dict) -> None:
        for name in self._sheets_for("ogl_register"):
            rows = self._sheet_rows.get(name, [])
            hidx, headers = self._find_header(rows)
            if hidx < 0:
                continue
            cols = _match_columns(headers, _OGL_ALIASES)
            if "lessor" not in cols or "lessee" not in cols:
                continue
            records = []
            for row in rows[hidx + 1:]:
                rec = {}
                any_val = False
                for field, idx in cols.items():
                    val = row[idx] if idx < len(row) else None
                    rec[field] = val
                    any_val = any_val or (val is not None and str(val).strip())
                if any_val:
                    records.append(rec)
            if records:
                ctx["ogl_records"] = records
                return

    def _extract_wi(self, ctx: dict) -> None:
        for name in self._sheets_for("working_interest"):
            rows = self._sheet_rows.get(name, [])
            hidx, headers = self._find_header(rows)
            if hidx < 0:
                continue
            cols = _match_columns(headers, _WI_ALIASES)
            if "wi" not in cols:
                continue
            assignments = []
            for row in rows[hidx + 1:]:
                def cell(field):
                    idx = cols.get(field, -1)
                    return row[idx] if 0 <= idx < len(row) else None
                wi = cell("wi")
                if wi is None:
                    continue
                assignments.append({
                    "party": cell("party"), "wi": wi,
                    "depth_top": cell("depth_top"),
                    "depth_base": cell("depth_base"),
                })
            if assignments:
                ctx["wi_assignments"] = assignments
                return

    def _extract_wells(self, ctx: dict) -> None:
        for name in self._sheets_for("wells"):
            rows = self._sheet_rows.get(name, [])
            hidx, headers = self._find_header(rows)
            if hidx < 0:
                continue
            cols = _match_columns(headers, _WELL_ALIASES)
            if "api" not in cols:
                continue
            wells = []
            for row in rows[hidx + 1:]:
                idx = cols["api"]
                api = row[idx] if idx < len(row) else None
                if not api:
                    continue
                sidx = cols.get("status", -1)
                status = row[sidx] if 0 <= sidx < len(row) else ""
                wells.append({"api": api, "status": status})
            if wells:
                ctx["wells"] = wells
                return

    def _extract_instruments(self, ctx: dict) -> None:
        """Scan all cell text for book/page + instrument references and collect
        the keys that already appear on a 'sources' sheet as known-sourced."""
        all_text_parts: list[str] = []
        known: set[str] = set()
        source_sheets = set(self._sheets_for("sources"))
        for name, rows in self._sheet_rows.items():
            text = " ".join(
                str(c) for row in rows for c in row if isinstance(c, str)
            )
            all_text_parts.append(text)
            if name in source_sheets:
                for ref in extract_references(text):
                    known.add(ref["reference_key"])
        refs = extract_references(" ".join(all_text_parts))
        if refs:
            ctx["instrument_references"] = refs
            ctx["known_source_keys"] = list(known)


def extract_context(workbook_path, classification: dict) -> dict:
    """Convenience wrapper returning the extracted validation context."""
    try:
        return DataExtractor(workbook_path, classification).extract()
    except Exception:
        # Extraction must never crash a run; on failure the gates escalate.
        return {}
