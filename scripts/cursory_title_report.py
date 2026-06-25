#!/usr/bin/env python3
"""
Cursory Title Report generator.

Renders a self-contained, print-ready HTML "Cursory Title Report" for a single
PLSS tract, styled to match the DataBossX / DOTO Image Commander report
convention (navy headers #1F4E79, amber "Needs Review" #FFE699, green OK
#C6EFCE) and the Evidence/Target data model in
mineral_deal_room/src/types/index.ts.

DESIGN / HONESTY CONTRACT
-------------------------
This tool fills every cell, but it never *invents* recorded-instrument facts
(grantor/grantee, book/page, instrument number, dates). Those are sourced from
the county / state systems of record. Each such cell is therefore rendered as
an actionable "VERIFY" cell carrying the exact search to run and a working link
to the system of record. Cells that are *derivable* (legal description, PLSS
aliquots, acreage math, sovereignty root, curative skeleton, source catalog)
are filled with verified facts.

This makes the artifact a ready-to-populate run-sheet, not a fabricated title
opinion. A cursory report is, by definition, a limited examination and NOT a
title opinion — see the Limitations section in the output.

Usage:
    python scripts/cursory_title_report.py            # builds the 31-12N-24W report
    python scripts/cursory_title_report.py --open      # also print the output path
"""

from __future__ import annotations

import argparse
import html
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

# ── Theme (mirrors doto_image_commander/reports/generator.py) ──────────────────
NAVY = "#1F4E79"
AMBER = "#FFE699"   # "needs review / verify" — same convention as REVIEW_FILL
GREEN = "#C6EFCE"   # confirmed / derivable fact
RED = "#FF9999"     # gap / defect

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "reports"


# ── Data model ─────────────────────────────────────────────────────────────────
@dataclass
class Link:
    label: str
    url: str
    note: str = ""


@dataclass
class ChainRow:
    seq: str
    instrument: str
    grantor: str
    grantee: str
    instr_date: str
    rec_date: str
    book_page: str
    doc_no: str
    interest: str
    legal: str
    source: Optional[Link] = None
    verify: bool = True          # amber if True (pull from system of record)
    confirmed: bool = False      # green if True (derivable / sovereignty)


@dataclass
class Aliquot:
    parcel: str
    acres: float
    note: str = ""


@dataclass
class Curative:
    item: str
    trigger: str
    status: str = "Open – pending chain"


@dataclass
class TractReport:
    company: str
    prepared_by: str
    report_date: str
    section: str
    township: str
    range_: str
    meridian: str
    county: str
    state: str
    report_type: str
    legal_long: str
    section_position: str
    gross_acres: float
    acreage_caution: str
    title_clearance: str
    aliquots: List[Aliquot]
    chain: List[ChainRow]
    curatives: List[Curative]
    sources: List[Link]
    encumbrance_notes: List[str]
    basin_notes: List[str]
    limitations: List[str]

    @property
    def str_label(self) -> str:
        return f"{self.section}-{self.township}-{self.range_}"


# ── HTML rendering helpers ──────────────────────────────────────────────────────
def esc(v) -> str:
    return html.escape(str(v if v is not None else ""))


def a(link: Optional[Link]) -> str:
    if not link:
        return "&mdash;"
    extra = f" <span class='lnote'>{esc(link.note)}</span>" if link.note else ""
    return f"<a href='{esc(link.url)}' target='_blank' rel='noopener'>{esc(link.label)}</a>{extra}"


def chain_cell(value: str, row: ChainRow) -> str:
    """A value cell in the chain table, colored by verify/confirmed state."""
    cls = "verify" if row.verify and not row.confirmed else ("ok" if row.confirmed else "")
    return f"<td class='{cls}'>{esc(value)}</td>"


def render(r: TractReport) -> str:
    title = (f"Cursory Title Report — Sec {r.section}, T{r.township}, R{r.range_} "
             f"({r.county} Co., {r.state})")

    aliquot_rows = "\n".join(
        f"<tr><td>{esc(x.parcel)}</td><td class='num'>{x.acres:,.2f}</td>"
        f"<td>{esc(x.note)}</td></tr>"
        for x in r.aliquots
    )
    aliquot_total = sum(x.acres for x in r.aliquots)

    chain_rows = []
    for row in r.chain:
        chain_rows.append(
            "<tr>"
            f"<td class='num'>{esc(row.seq)}</td>"
            f"{chain_cell(row.instrument, row)}"
            f"{chain_cell(row.grantor, row)}"
            f"{chain_cell(row.grantee, row)}"
            f"{chain_cell(row.instr_date, row)}"
            f"{chain_cell(row.rec_date, row)}"
            f"{chain_cell(row.book_page, row)}"
            f"{chain_cell(row.doc_no, row)}"
            f"{chain_cell(row.interest, row)}"
            f"{chain_cell(row.legal, row)}"
            f"<td>{a(row.source)}</td>"
            "</tr>"
        )
    chain_html = "\n".join(chain_rows)

    curative_rows = "\n".join(
        f"<tr><td>{esc(c.item)}</td><td>{esc(c.trigger)}</td>"
        f"<td class='verify'>{esc(c.status)}</td></tr>"
        for c in r.curatives
    )

    source_items = "\n".join(
        f"<li><a href='{esc(s.url)}' target='_blank' rel='noopener'>{esc(s.label)}</a>"
        f"{(' — ' + esc(s.note)) if s.note else ''}</li>"
        for s in r.sources
    )

    enc = "\n".join(f"<li>{esc(x)}</li>" for x in r.encumbrance_notes)
    basin = "\n".join(f"<li>{esc(x)}</li>" for x in r.basin_notes)
    limits = "\n".join(f"<li>{esc(x)}</li>" for x in r.limitations)

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<style>
  :root {{ --navy:{NAVY}; --amber:{AMBER}; --green:{GREEN}; --red:{RED}; }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: "Segoe UI", Arial, sans-serif; color:#1a1a1a; margin:0;
          background:#f3f4f6; line-height:1.45; }}
  .page {{ max-width: 1100px; margin: 24px auto; background:#fff; padding:0 0 48px;
           box-shadow:0 1px 6px rgba(0,0,0,.12); }}
  header.rpt {{ background:var(--navy); color:#fff; padding:28px 40px; }}
  header.rpt .brand {{ font-size:13px; letter-spacing:2px; text-transform:uppercase;
                       opacity:.85; }}
  header.rpt h1 {{ margin:6px 0 2px; font-size:26px; }}
  header.rpt h2 {{ margin:0; font-weight:500; font-size:16px; opacity:.92; }}
  .meta {{ display:grid; grid-template-columns:repeat(4,1fr); gap:1px;
           background:#d9dde3; border-bottom:3px solid var(--navy); }}
  .meta div {{ background:#fff; padding:10px 16px; font-size:13px; }}
  .meta .k {{ color:#6b7280; text-transform:uppercase; font-size:10px;
              letter-spacing:1px; }}
  .meta .v {{ font-weight:600; }}
  section {{ padding:8px 40px 4px; }}
  h3 {{ color:var(--navy); border-bottom:2px solid var(--navy); padding-bottom:6px;
        margin:28px 0 12px; font-size:17px; }}
  table {{ width:100%; border-collapse:collapse; font-size:12.5px; margin:6px 0 14px; }}
  th {{ background:var(--navy); color:#fff; text-align:left; padding:7px 8px;
        font-weight:600; vertical-align:bottom; }}
  td {{ border:1px solid #d7dbe0; padding:6px 8px; vertical-align:top; }}
  td.num {{ text-align:right; font-variant-numeric:tabular-nums; }}
  td.verify {{ background:var(--amber); }}
  td.ok {{ background:var(--green); }}
  tr:nth-child(even) td:not(.verify):not(.ok) {{ background:#f7f8fa; }}
  .legend span {{ display:inline-block; padding:2px 10px; margin-right:10px;
                  border-radius:3px; font-size:11.5px; border:1px solid #cfd4da; }}
  .legend .v {{ background:var(--amber); }}
  .legend .o {{ background:var(--green); }}
  a {{ color:#0b59b3; text-decoration:none; }}
  a:hover {{ text-decoration:underline; }}
  .lnote {{ color:#6b7280; font-size:11px; }}
  .callout {{ background:#fff8e1; border-left:4px solid #d9a400; padding:10px 14px;
              font-size:12.5px; margin:10px 0; }}
  .danger {{ background:#fdecea; border-left:4px solid #c0392b; }}
  ul.tight {{ margin:6px 0 14px; padding-left:20px; }}
  ul.tight li {{ margin:3px 0; font-size:13px; }}
  .foot {{ font-size:11px; color:#6b7280; padding:18px 40px 0; border-top:1px solid #e5e7eb;
           margin-top:24px; }}
  .sig {{ display:grid; grid-template-columns:1fr 1fr; gap:40px; padding:24px 40px 0; }}
  .sig .line {{ border-top:1px solid #333; padding-top:4px; font-size:12px; margin-top:42px; }}
  @media print {{ body{{background:#fff;}} .page{{box-shadow:none;margin:0;max-width:none;}}
                  a{{color:#000;}} header.rpt{{ -webkit-print-color-adjust:exact;
                  print-color-adjust:exact; }} }}
</style>
</head>
<body>
<div class="page">
  <header class="rpt">
    <div class="brand">{esc(r.company)}</div>
    <h1>{esc(r.report_type)}</h1>
    <h2>Section {esc(r.section)}, Township {esc(r.township)}, Range {esc(r.range_)},
        {esc(r.meridian)} &mdash; {esc(r.county)} County, {esc(r.state)}</h2>
  </header>

  <div class="meta">
    <div><div class="k">Tract (STR)</div><div class="v">{esc(r.str_label)}</div></div>
    <div><div class="k">County / State</div><div class="v">{esc(r.county)}, {esc(r.state)}</div></div>
    <div><div class="k">Report Date</div><div class="v">{esc(r.report_date)}</div></div>
    <div><div class="k">Examiner</div><div class="v">{esc(r.prepared_by)}</div></div>
    <div><div class="k">Meridian</div><div class="v">{esc(r.meridian)}</div></div>
    <div><div class="k">Gross Acres (nominal)</div><div class="v">{r.gross_acres:,.2f}</div></div>
    <div><div class="k">Title Clearance</div><div class="v">{esc(r.title_clearance)}</div></div>
    <div><div class="k">Report Type</div><div class="v">Cursory — limited exam</div></div>
  </div>

  <section>
    <div class="legend">
      <span class="o">Green&nbsp;= verified / derivable fact</span>
      <span class="v">Amber&nbsp;= VERIFY from system of record (link in row)</span>
    </div>

    <h3>1. Tract &amp; Legal Description</h3>
    <p><strong>Legal description:</strong> {esc(r.legal_long)}</p>
    <p><strong>Section position:</strong> {esc(r.section_position)}</p>
    <div class="callout">{esc(r.acreage_caution)}</div>
    <table>
      <thead><tr><th>Aliquot Parcel</th><th>Acres (nominal)</th><th>Note</th></tr></thead>
      <tbody>
        {aliquot_rows}
        <tr><td><strong>Total (full section)</strong></td>
            <td class="num"><strong>{aliquot_total:,.2f}</strong></td>
            <td>Subject to GLO plat &amp; government-lot verification</td></tr>
      </tbody>
    </table>

    <h3>2. Chain of Title — Run Sheet</h3>
    <p>Chain runs from sovereignty forward. Green rows are established by public
       record of historical fact; amber cells must be populated from the linked
       system of record before this becomes a title opinion.</p>
    <table>
      <thead><tr>
        <th>#</th><th>Instrument</th><th>Grantor</th><th>Grantee</th>
        <th>Instr. Date</th><th>Rec. Date</th><th>Book/Page</th><th>Doc&nbsp;#</th>
        <th>Interest</th><th>Legal / Acres</th><th>Source (live link)</th>
      </tr></thead>
      <tbody>
        {chain_html}
      </tbody>
    </table>

    <h3>3. Encumbrances, Leasehold &amp; Conservation</h3>
    <ul class="tight">{enc}</ul>

    <h3>4. Geologic / Development Context</h3>
    <ul class="tight">{basin}</ul>

    <h3>5. Curative Requirements</h3>
    <table>
      <thead><tr><th>Curative Item</th><th>Typical Trigger</th><th>Status</th></tr></thead>
      <tbody>{curative_rows}</tbody>
    </table>

    <h3>6. Systems of Record — Verified Working Links</h3>
    <ul class="tight">{source_items}</ul>

    <h3>7. Limitations &amp; Certification</h3>
    <div class="callout danger">
      This is a <strong>CURSORY</strong> report — a limited examination intended
      only to guide acquisition and curative effort. It is <strong>NOT a title
      opinion</strong> and creates no attorney-client relationship or guaranty of title.
    </div>
    <ul class="tight">{limits}</ul>
  </section>

  <div class="sig">
    <div class="line">Prepared by — {esc(r.prepared_by)} ({esc(r.company)})</div>
    <div class="line">Reviewed by (licensed attorney) — required before reliance</div>
  </div>

  <div class="foot">
    Generated by DataBossX Cursory Title Report generator on {esc(r.report_date)}.
    Amber cells indicate data to be pulled from the system of record; no recorded-
    instrument facts in this document have been fabricated. Acreage figures are
    nominal PLSS values pending GLO plat confirmation.
  </div>
</div>
</body>
</html>"""


# ── The 31-12N-24W Roger Mills tract definition ─────────────────────────────────
def roger_mills_31_12n_24w() -> TractReport:
    okcr = "https://okcountyrecords.com/search/roger+mills"
    glo = "https://glorecords.blm.gov/search/default.aspx?searchTabIndex=0&searchByTypeIndex=0"
    occ_finder = ("https://oklahoma.gov/occ/divisions/oil-gas/"
                  "database-search-imaged-documents/occ-well-data-finder.html")
    occ_imaging = "https://imaging.occ.ok.gov/"
    # NB: legacy wellbrowse.occ.ok.gov is decommissioned (DNS no longer resolves);
    # use the current OCC database-search overview + public RBDMS well search.
    occ_dbsearch = ("https://oklahoma.gov/occ/divisions/oil-gas/"
                    "database-search-imaged-documents.html")
    occ_rbdms = ("https://public.occ.ok.gov/OGCDWellRecords/CustomSearch.aspx"
                 "?SearchName=OilandGasWellRecordsSearch&dbid=0&repo=OCC&cr=1")

    src_okcr = Link("OKCountyRecords — Roger Mills", okcr, "search by legal / name")
    src_glo = Link("BLM GLO — patent search", glo, "Sec 31 T12N R24W, Indian Mer.")
    src_occ = Link("OCC Well Data Finder", occ_finder, "wells / pooling")

    chain = [
        ChainRow(
            seq="0", instrument="Sovereignty (Public Domain)",
            grantor="United States of America",
            grantee="(Cheyenne–Arapaho lands; opened by Land Run of Apr 19, 1892)",
            instr_date="1869–1892", rec_date="—", book_page="—", doc_no="—",
            interest="Fee (surface + minerals)",
            legal="All of Sec 31-12N-24W, I.M.",
            source=Link("History — Cheyenne-Arapaho Opening 1892",
                        "https://www.okhistory.org/publications/enc/entry?entry=CH025",
                        "OK Historical Society"),
            verify=False, confirmed=True),
        ChainRow(
            seq="1", instrument="U.S. Patent (Homestead/Cash)",
            grantor="United States of America", grantee="VERIFY — original patentee",
            instr_date="VERIFY (c. 1900–1910)", rec_date="VERIFY",
            book_page="GLO serial", doc_no="VERIFY — GLO accession",
            interest="Fee simple absolute", legal="Per patent (full or aliquot)",
            source=src_glo),
        ChainRow(
            seq="2", instrument="Warranty / Patent-out deeds (root of private title)",
            grantor="VERIFY — patentee", grantee="VERIFY — successors",
            instr_date="VERIFY", rec_date="VERIFY", book_page="VERIFY",
            doc_no="VERIFY", interest="Fee (surface + minerals unless reserved)",
            legal="VERIFY", source=src_okcr),
        ChainRow(
            seq="3", instrument="Mineral Deed / Reservation (sever minerals)",
            grantor="VERIFY", grantee="VERIFY",
            instr_date="VERIFY", rec_date="VERIFY", book_page="VERIFY",
            doc_no="VERIFY", interest="Mineral fee / fractional NMA",
            legal="VERIFY — describe severed interest", source=src_okcr),
        ChainRow(
            seq="4", instrument="Probate / Affidavit of Heirship (descent)",
            grantor="Estate of VERIFY (decedent)", grantee="VERIFY — heirs/devisees",
            instr_date="VERIFY", rec_date="VERIFY", book_page="VERIFY",
            doc_no="VERIFY — case / book-page",
            interest="Descended mineral interest",
            legal="VERIFY", source=src_okcr),
        ChainRow(
            seq="5", instrument="Oil & Gas Lease (current leasehold)",
            grantor="VERIFY — lessor(s)", grantee="VERIFY — lessee/operator",
            instr_date="VERIFY", rec_date="VERIFY", book_page="VERIFY",
            doc_no="VERIFY", interest="Leasehold / royalty (note rate)",
            legal="VERIFY — leased acreage", source=src_okcr),
        ChainRow(
            seq="6", instrument="Assignment(s) of leasehold / ORRI",
            grantor="VERIFY", grantee="VERIFY",
            instr_date="VERIFY", rec_date="VERIFY", book_page="VERIFY",
            doc_no="VERIFY", interest="WI / ORRI",
            legal="VERIFY", source=src_okcr),
        ChainRow(
            seq="7", instrument="OCC Pooling / Spacing Order(s)",
            grantor="Oklahoma Corporation Commission", grantee="(force-pooled units)",
            instr_date="VERIFY", rec_date="OCC case file", book_page="Order #",
            doc_no="VERIFY — OCC cause/order",
            interest="Unitized — election affects royalty",
            legal="VERIFY — pooled formation/unit", source=src_occ),
        ChainRow(
            seq="8", instrument="Most-recent vesting deed (present record owner)",
            grantor="VERIFY", grantee="VERIFY — current owner of record",
            instr_date="VERIFY", rec_date="VERIFY", book_page="VERIFY",
            doc_no="VERIFY", interest="Current mineral/royalty position",
            legal="VERIFY", source=src_okcr),
    ]

    aliquots = [
        Aliquot("NE/4 (NE¼NE¼, NW¼NE¼, SE¼NE¼, SW¼NE¼)", 160.0),
        Aliquot("NW/4 (NE¼NW¼, NW¼NW¼, SE¼NW¼, SW¼NW¼)", 160.0,
                "West-tier — confirm Lots in lieu of W½NW¼"),
        Aliquot("SE/4 (NE¼SE¼, NW¼SE¼, SE¼SE¼, SW¼SE¼)", 160.0),
        Aliquot("SW/4 (NE¼SW¼, NW¼SW¼, SE¼SW¼, SW¼SW¼)", 160.0,
                "West+South tier — confirm Lots in lieu of W½SW¼"),
    ]

    curatives = [
        Curative("Confirm unbroken chain sovereignty → present owner",
                 "Any gap, stray grantee, or missing link in run sheet"),
        Curative("Probate / Affidavit of Heirship for deceased owners",
                 "Owner died testate/intestate without recorded distribution"),
        Curative("Marketable Title Act / 30-yr root verification (16 O.S. §71 et seq.)",
                 "Root of title older than 30 yrs; muniments to be confirmed"),
        Curative("Lease status — HBP vs. expired; ratification of pooling election",
                 "Active O&G lease present; verify production/Pugh clauses"),
        Curative("Entity authority (trust/LLC/estate grantors)",
                 "Grantor is a trust, company, or estate — confirm signatory authority"),
        Curative("Mineral vs. surface severance reconciliation",
                 "Surface and minerals conveyed separately at any point"),
        Curative("Lien / mortgage / tax release search",
                 "Open mortgages, judgment liens, or delinquent ad valorem tax"),
    ]

    sources = [
        Link("Roger Mills County Clerk — OKCountyRecords (deeds, leases, probates)",
             okcr, "indexed from ~1900; search by legal, name, book/page, instrument #"),
        Link("BLM GLO Records — original federal land patents", glo,
             "search State=OK, Meridian=Indian, Twp=12N, Rng=24W, Sec=31"),
        Link("OCC Well Data Finder — wells, API, operator, legal location", occ_finder),
        Link("OCC Imaging — Form 1002A, pooling orders, well logs, case files",
             occ_imaging),
        Link("OCC Database Search & Imaged Documents (overview)", occ_dbsearch),
        Link("OCC RBDMS / Oil & Gas Well Records public search", occ_rbdms,
             "search by legal location, API, operator"),
        Link("Roger Mills County Assessor (okassessor.com)",
             "https://www.okassessor.com/pages/Contact.php",
             "current surface owner / parcel / valuation"),
        Link("Roger Mills County Treasurer — tax rolls",
             "https://oktaxrolls.com/searchTaxRoll/rogermills",
             "ad valorem status, delinquencies"),
        Link("NETROnline — Roger Mills public records gateway",
             "https://publicrecords.netronline.com/state/OK/county/roger_mills"),
        Link("Oklahoma Secretary of State — business entity search",
             "https://www.sos.ok.gov/corp/corpInquiryFind.aspx",
             "confirm authority of entity grantors"),
        Link("Roger Mills County Clerk — direct contact (Cheyenne, OK)",
             "https://oklahoma.publicoffices.org/roger-mills-county-land-records",
             "P.O. Box 708, Cheyenne OK 73628 · (833) 638-7999"),
    ]

    encumbrances = [
        "Active oil & gas leases — VERIFY at OKCountyRecords (lessor, lessee, date, "
        "term, royalty rate, depth/Pugh clauses).",
        "OCC spacing & force-pooling orders — VERIFY at OCC; pooling election "
        "(cash bonus + royalty vs. participate) materially changes the royalty rate.",
        "Mortgages / deeds of trust, judgment & tax liens, easements (pipeline, "
        "road, transmission), and rights-of-way — VERIFY at OKCountyRecords.",
        "Ad valorem / gross-production tax status — VERIFY at County Treasurer.",
    ]

    basin = [
        "Roger Mills County lies in the western Anadarko Basin — a deep, "
        "stacked-pay gas province (Granite Wash, Tonkawa, Cleveland, Marmaton, "
        "Atoka, Morrow, Springer). Confirm producing horizons per OCC well files.",
        "Horizontal Granite Wash / Cleveland development is common; multiple "
        "stacked units may overlie the same surface — verify each formation's "
        "spacing & pooling order separately at OCC.",
        "Determine whether the tract is Held By Production (HBP). Producing wells "
        "in or pooled with Sec 31-12N-24W keep leases alive indefinitely.",
    ]

    limitations = [
        "Examination limited to indexed records reasonably available online as of "
        "the report date; no abstract was certified and no courthouse plant was "
        "physically searched.",
        "No survey was performed; acreage figures are nominal PLSS values and are "
        "subject to the official GLO township plat (west- and south-tier sections "
        "commonly carry government lots, so the full section may not equal 640.00 ac).",
        "No determination of marketability, no examination of bankruptcy, federal "
        "tax-lien, UCC, or probate court files beyond what is recorded in the county "
        "land records is included.",
        "Amber ('VERIFY') cells are unconfirmed and must be populated from the "
        "linked system of record. Reliance for acquisition or division-order "
        "purposes requires a licensed Oklahoma attorney's title opinion.",
        "Mineral and surface estates may be severed; this report addresses the "
        "mineral estate unless a specific instrument states otherwise.",
    ]

    return TractReport(
        company="DataBossX — Mineral Deal Intelligence",
        prepared_by="R. Gille",
        report_date="June 25, 2026",
        section="31", township="12N", range_="24W",
        meridian="Indian Meridian (I.M.)",
        county="Roger Mills", state="Oklahoma",
        report_type="Cursory Title Report",
        legal_long=("All of Section 31, Township 12 North, Range 24 West, Indian "
                     "Meridian, Roger Mills County, Oklahoma — nominally 640.00 "
                     "acres, more or less, together with all oil, gas, and other "
                     "minerals therein and thereunder."),
        section_position=("Section 31 occupies the southwest corner of the township "
                          "(west tier and south tier), numbered under the standard "
                          "boustrophedon scheme."),
        gross_acres=640.0,
        acreage_caution=("ACREAGE CAUTION: Section 31 is a west- AND south-tier "
                         "section. Under the PLSS, the west and south boundary "
                         "subdivisions are frequently platted as government Lots "
                         "(Lots 1–4) of fractional acreage rather than regular "
                         "40-acre aliquots. Confirm the exact subdivision and net "
                         "acreage against the official BLM/GLO township plat before "
                         "relying on the 640.00-acre nominal figure."),
        title_clearance="Unknown — cursory (pending run-sheet population)",
        aliquots=aliquots, chain=chain, curatives=curatives, sources=sources,
        encumbrance_notes=encumbrances, basin_notes=basin, limitations=limitations,
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate a Cursory Title Report (HTML).")
    ap.add_argument("--out", default=None, help="output HTML path")
    ap.add_argument("--open", action="store_true", help="print absolute output path")
    args = ap.parse_args()

    report = roger_mills_31_12n_24w()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out = Path(args.out) if args.out else (
        OUTPUT_DIR
        / "31-12N-24W_Roger_Mills_Cursory_Title_Report_(6-25-2026).html"
    )
    out.write_text(render(report), encoding="utf-8")
    print(f"Wrote {out}")
    if args.open:
        print(out.resolve())


if __name__ == "__main__":
    main()
