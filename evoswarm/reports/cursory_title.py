"""Cursory Title Report generator for DataBoss / EvoSwarm.

Renders a complete, professionally-formatted cursory title report (HTML with
working internal anchors + external record links, plus a Markdown mirror) from a
structured, internally-consistent data set. Mineral and royalty decimals are
computed by the real DOI engine (evoswarm.oklahoma.royalty) so every figure ties
out exactly.

IMPORTANT — DATA PROVENANCE
This module ships with an ILLUSTRATIVE worked example for 31-12N-24W, Roger Mills
County, OK. The instruments, parties, books/pages and well data are SYNTHETIC and
were NOT retrieved from county records. The report is watermarked accordingly. To
produce a real report, replace REPORT_DATA by running the DataBoss pipeline
(OK County pull -> OCR -> analysis) and feeding the resulting runsheet in.
"""

from __future__ import annotations

import html
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from evoswarm.oklahoma.royalty import division_order_decimal  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent / "out"
RECORD_BASE = "https://www.okcountyrecords.com/search"
COUNTY = "Roger Mills"
STR_LABEL = "Section 31, Township 12 North, Range 24 West, I.M."
TRACT_KEY = "31-12N-24W"
GROSS_ACRES = Decimal("640.00")
UNIT_ACRES = Decimal("640")          # OCC 640-ac drilling & spacing unit
LEASE_ROYALTY = Decimal("0.1875")    # 3/16
REPORT_DATE = "June 25, 2026"
EFFECTIVE_DATE = "June 20, 2026, 7:00 A.M."


def record_url(book: str, page: str) -> str:
    q = f"?county=Roger+Mills&book={book}&page={page}"
    return RECORD_BASE + q


# ── Structured data ───────────────────────────────────────────────────────────

@dataclass
class Instrument:
    id: str
    itype: str
    book: str
    page: str
    inst_no: str
    inst_date: str
    rec_date: str
    grantors: list[str]
    grantees: list[str]
    interest: str
    consideration: str
    remarks: str


@dataclass
class Owner:
    name: str
    capacity: str            # how title is held
    nma: Decimal             # net mineral acres
    lease_status: str        # Leased 3/16 | Force-Pooled | Unleased
    source_inst: str         # instrument id vesting current interest
    curative: str = ""

    @property
    def mineral_decimal(self) -> Decimal:
        return (self.nma / GROSS_ACRES).quantize(Decimal("0.00000001"))

    @property
    def royalty_decimal(self) -> Decimal:
        # 8-place DOI for a 3/16 lease in the 640-ac unit.
        return division_order_decimal(self.nma, UNIT_ACRES, LEASE_ROYALTY)


@dataclass
class Curative:
    ref: str
    severity: str            # Critical | Material | Minor
    requirement: str
    affects: str


# The fully-chained instrument record (patent -> present).
INSTRUMENTS: list[Instrument] = [
    Instrument("INST-001", "United States Patent", "A-1", "044", "P-1041",
               "1903-05-11", "1903-06-02", ["United States of America"],
               ["Elias T. Boone"], "Surface and all minerals (640.00 ac)",
               "Homestead", "Cheyenne-Arapaho opening; patent of entire Section 31."),
    Instrument("INST-002", "Warranty Deed", "27", "311", "WD-3387",
               "1921-09-30", "1921-10-06", ["Elias T. Boone", "Martha Boone"],
               ["J. W. Halloran"], "Surface and all minerals (640.00 ac)",
               "$3,200.00", "Conveys entire section, surface and minerals."),
    Instrument("INST-003", "Warranty Deed (Mineral Reservation)", "64", "118", "WD-9920",
               "1945-03-18", "1945-03-25", ["J. W. Halloran", "Mabel Halloran"],
               ["Carl F. Wexler", "Ada L. Wexler"],
               "Surface + 1/2 minerals; grantor reserves undivided 1/2 minerals",
               "$8,000.00",
               "FIRST MINERAL SEVERANCE. Halloran reserves 320.00 NMA; Wexlers take "
               "surface + 320.00 NMA."),
    Instrument("INST-004", "Oil & Gas Lease (expired)", "71", "402", "OGL-1188",
               "1955-07-12", "1955-07-20", ["Carl F. Wexler", "et ux"],
               ["Sinclair Oil & Gas Company"], "Oil & gas leasehold, 1/8 royalty",
               "$1.00/ac", "Released 1962 (Book 80, Pg 17); no production. Of record only."),
    Instrument("INST-005", "Final Decree of Distribution", "79", "555", "PR-2207",
               "1961-11-02", "1961-11-15", ["Estate of J. W. Halloran, deceased"],
               ["Mabel Halloran (widow)"], "Reserved 1/2 minerals (320.00 NMA)",
               "Probate", "Case No. 4471, District Court of Roger Mills County. "
               "Vests Halloran reserved minerals in surviving spouse."),
    Instrument("INST-006", "Mineral Deed", "92", "204", "MD-3015",
               "1972-04-19", "1972-04-28", ["Mabel Halloran, a widow"],
               ["Three Sands Royalty Co."], "Undivided 1/2 minerals (320.00 NMA)",
               "$48,000.00", "Conveys all of grantor's 320.00 NMA. Predecessor in "
               "title to Three Sands Royalty Partners, LP (see INST-013)."),
    Instrument("INST-007", "Warranty Deed", "104", "067", "WD-5540",
               "1978-08-14", "1978-08-22", ["Carl F. Wexler", "Ada L. Wexler"],
               ["Wendell A. Krause", "Doris E. Krause"],
               "Surface + 1/2 minerals (320.00 NMA), as joint tenants",
               "$112,000.00", "Krauses take surface and the Wexler 320.00 NMA in JTWROS."),
    Instrument("INST-008", "Mineral Deed", "131", "488", "MD-7781",
               "1989-06-05", "1989-06-12", ["Wendell A. Krause", "Doris E. Krause"],
               ["McBee Family Mineral Trust"], "Undivided 1/4 minerals (160.00 NMA)",
               "$96,000.00", "Trust dated 3/1/1989, Royce & Lana McBee, Trustees. "
               "Leaves Krauses 160.00 NMA."),
    Instrument("INST-009", "Mineral Deed", "158", "021", "MD-9904",
               "1998-10-27", "1998-11-03", ["Wendell A. Krause", "Doris E. Krause"],
               ["Cimarron Minerals, LLC"], "Undivided 1/16 minerals (40.00 NMA)",
               "$30,000.00", "Leaves Krauses 120.00 NMA held jointly."),
    Instrument("INST-010", "Mineral Deed (Partition + Life Estate)", "201", "315", "MD-1466",
               "2005-02-09", "2005-02-16", ["Wendell A. Krause", "Doris E. Krause"],
               ["Wendell A. Krause (80.00 NMA)", "Doris E. Krause (40.00 NMA, life estate)"],
               "Severs joint tenancy: Wendell 80.00 NMA in severalty; Doris 40.00 NMA "
               "life estate, remainder to the heirs of Doris E. Krause",
               "$10.00 & love/affection",
               "Creates the life-estate interest examined in Sec. IV."),
    Instrument("INST-011", "Affidavit of Death & Heirship", "248", "702", "AFF-3120",
               "2019-12-04", "2019-12-10", ["Doris E. Krause, affiant"],
               ["(of record)"], "Re: Wendell A. Krause, died 9/18/2019, Roger Mills Co.",
               "N/A", "Recites death of Wendell A. Krause intestate; surviving spouse "
               "Doris and two children. NO PROBATE of record — see curative C-1."),
    Instrument("INST-012", "Mortgage", "249", "118", "MTG-3199",
               "2019-12-15", "2019-12-20", ["Doris E. Krause"],
               ["Cheyenne Valley State Bank"], "Mortgage on SURFACE estate only",
               "$140,000.00", "Encumbers surface; expressly excepts minerals. Of record, "
               "unreleased."),
    Instrument("INST-013", "Oil & Gas Lease", "262", "440", "OGL-4471",
               "2021-03-22", "2021-03-29", ["Three Sands Royalty Partners, LP"],
               ["Mewbourne Oil Company"], "OGL, 3/16 royalty, 3-yr primary, Pugh clause",
               "$500.00/ac", "Covers 320.00 NMA. Held by production by Redbird 31-1H."),
    Instrument("INST-014", "Oil & Gas Lease", "262", "446", "OGL-4472",
               "2021-04-02", "2021-04-09", ["McBee Family Mineral Trust"],
               ["Mewbourne Oil Company"], "OGL, 3/16 royalty, 3-yr primary",
               "$500.00/ac", "Covers 160.00 NMA. Held by production."),
    Instrument("INST-015", "Oil & Gas Lease", "263", "012", "OGL-4480",
               "2021-04-19", "2021-04-26", ["Cimarron Minerals, LLC"],
               ["Mewbourne Oil Company"], "OGL, 3/16 royalty, 3-yr primary",
               "$500.00/ac", "Covers 40.00 NMA. Held by production."),
    Instrument("INST-016", "OCC Spacing & Pooling Order", "264", "880", "OCC-2021-318447",
               "2021-06-15", "2021-06-30", ["Oklahoma Corporation Commission"],
               ["(all respondents)"], "640-ac drilling & spacing unit; Woodford/Springer",
               "Order", "Order No. 318447, Cause CD 2021-000991. Force-pools "
               "non-consenting/unleased interests; 3/16 royalty election available."),
    Instrument("INST-017", "Right-of-Way Easement", "271", "204", "ROW-5567",
               "2022-05-10", "2022-05-17", ["Doris E. Krause", "et al"],
               ["Mewbourne Pipeline, LLC"], "30-ft pipeline easement across S/2",
               "$7,500.00", "Surface burden; gathering line to Redbird 31-1H."),
]

# Current mineral ownership (ties to 640.00 NMA; royalty decimals tie to 0.1875).
OWNERS: list[Owner] = [
    Owner("Three Sands Royalty Partners, LP", "Partnership (successor to Three Sands "
          "Royalty Co.)", Decimal("320.00"), "Leased 3/16 (INST-013)", "INST-006"),
    Owner("McBee Family Mineral Trust", "Trust dtd 3/1/1989", Decimal("160.00"),
          "Leased 3/16 (INST-014)", "INST-008"),
    Owner("Estate of Wendell A. Krause, deceased", "Intestate estate (unadministered)",
          Decimal("80.00"), "Force-Pooled (OCC Order 318447)", "INST-010",
          curative="C-1"),
    Owner("Doris E. Krause", "Life estate; remainder to heirs of Doris E. Krause",
          Decimal("40.00"), "Force-Pooled (OCC Order 318447)", "INST-010",
          curative="C-2"),
    Owner("Cimarron Minerals, LLC", "Oklahoma LLC", Decimal("40.00"),
          "Leased 3/16 (INST-015)", "INST-009"),
]

CURATIVES: list[Curative] = [
    Curative("C-1", "Critical",
             "Probate or determine heirship of Wendell A. Krause (d. 9/18/2019, "
             "intestate). Of record only by Affidavit of Death & Heirship (INST-011), "
             "which is insufficient to merchantably vest the 80.00 NMA. Obtain Oklahoma "
             "probate or §83 affidavit of heirship recorded 10+ years, plus releases of "
             "estate tax liens.", "80.00 NMA (Estate of Wendell A. Krause)"),
    Curative("C-2", "Material",
             "Confirm the Doris E. Krause life estate and identify vested remaindermen "
             "(heirs) per INST-010. A life tenant cannot execute a merchantable lease "
             "beyond the life estate without joinder of remaindermen; secure ratification "
             "or remaindermen joinder before relying on any lease of this 40.00 NMA.",
             "40.00 NMA (Doris E. Krause life estate)"),
    Curative("C-3", "Material",
             "Confirm Mewbourne force-pooling election and royalty/bonus election deadline "
             "for the unleased/force-pooled 120.00 NMA under OCC Order 318447 (INST-016); "
             "verify the election was perfected and consideration tendered.",
             "120.00 NMA (force-pooled)"),
    Curative("C-4", "Minor",
             "Obtain recorded release of the Sinclair 1955 oil & gas lease confirmation "
             "(INST-004) if not already cured by the 1962 release; run release book/page "
             "to clear the of-record cloud.", "All minerals (of record cloud only)"),
    Curative("C-5", "Minor",
             "Surface mortgage to Cheyenne Valley State Bank (INST-012) is unreleased; "
             "confirm it excepts minerals (it does, by its terms) and obtain subordination "
             "if surface use is required.", "Surface estate"),
]

WELL = {
    "name": "Redbird 31-1H",
    "api": "35-129-24417",
    "operator": "Mewbourne Oil Company",
    "status": "Producing (oil & gas)",
    "spud": "2022-01-14",
    "first_prod": "2022-06-01",
    "formation": "Woodford / Springer",
    "unit": "640-ac DSU, Sec. 31-12N-24W (OCC Order 318447)",
}


# ── Rendering ─────────────────────────────────────────────────────────────────

def e(s) -> str:
    return html.escape(str(s))


def _verify_totals() -> dict:
    nma = sum((o.nma for o in OWNERS), Decimal("0"))
    min_dec = sum((o.mineral_decimal for o in OWNERS), Decimal("0"))
    roy_dec = sum((o.royalty_decimal for o in OWNERS), Decimal("0"))
    return {"nma": nma, "mineral_decimal": min_dec, "royalty_decimal": roy_dec}


SECTIONS = [
    ("s1", "I. Tract Identification"),
    ("s2", "II. Examination Summary & Marketability"),
    ("s3", "III. Surface Ownership"),
    ("s4", "IV. Mineral Ownership & Division of Interest"),
    ("s5", "V. Leasehold & Operations"),
    ("s6", "VI. Chain of Title"),
    ("s7", "VII. Instrument Abstracts"),
    ("s8", "VIII. Encumbrances & Burdens"),
    ("s9", "IX. Curative Requirements"),
    ("s10", "X. Sources & Record Links"),
    ("s11", "XI. Examiner Certification"),
]


def render_html() -> str:
    t = _verify_totals()
    sev_class = {"Critical": "crit", "Material": "matl", "Minor": "minr"}

    css = """
    :root{--ink:#1f2937;--muted:#6b7280;--line:#d1d5db;--navy:#1F4E79;--accent:#b45309}
    *{box-sizing:border-box}
    body{font:14px/1.5 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
      color:var(--ink);margin:0;background:#f3f4f6}
    .page{max-width:1000px;margin:0 auto;background:#fff;padding:48px 56px;
      box-shadow:0 1px 4px rgba(0,0,0,.1)}
    h1{font-size:24px;margin:0 0 2px;color:var(--navy)}
    h2{font-size:18px;color:var(--navy);border-bottom:2px solid var(--navy);
      padding-bottom:4px;margin-top:36px}
    h3{font-size:14px;margin:18px 0 6px}
    a{color:var(--navy);text-decoration:none}a:hover{text-decoration:underline}
    .sub{color:var(--muted)}
    .watermark{background:#fff7ed;border:1px solid var(--accent);color:#7c2d12;
      padding:10px 14px;border-radius:6px;margin:16px 0;font-size:12.5px}
    table{border-collapse:collapse;width:100%;margin:10px 0;font-size:12.5px}
    th,td{border:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}
    th{background:var(--navy);color:#fff;font-weight:600}
    tr:nth-child(even) td{background:#f9fafb}
    .num{text-align:right;font-variant-numeric:tabular-nums}
    .meta{display:grid;grid-template-columns:1fr 1fr;gap:4px 24px;margin:14px 0}
    .meta div{border-bottom:1px dotted var(--line);padding:3px 0}
    .k{color:var(--muted)}
    .toc{columns:2;margin:8px 0 0}
    .toc a{display:block;padding:2px 0}
    .crit{color:#b91c1c;font-weight:700}.matl{color:#b45309;font-weight:700}
    .minr{color:#047857;font-weight:600}
    .top{font-size:11px;color:var(--muted)}
    .pill{display:inline-block;padding:1px 7px;border-radius:10px;font-size:11px;
      background:#e5edf5;color:var(--navy)}
    footer{margin-top:40px;border-top:1px solid var(--line);padding-top:12px;
      color:var(--muted);font-size:11.5px}
    code{background:#f3f4f6;padding:1px 4px;border-radius:3px}
    """

    def top():
        return '<div class="top"><a href="#toc">↑ Back to contents</a></div>'

    P = []
    P.append(f"<!doctype html><html lang=en><head><meta charset=utf-8>")
    P.append(f"<meta name=viewport content='width=device-width,initial-scale=1'>")
    P.append(f"<title>{TRACT_KEY} {e(COUNTY)} Cursory Title Report</title>")
    P.append(f"<style>{css}</style></head><body><div class=page>")

    # Header
    P.append(f"<h1>Cursory Title Report</h1>")
    P.append(f"<div class=sub>{e(STR_LABEL)} &nbsp;·&nbsp; {e(COUNTY)} County, Oklahoma</div>")
    P.append('<div class=meta>'
             f'<div><span class=k>Tract:</span> {TRACT_KEY} ({GROSS_ACRES} ac, full section)</div>'
             f'<div><span class=k>Report date:</span> {REPORT_DATE}</div>'
             f'<div><span class=k>Effective (certified) thru:</span> {EFFECTIVE_DATE}</div>'
             f'<div><span class=k>County:</span> {e(COUNTY)}, OK (FIPS 35-129)</div>'
             f'<div><span class=k>Examination type:</span> Cursory (preliminary, non-opinion)</div>'
             f'<div><span class=k>Prepared by:</span> DataBoss · EvoSwarm title agent</div>'
             '</div>')

    P.append('<div class=watermark><b>⚠ ILLUSTRATIVE SAMPLE — SYNTHETIC DATA.</b> '
             'This document demonstrates report format and chain logic. The parties, '
             'instruments, book/page citations, OCC order and well were NOT retrieved '
             'from Roger Mills County records and must not be relied upon for any '
             'transaction. Decimals are mathematically exact for the example. Replace '
             'with live runsheet data before use. This is not a title opinion.</div>')

    # TOC
    P.append('<h2 id=toc>Table of Contents</h2><nav class=toc>')
    for sid, name in SECTIONS:
        P.append(f'<a href="#{sid}">{e(name)}</a>')
    P.append('</nav>')

    # I. Tract
    P.append(f'<h2 id=s1>I. Tract Identification</h2>')
    P.append('<div class=meta>'
             f'<div><span class=k>Legal:</span> {e(STR_LABEL)}</div>'
             f'<div><span class=k>Gross acres:</span> {GROSS_ACRES}</div>'
             f'<div><span class=k>Net mineral acres:</span> {GROSS_ACRES} (examined 100%)</div>'
             f'<div><span class=k>Drilling/spacing unit:</span> 640 ac (OCC Order 318447)</div>'
             f'<div><span class=k>Search period:</span> Sovereignty (1903 Patent) → {REPORT_DATE}</div>'
             f'<div><span class=k>Records searched:</span> Roger Mills Co. Clerk; OCC; District Court</div>'
             '</div>')

    # II. Summary
    P.append(f'<h2 id=s2>II. Examination Summary &amp; Marketability</h2>')
    P.append('<p>Record title to the minerals under the captioned tract is vested as set '
             'out in Section IV and traces by an unbroken chain from the 1903 United '
             'States Patent. Title is <b>marketable subject to the curative requirements '
             'in Section IX</b>. The mineral estate was severed from the surface in 1945 '
             '(INST-003) and has since fractionated into five ownership groups totaling '
             f'{t["nma"]} NMA. Production exists; the 2021 leases are held by production '
             'by the Redbird 31-1H (Section V).</p>')
    P.append('<table><tr><th>Marketability driver</th><th>Status</th></tr>'
             '<tr><td>Chain unbroken from sovereignty</td><td>Yes</td></tr>'
             '<tr><td>Mineral decimals reconcile to 1.00000000</td>'
             f'<td>Yes — {t["mineral_decimal"]}</td></tr>'
             '<tr><td>Royalty decimals reconcile to lease 3/16</td>'
             f'<td>Yes — {t["royalty_decimal"]}</td></tr>'
             '<tr><td>Open curative items</td><td>'
             f'{len(CURATIVES)} (1 critical) — see Sec. IX</td></tr></table>')
    P.append(top())

    # III. Surface
    P.append(f'<h2 id=s3>III. Surface Ownership</h2>')
    P.append('<table><tr><th>Owner</th><th>Interest</th><th>Vesting instrument</th>'
             '<th>Encumbrances</th></tr>'
             '<tr><td>Doris E. Krause</td><td>Surface estate (100%)</td>'
             '<td><a href="#INST-007">INST-007</a>, <a href="#INST-010">INST-010</a></td>'
             '<td>Mortgage <a href="#INST-012">INST-012</a>; pipeline ROW '
             '<a href="#INST-017">INST-017</a></td></tr></table>')

    # IV. Mineral DOI
    P.append(f'<h2 id=s4>IV. Mineral Ownership &amp; Division of Interest</h2>')
    P.append('<p class=sub>Mineral decimal = NMA ÷ 640. Royalty (net-revenue) decimal = '
             'NMA ÷ 640-ac unit × 3/16 lease royalty, carried to 8 places per industry '
             'convention. Computed by the DataBoss DOI engine.</p>')
    P.append('<table><tr><th>#</th><th>Mineral owner</th><th>Capacity</th>'
             '<th class=num>NMA</th><th class=num>Mineral decimal</th>'
             '<th class=num>Royalty decimal (3/16)</th><th>Lease status</th>'
             '<th>Vesting</th><th>Curative</th></tr>')
    for i, o in enumerate(OWNERS, 1):
        cur = (f'<a href="#s9">{o.curative}</a>' if o.curative else '—')
        P.append(f'<tr><td>{i}</td><td><b>{e(o.name)}</b></td><td>{e(o.capacity)}</td>'
                 f'<td class=num>{o.nma}</td><td class=num>{o.mineral_decimal}</td>'
                 f'<td class=num>{o.royalty_decimal}</td><td>{e(o.lease_status)}</td>'
                 f'<td><a href="#{o.source_inst}">{o.source_inst}</a></td>'
                 f'<td>{cur}</td></tr>')
    P.append(f'<tr><td></td><td><b>TOTAL</b></td><td></td>'
             f'<td class=num><b>{t["nma"]}</b></td>'
             f'<td class=num><b>{t["mineral_decimal"]}</b></td>'
             f'<td class=num><b>{t["royalty_decimal"]}</b></td>'
             f'<td colspan=3 class=sub>reconciles to 1.00000000 / 0.18750000</td></tr>')
    P.append('</table>')
    P.append(top())

    # V. Leasehold
    P.append(f'<h2 id=s5>V. Leasehold &amp; Operations</h2>')
    P.append('<table>'
             f'<tr><th>Well</th><td>{e(WELL["name"])} (API {e(WELL["api"])})</td>'
             f'<th>Operator</th><td>{e(WELL["operator"])}</td></tr>'
             f'<tr><th>Status</th><td>{e(WELL["status"])}</td>'
             f'<th>Formation</th><td>{e(WELL["formation"])}</td></tr>'
             f'<tr><th>Spud</th><td>{e(WELL["spud"])}</td>'
             f'<th>First prod.</th><td>{e(WELL["first_prod"])}</td></tr>'
             f'<tr><th>Unit</th><td colspan=3>{e(WELL["unit"])}</td></tr></table>')
    P.append('<p>Active leases: <a href="#INST-013">INST-013</a> (Three Sands, 320 NMA), '
             '<a href="#INST-014">INST-014</a> (McBee, 160 NMA), '
             '<a href="#INST-015">INST-015</a> (Cimarron, 40 NMA), each 3/16 and HBP. '
             'The 120 NMA Krause interests are force-pooled under '
             '<a href="#INST-016">INST-016</a>.</p>')

    # VI. Chain of title
    P.append(f'<h2 id=s6>VI. Chain of Title</h2>')
    P.append('<table><tr><th>Inst.</th><th>Type</th><th>Dated</th><th>Recorded</th>'
             '<th>Book/Pg</th><th>Grantor → Grantee</th><th>Interest</th>'
             '<th>Record</th></tr>')
    for ins in INSTRUMENTS:
        gg = f'{"; ".join(ins.grantors)} → {"; ".join(ins.grantees)}'
        P.append(f'<tr><td><a href="#{ins.id}">{ins.id}</a></td><td>{e(ins.itype)}</td>'
                 f'<td>{e(ins.inst_date)}</td><td>{e(ins.rec_date)}</td>'
                 f'<td>{e(ins.book)}/{e(ins.page)}</td><td>{e(gg)}</td>'
                 f'<td>{e(ins.interest)}</td>'
                 f'<td><a href="{record_url(ins.book, ins.page)}" target=_blank '
                 f'rel=noopener>view ↗</a></td></tr>')
    P.append('</table>')
    P.append(top())

    # VII. Abstracts
    P.append(f'<h2 id=s7>VII. Instrument Abstracts</h2>')
    for ins in INSTRUMENTS:
        P.append(f'<h3 id="{ins.id}">{ins.id} — {e(ins.itype)} '
                 f'<span class=pill>Bk {e(ins.book)} Pg {e(ins.page)}</span></h3>')
        P.append('<div class=meta>'
                 f'<div><span class=k>Instrument #:</span> {e(ins.inst_no)}</div>'
                 f'<div><span class=k>Dated / Recorded:</span> {e(ins.inst_date)} / {e(ins.rec_date)}</div>'
                 f'<div><span class=k>Grantor(s):</span> {e("; ".join(ins.grantors))}</div>'
                 f'<div><span class=k>Grantee(s):</span> {e("; ".join(ins.grantees))}</div>'
                 f'<div><span class=k>Interest:</span> {e(ins.interest)}</div>'
                 f'<div><span class=k>Consideration:</span> {e(ins.consideration)}</div>'
                 '</div>')
        P.append(f'<p>{e(ins.remarks)} '
                 f'<a href="{record_url(ins.book, ins.page)}" target=_blank rel=noopener>'
                 f'Open county record ↗</a></p>')
        P.append(top())

    # VIII. Encumbrances
    P.append(f'<h2 id=s8>VIII. Encumbrances &amp; Burdens</h2>')
    P.append('<table><tr><th>Type</th><th>Instrument</th><th>Holder</th><th>Affects</th>'
             '<th>Status</th></tr>'
             '<tr><td>Oil &amp; gas leases (3)</td>'
             '<td><a href="#INST-013">013</a>/<a href="#INST-014">014</a>/'
             '<a href="#INST-015">015</a></td><td>Mewbourne Oil Company</td>'
             '<td>520 NMA</td><td>Active, HBP</td></tr>'
             '<tr><td>Force-pooling order</td><td><a href="#INST-016">INST-016</a></td>'
             '<td>OCC</td><td>120 NMA</td><td>In effect</td></tr>'
             '<tr><td>Mortgage (surface)</td><td><a href="#INST-012">INST-012</a></td>'
             '<td>Cheyenne Valley State Bank</td><td>Surface</td><td>Unreleased</td></tr>'
             '<tr><td>Pipeline easement</td><td><a href="#INST-017">INST-017</a></td>'
             '<td>Mewbourne Pipeline, LLC</td><td>S/2 surface</td><td>Recorded</td></tr>'
             '<tr><td>Prior OGL (Sinclair)</td><td><a href="#INST-004">INST-004</a></td>'
             '<td>Sinclair (expired)</td><td>Minerals</td><td>Released 1962</td></tr></table>')

    # IX. Curative
    P.append(f'<h2 id=s9>IX. Curative Requirements</h2>')
    P.append('<table><tr><th>Ref</th><th>Severity</th><th>Requirement</th>'
             '<th>Affects</th></tr>')
    for c in CURATIVES:
        P.append(f'<tr><td>{c.ref}</td>'
                 f'<td class={sev_class[c.severity]}>{c.severity}</td>'
                 f'<td>{e(c.requirement)}</td><td>{e(c.affects)}</td></tr>')
    P.append('</table>')
    P.append(top())

    # X. Sources
    P.append(f'<h2 id=s10>X. Sources &amp; Record Links</h2>')
    P.append('<p>Each instrument links to its county record image via the Roger Mills '
             'County records portal (subscription/login may be required). Link pattern: '
             f'<code>{RECORD_BASE}?county=Roger+Mills&amp;book=&lt;bk&gt;&amp;page=&lt;pg&gt;</code></p>')
    P.append('<table><tr><th>Source</th><th>Coverage</th><th>Link</th></tr>'
             '<tr><td>Roger Mills County Clerk</td><td>Deeds, leases, mortgages, ROW</td>'
             f'<td><a href="{RECORD_BASE}?county=Roger+Mills" target=_blank rel=noopener>'
             'okcountyrecords.com ↗</a></td></tr>'
             '<tr><td>Oklahoma Corporation Commission</td><td>Spacing/pooling orders, wells</td>'
             '<td><a href="https://oklahoma.gov/occ.html" target=_blank rel=noopener>occ ↗</a></td></tr>'
             '<tr><td>OCC well records (Redbird 31-1H)</td><td>API 35-129-24417</td>'
             '<td><a href="https://oklahoma.gov/occ/divisions/oil-gas.html" target=_blank '
             'rel=noopener>well browse ↗</a></td></tr></table>')

    # XI. Certification
    P.append(f'<h2 id=s11>XI. Examiner Certification</h2>')
    P.append('<p>This <b>cursory</b> examination was prepared for internal evaluation only '
             'and is <b>not a title opinion</b> and not a guarantee of title. It is limited '
             'to the records cited and the effective date above, and is expressly subject '
             'to the curative requirements in Section IX. No liability is assumed. '
             '<i>(Sample certification — synthetic data.)</i></p>')
    P.append(top())

    P.append(f'<footer>Generated by DataBoss · EvoSwarm cursory-title generator. '
             f'Tract {TRACT_KEY}, {e(COUNTY)} County, OK. {REPORT_DATE}. '
             'ILLUSTRATIVE SAMPLE — not for transactional use.</footer>')
    P.append('</div></body></html>')
    return "\n".join(P)


def render_markdown() -> str:
    t = _verify_totals()
    L = []
    L.append(f"# Cursory Title Report — {TRACT_KEY}, {COUNTY} County, OK\n")
    L.append(f"**{STR_LABEL}**  ")
    L.append(f"Report date: {REPORT_DATE} · Effective thru: {EFFECTIVE_DATE} · "
             f"Gross/NMA: {GROSS_ACRES}\n")
    L.append("> ⚠ **ILLUSTRATIVE SAMPLE — SYNTHETIC DATA.** Parties, instruments, "
             "book/page, OCC order and well were not retrieved from county records and "
             "must not be relied upon. Decimals are exact for the example. Not a title "
             "opinion.\n")
    L.append("## IV. Mineral Ownership & Division of Interest\n")
    L.append("| # | Mineral owner | NMA | Mineral decimal | Royalty decimal (3/16) | "
             "Lease status | Vesting | Curative |")
    L.append("|--|--|--:|--:|--:|--|--|--|")
    for i, o in enumerate(OWNERS, 1):
        L.append(f"| {i} | {o.name} | {o.nma} | {o.mineral_decimal} | "
                 f"{o.royalty_decimal} | {o.lease_status} | {o.source_inst} | "
                 f"{o.curative or '—'} |")
    L.append(f"| | **TOTAL** | **{t['nma']}** | **{t['mineral_decimal']}** | "
             f"**{t['royalty_decimal']}** | | | |\n")
    L.append("## VI. Chain of Title\n")
    L.append("| Inst | Type | Dated | Recorded | Bk/Pg | Grantor → Grantee | Interest | Record |")
    L.append("|--|--|--|--|--|--|--|--|")
    for ins in INSTRUMENTS:
        gg = f'{"; ".join(ins.grantors)} → {"; ".join(ins.grantees)}'
        L.append(f"| {ins.id} | {ins.itype} | {ins.inst_date} | {ins.rec_date} | "
                 f"{ins.book}/{ins.page} | {gg} | {ins.interest} | "
                 f"[view]({record_url(ins.book, ins.page)}) |")
    L.append("\n## IX. Curative Requirements\n")
    L.append("| Ref | Severity | Requirement | Affects |")
    L.append("|--|--|--|--|")
    for c in CURATIVES:
        L.append(f"| {c.ref} | {c.severity} | {c.requirement} | {c.affects} |")
    L.append("")
    return "\n".join(L)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stem = "31-12N-24W_Roger_Mills_Cursory_Title_Report_(6-25-2026)"
    html_path = OUT_DIR / f"{stem}.html"
    md_path = OUT_DIR / f"{stem}.md"
    html_path.write_text(render_html())
    md_path.write_text(render_markdown())
    t = _verify_totals()
    print(f"wrote {html_path}")
    print(f"wrote {md_path}")
    print(f"reconcile: NMA={t['nma']} mineral={t['mineral_decimal']} "
          f"royalty={t['royalty_decimal']}")
    assert t["nma"] == GROSS_ACRES, "NMA must total 640.00"
    assert t["mineral_decimal"] == Decimal("1.00000000"), "mineral decimals must total 1"
    assert t["royalty_decimal"] == LEASE_ROYALTY.quantize(Decimal("0.00000001")), \
        "royalty decimals must total 3/16"
    print("RECONCILED OK")


if __name__ == "__main__":
    main()
