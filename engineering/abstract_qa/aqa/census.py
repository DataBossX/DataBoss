"""File selection, distinct counting units, and an arithmetic explanation of count differences."""
from __future__ import annotations

import itertools
import posixpath
import re
from collections import defaultdict
from typing import Any

from .util import norm_compare

VERSION = re.compile(r"(?i)[ _\-.]v(?:er(?:sion)?)?[ _\-]?(\d+)")
NOISE = re.compile(r"(?i)([ _\-]*(copy|final|old|backup|superseded|draft)\b|[ _\-]*\(\d+\)|[ _\-.]v(?:er(?:sion)?)?[ _\-]?\d+)")


def stem_key(path: str, section: str) -> str:
    base = posixpath.basename(path.split("!/")[-1]).rsplit(".", 1)[0]
    base = NOISE.sub("", base)
    if section:
        base = re.sub(re.escape(section), "", base, flags=re.I)
    return norm_compare(base)


def _rank(rec: dict[str, Any]) -> tuple:
    m = VERSION.search(posixpath.basename(rec["file"]))
    return (int(m.group(1)) if m else 0, rec.get("mtime_ns") or 0, rec["file"])


def select_tables(records: list[dict[str, Any]]) -> None:
    """Mark each table record selected / duplicate_of / superseded_by (in place, deterministic)."""
    first_by_sha: dict[tuple[str, str, str], str] = {}
    for r in sorted(records, key=lambda x: x["file"]):
        r["selected"], r["duplicate_of"], r["superseded_by"] = False, None, None
        k = (r["sha256"], r["table"], r["kind"] or "")
        if k in first_by_sha and first_by_sha[k] != r["file"]:
            r["duplicate_of"] = first_by_sha[k]
        else:
            first_by_sha[k] = r["file"]
    groups: dict[tuple, list[dict[str, Any]]] = defaultdict(list)
    for r in records:
        if r["duplicate_of"]:
            continue
        groups[(r["section"], r["kind"], stem_key(r["file"], r["section"]))].append(r)
    for g in groups.values():
        files = {}
        for r in g:
            files.setdefault(r["file"], r)
        best = max(files.values(), key=_rank)["file"]
        for r in g:
            if r["file"] == best:
                r["selected"] = True
            else:
                r["superseded_by"] = best


def counting_units(entries: list[dict[str, Any]], rows: list[dict[str, Any]], recon: dict[str, Any],
                   ledger: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    pdfs = [e for e in entries if e["ext"] == ".pdf" and e.get("sha256")]
    distinct: dict[str, dict[str, Any]] = {}
    for e in pdfs:
        distinct.setdefault(e["sha256"], e)
    imgs = [e for e in entries if e["ext"] in {".tif", ".tiff", ".jpg", ".jpeg", ".png", ".bmp", ".gif", ".jp2"} and e.get("sha256")]
    sel = [r for r in rows if r["selected"]]
    county = [r for r in sel if r["kind"] == "county"]
    fed = [r for r in sel if r["kind"] == "federal"]
    tract = cfg["tract_field"]
    tract_app = {(r.get("identity"), norm_compare(r["fields"].get(tract, ""))) for r in county if r.get("identity")}
    sect_app = {(r.get("identity"), r["section"]) for r in county if r.get("identity")}
    return {
        "physical_pages_all_pdf_copies": sum(e["pdf_pages"] or 0 for e in pdfs),
        "physical_pages_distinct_pdfs": sum(e["pdf_pages"] or 0 for e in distinct.values()),
        "pdf_file_copies": len(pdfs),
        "pdf_distinct_by_sha256": len(distinct),
        "pdf_duplicate_copies": len(pdfs) - len(distinct),
        "pdf_page_count_unreadable": sum(1 for e in pdfs if e["pdf_pages"] is None),
        "embedded_pdf_images": sum(e["pdf_images"] or 0 for e in distinct.values()),
        "image_files": len(imgs),
        "image_frames": sum(e["image_frames"] or 1 for e in imgs),
        "index_placements_county_rows": len(county),
        "index_placements_federal_rows": len(fed),
        "index_placements_total": len(county) + len(fed),
        "recorder_identities": len(recon.get("identities", [])),
        "tract_appearances": len(tract_app),
        "section_applications": len(sect_app),
        "county_rows_without_identity": len(recon.get("no_identity_rows", [])),
        "federal_events": len(ledger.get("ledger", [])),
        "federal_serials": ledger.get("serials", 0),
    }


def explain_difference(claimed: int | None, table_records: list[dict[str, Any]], unit_total: int) -> dict[str, Any]:
    """Recalculate from bytes and show which excluded populations could account for the claimed figure."""
    by = lambda pred: sum(r["data_rows"] for r in table_records if pred(r))  # noqa: E731
    cats = {
        "duplicate_file_copies_rows": by(lambda r: bool(r["duplicate_of"])),
        "superseded_version_rows": by(lambda r: bool(r["superseded_by"])),
        "repeated_header_rows": sum(r["excluded"]["repeated_header"] for r in table_records if r["selected"]),
        "narrative_placeholder_rows": sum(r["excluded"]["narrative_placeholder"] for r in table_records if r["selected"]),
        "total_rows": sum(r["excluded"]["total_row"] for r in table_records if r["selected"]),
        "unclassified_kind_rows": by(lambda r: r["selected"] and r["kind"] not in ("county", "federal")),
    }
    out: dict[str, Any] = {
        "claimed": claimed, "recalculated_selected": unit_total,
        "recalculated_all_files": sum(r["data_rows"] for r in table_records),
        "categories": cats, "delta_claimed_minus_selected": None, "candidate_explanations": [],
        "note": "Subset matches are arithmetic coincidences until the contributing files are inspected.",
    }
    if claimed is None:
        return out
    delta = claimed - unit_total
    out["delta_claimed_minus_selected"] = delta
    names = [k for k, v in cats.items() if v]
    for n in range(0, len(names) + 1):
        for combo in itertools.combinations(names, n):
            if sum(cats[c] for c in combo) == delta:
                out["candidate_explanations"].append(list(combo) or ["exact_match_no_difference"])
    if not out["candidate_explanations"]:
        out["candidate_explanations"].append(["UNEXPLAINED"])
    return out
