"""Adapter: DOTO Image Commander SQLite DB -> TitleReport (real examined feed).

Reads the DOTO ``analyses`` rows (joined to ``image_queue`` and ``downloads``)
for a given Section-Township-Range and assembles a runsheet, instrument
abstractions, and a chronological mineral/surface chain from *examined* records.

This is the bridge that turns the report engine from specimen-only into a real
producer: point it at ``databossx.db`` (or the DOTO app DB) and it emits an
``EXAMINED`` report grounded in the analyzed instruments.

Integrity is preserved end to end:
  * Only stdlib ``sqlite3`` is used -- no dependency on the DOTO package.
  * Nothing is invented. Ownership interests are **not** synthesized here:
    extracting exact NMA/NRI/WI fractions requires governing lease/deed language
    that the analyzer does not reliably emit, so the ownership matrix is left
    empty and the gap is surfaced on the Missing/Unverified schedule rather than
    guessed. Add ownership only when exact fractions are confirmed.
"""

from __future__ import annotations

import json
import sqlite3
from fractions import Fraction
from pathlib import Path
from typing import List, Optional

from ..models import (
    ProjectConfig, Source, Instrument, Abstraction, ChainLink, TitleReport, UNKNOWN,
)

# Public OK portals used as source references for an examined county/OCC feed.
URL_COUNTY = "https://okcountyrecords.com/"
URL_OCC = "https://gisdata-occokc.opendata.arcgis.com/"


def _norm(value) -> str:
    """SQLite value -> display string; None/empty -> UNKNOWN."""
    if value is None:
        return UNKNOWN
    s = str(value).strip()
    return s if s else UNKNOWN


def _parse_parties(value) -> List[str]:
    """Grantor/grantee columns may be JSON lists or delimited strings."""
    if not value:
        return []
    s = str(value).strip()
    if s.startswith("["):
        try:
            data = json.loads(s)
            if isinstance(data, list):
                return [str(x) for x in data if str(x).strip()]
        except json.JSONDecodeError:
            pass
    for sep in (";", "|", "\n"):
        if sep in s:
            return [p.strip() for p in s.split(sep) if p.strip()]
    return [s] if s else []


def _str_label(section, township, range_val) -> str:
    parts = [p for p in (_norm(section), _norm(township), _norm(range_val)) if p != UNKNOWN]
    return "-".join(parts) if parts else UNKNOWN


def available_tracts(db_path: str) -> List[dict]:
    """Distinct Section-Township-Range tracts present in the analyses table."""
    if not Path(db_path).exists():
        return []
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """SELECT a.section AS section, a.township AS township,
                      a.range_val AS range_val, q.county AS county, COUNT(*) AS n
               FROM analyses a
               JOIN image_queue q ON q.id = a.queue_item_id
               WHERE a.section IS NOT NULL AND a.township IS NOT NULL
                     AND a.range_val IS NOT NULL
               GROUP BY a.section, a.township, a.range_val, q.county
               ORDER BY n DESC"""
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()
    out = []
    for r in rows:
        out.append({
            "section": _norm(r["section"]), "township": _norm(r["township"]),
            "range": _norm(r["range_val"]), "county": _norm(r["county"]),
            "count": r["n"],
            "slug": _str_label(r["section"], r["township"], r["range_val"]),
        })
    return out


def build_report_from_db(
    db_path: str,
    section: str,
    township: str,
    range_val: str,
    county: Optional[str] = None,
    report_date: str = UNKNOWN,
    source_cutoff_date: str = UNKNOWN,
) -> TitleReport:
    """Build a TitleReport from DOTO analyses matching the given tract."""
    if not Path(db_path).exists():
        raise FileNotFoundError(f"DOTO database not found: {db_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """SELECT a.*, q.county AS q_county, d.file_path AS file_path
               FROM analyses a
               JOIN image_queue q ON q.id = a.queue_item_id
               LEFT JOIN downloads d ON d.id = a.download_id
               WHERE a.section = ? AND a.township = ? AND a.range_val = ?
               ORDER BY a.recording_date, a.book, a.page""",
            (section, township, range_val),
        ).fetchall()
    finally:
        conn.close()

    county = county or (rows[0]["q_county"] if rows else UNKNOWN) or UNKNOWN
    has_data = len(rows) > 0

    cfg = ProjectConfig(
        section=section, township=township, range_=range_val, county=county, state="OK",
        gross_acres=UNKNOWN, net_mineral_acres=UNKNOWN,
        acreage_basis="Per recorded legals; not survey-verified",
        report_date=report_date, source_cutoff_date=source_cutoff_date,
        prepared_for=UNKNOWN, preparer="DataBoss Title Report Engine (DOTO feed)",
        report_type="Cursory Title Report",
        is_placeholder=not has_data,
        data_status="EXAMINED" if has_data else "PLACEHOLDER",
        assumptions=[
            "Built from DOTO-examined instruments for the tract (index + analyzed images).",
            "Ownership interests (NMA/NRI/WI) are NOT computed: exact governing fractions "
            "were not confirmed from the instruments; see Missing/Unverified.",
            "Cursory scope: covers instruments examined through the source cutoff date.",
        ],
    )

    sources = [
        Source("SRC-CTY", "County Index",
               f"{county} County Clerk records (via OKCountyRecords)",
               location=URL_COUNTY, accessed_date=source_cutoff_date,
               doc_count=Fraction(len(rows)), credential_required=True,
               page_ref="Per instrument book/page", notes="Examined via DOTO Image Commander."),
        Source("SRC-OCC", "OCC", "Oklahoma Corporation Commission — well & case data",
               location=URL_OCC, accessed_date=source_cutoff_date,
               notes="Well/HBP evidence to be added from OCC."),
    ]

    instruments: List[Instrument] = []
    abstractions: List[Abstraction] = []
    chain: List[ChainLink] = []

    for seq, r in enumerate(rows, start=1):
        inst_no = _norm(r["instrument_number"]) if r["instrument_number"] else f"DOTO-{r['id']}"
        book, page = _norm(r["book"]), _norm(r["page"])
        cite = f"SRC-CTY {book}/{page}" if book != UNKNOWN else "SRC-CTY"
        image_url = (f"{URL_COUNTY}search?book={book}&page={page}"
                     if book != UNKNOWN and page != UNKNOWN else UNKNOWN)
        legal = _norm(r["legal_description"])

        instruments.append(Instrument(
            instrument_no=inst_no, instrument_type=_norm(r["instrument_type"]),
            book=book, page=page, instrument_date=_norm(r["instrument_date"]),
            recording_date=_norm(r["recording_date"]),
            grantors=_parse_parties(r["grantors"]), grantees=_parse_parties(r["grantees"]),
            legal_raw=legal, legal_normalized=_str_label(r["section"], r["township"], r["range_val"]),
            consideration=UNKNOWN, classification=_classify(_norm(r["instrument_type"])),
            citation=cite, image_url=image_url,
            notes=_norm(r["title_requirement_affected"]) if r["title_requirement_affected"] else "",
        ))

        conf = r["confidence_score"]
        abstractions.append(Abstraction(
            instrument_no=inst_no,
            grant_clause=_norm(r["interest_conveyed"]),
            reservations=UNKNOWN,
            royalty_wi_language=_norm(r["lease_royalty_terms"]),
            exceptions=UNKNOWN, pugh_shutin=UNKNOWN, depth_limits=UNKNOWN,
            pooling_refs=UNKNOWN, liens=UNKNOWN, probate=UNKNOWN,
            tags=["doto-extracted"],
            confidence=_frac_conf(conf),
            needs_review=bool(r["needs_review"]),
            citation=cite,
        ))

        chain.append(ChainLink(
            chain_type="mineral_surface", seq=seq, instrument_no=inst_no,
            date=_norm(r["recording_date"]), conveyance=_norm(r["instrument_type"]),
            from_party="; ".join(_parse_parties(r["grantors"])) or UNKNOWN,
            to_party="; ".join(_parse_parties(r["grantees"])) or UNKNOWN,
            interest=_norm(r["interest_conveyed"]),
            gap_note=("Recording date missing — chain order uncertain."
                      if _norm(r["recording_date"]) == UNKNOWN else ""),
            citation=cite,
        ))

    return TitleReport(
        config=cfg, sources=sources, instruments=instruments,
        abstractions=abstractions, chain_links=chain, wells=[], curative=[], ownership=[],
    )


def _classify(instrument_type: str) -> str:
    t = (instrument_type or "").lower()
    if any(k in t for k in ("lease", "ogl")):
        return "Leasehold"
    if any(k in t for k in ("mortgage", "lien", "deed of trust")):
        return "Lien"
    if any(k in t for k in ("assignment",)):
        return "Leasehold"
    if any(k in t for k in ("easement", "row", "right-of-way", "right of way")):
        return "Surface"
    if any(k in t for k in ("deed", "patent", "probate", "decree", "mineral")):
        return "Mineral"
    return UNKNOWN


def _frac_conf(conf):
    """Confidence score (0..1 float) -> Fraction, or UNKNOWN."""
    from fractions import Fraction
    if conf is None:
        return UNKNOWN
    try:
        return Fraction(float(conf)).limit_denominator(100)
    except (TypeError, ValueError):
        return UNKNOWN
