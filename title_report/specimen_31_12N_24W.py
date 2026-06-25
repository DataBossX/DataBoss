"""Fully-populated SPECIMEN dataset for Section 31-12N-24W, Roger Mills Co., OK.

SPECIMEN / ILLUSTRATIVE: this models a complete, internally-consistent chain of
title so the report renders every cell, a gap-free chain, and a fully
reconciling ownership matrix (minerals sum to 1; NRI sums to 8/8). It is NOT an
examination of record title -- no live records were pulled. ``data_status`` is
"SPECIMEN" and the cover/QA surface this prominently.

The narrative (illustrative parties):
  * 1903 US patent to Elias J. Thornton (full fee).
  * 1921 deed Thornton -> Caleb T. Mercer (full fee).
  * 1935 Mercer conveys surface + 1/2 minerals to Walter S. Boyd, reserves 1/2.
  * Mercer reserved 1/2 -> 1958 probate -> Ada Mercer -> 1972 Mercer Family Trust.
  * Boyd 1/2 -> 1990 probate -> Helen Boyd Carter (1/4) + Raymond W. Boyd (1/4).
  * 2015 Raymond Boyd sells his 1/4 to Cardinal Minerals LLC.
  * 2018 all minerals leased to Redbud Exploration LLC at 3/16 royalty.
  * 2020 Redbud assigns 100% WI to Sundown Operating LLC, reserving 1/32 ORRI.
  * 2021 Thornton 1-31MH well -> producing -> HBP supported.

Resulting interests (reconcile exactly):
  minerals : Mercer Trust 1/2 + Carter 1/4 + Cardinal 1/4              = 1
  royalty  : (1/2 + 1/4 + 1/4) x 3/16                                  = 3/16
  WI NRI   : 1 x (1 - (3/16 + 1/32))                                   = 25/32
  ORRI     : 1/32
  total NRI: 3/16 + 25/32 + 1/32                                       = 8/8
"""

from __future__ import annotations

from fractions import Fraction as F

from .models import (
    ProjectConfig, Source, Instrument, Abstraction, ChainLink, Well,
    Curative, OwnershipEntry, TitleReport,
)

# Real public portals (links resolve to the live search page for the source).
URL_COUNTY = "https://okcountyrecords.com/"
URL_OCC = "https://gisdata-occokc.opendata.arcgis.com/"
URL_OCC_IMG = "http://imaging.occ.ok.gov/"
URL_BLM = "https://glorecords.blm.gov/"
URL_OTC = "https://oklahoma.gov/tax.html"
URL_OSCN = "https://www.oscn.net/dockets/search.aspx"
URL_SOS = "https://www.sos.ok.gov/corp/corpInquiryFind.aspx"
URL_FRACFOCUS = "https://fracfocus.org/"


def _county_img(book: str, page: str) -> str:
    return f"{URL_COUNTY}search?county=roger-mills&book={book}&page={page}"


def build_report(report_date: str = "2026-06-25") -> TitleReport:
    cfg = ProjectConfig(
        section="31", township="12N", range_="24W", county="Roger Mills", state="OK",
        gross_acres=F(640), net_mineral_acres=F(640),
        acreage_basis="Nominal full-section (640.00 ac) per OCC 640-ac spacing unit; not survey-verified",
        report_date=report_date, source_cutoff_date="2026-06-23",
        prepared_for="DataBoss — Specimen Deliverable",
        preparer="DataBoss Cursory Title Report Engine v0.2",
        report_type="Cursory Title Report",
        is_placeholder=True, data_status="SPECIMEN",
        assumptions=[
            "SPECIMEN: illustrative, internally-consistent title model; NOT an examination of record title.",
            "Acreage 640.00 ac nominal per OCC drilling & spacing unit; not survey-verified.",
            "Mineral estate assumed 100% private (no federal/state mineral reservation of record).",
            "Examination is cursory (index + imaged instruments through the source cutoff date).",
            "All interests stated as exact fractions; derived values computed by live workbook formula.",
        ],
    )

    sources = [
        Source("SRC-001", "County Index", "Roger Mills County Clerk — grantor/grantee & tract index (via OKCountyRecords)",
               location=URL_COUNTY, accessed_date="2026-06-24", doc_count=F(14),
               credential_required=True, page_ref="Books P-3..M-110",
               notes="Accessed via approved credential manager; not pasted in prompts."),
        Source("SRC-002", "OCC", "Oklahoma Corporation Commission — RBDMS well data, spacing/pooling orders, completions",
               location=URL_OCC, accessed_date="2026-06-24", doc_count=F(3),
               credential_required=False, page_ref="Cause CD-2019; Orders 700123/700456",
               notes="Imaging at " + URL_OCC_IMG),
        Source("SRC-003", "BLM/GLO", "BLM General Land Office — federal patent record",
               location=URL_BLM, accessed_date="2026-06-23", doc_count=F(1),
               credential_required=False, page_ref="Patent 1903", notes="MLRS confirms no federal mineral reservation."),
        Source("SRC-004", "OTC", "Oklahoma Tax Commission — gross production records",
               location=URL_OTC, accessed_date="2026-06-24", doc_count=F(1),
               credential_required=False, page_ref="PUN 129-xxxxxx", notes="Confirms operator & production months."),
        Source("SRC-005", "Court", "OSCN / ODCR — probate & civil dockets, Roger Mills County",
               location=URL_OSCN, accessed_date="2026-06-24", doc_count=F(2),
               credential_required=False, page_ref="P-58-21; PB-1990-44", notes="Decrees of distribution reviewed."),
        Source("SRC-006", "Other", "Oklahoma Secretary of State — business entity search",
               location=URL_SOS, accessed_date="2026-06-24", doc_count=F(3),
               credential_required=False, page_ref="Entity filings", notes="Entity good-standing checks."),
        Source("SRC-007", "Other", "FracFocus — completion / frac disclosure (supplemental)",
               location=URL_FRACFOCUS, accessed_date="2026-06-24", doc_count=F(1),
               credential_required=False, page_ref="API 35-129-24567", notes="Supplemental completion date only."),
    ]

    # ── Runsheet (every cell populated) ───────────────────────────────────
    instruments = [
        Instrument("PAT-1903-0001", "US Patent", "P-3", "88", "1903-08-11", "1903-09-02",
                   ["United States of America"], ["Elias J. Thornton"],
                   "The Southwest Quarter and the West Half of the Southeast Quarter and lots... of Section 31, Township 12 North, Range 24 West I.M. (full Section 31)",
                   "31-12N-24W (all)", "Homestead patent (Act of 1862)", "Mineral",
                   "SRC-003 Patent 1903", URL_BLM + "results/default.aspx", "Root of title; full fee to patentee."),
        Instrument("WD-1921-0047", "Warranty Deed", "47", "512", "1921-04-18", "1921-04-25",
                   ["Elias J. Thornton", "Sarah Thornton"], ["Caleb T. Mercer"],
                   "All of Section 31, Township 12 North, Range 24 West", "31-12N-24W (all)",
                   "$3,200.00", "Mineral", "SRC-001 p.47/512", _county_img("47", "512"),
                   "Full fee surface + minerals."),
        Instrument("WD-1935-0088", "Warranty Deed (mineral reservation)", "88", "145", "1935-06-30", "1935-07-08",
                   ["Caleb T. Mercer", "Ada B. Mercer"], ["Walter S. Boyd"],
                   "All of Section 31-12N-24W, RESERVING unto grantors an undivided one-half (1/2) of all oil, gas and other minerals",
                   "31-12N-24W (all)", "$6,400.00", "Mineral", "SRC-001 p.88/145", _county_img("88", "145"),
                   "Surface + 1/2 minerals to Boyd; 1/2 minerals reserved to Mercer."),
        Instrument("PRB-1958-0021", "Decree of Distribution", "121", "04", "1958-03-12", "1958-03-20",
                   ["Estate of Caleb T. Mercer, deceased"], ["Ada B. Mercer"],
                   "Reserved undivided 1/2 mineral interest in Section 31-12N-24W", "31-12N-24W (1/2 min)",
                   "Probate Case P-58-21", "Mineral", "SRC-005 P-58-21", URL_OSCN,
                   "Distributes Caleb Mercer reserved 1/2 minerals to surviving spouse."),
        Instrument("MD-1972-0204", "Mineral Deed", "204", "330", "1972-09-01", "1972-09-14",
                   ["Ada B. Mercer"], ["Mercer Family Trust dated 9/1/1972"],
                   "Undivided 1/2 of all minerals in Section 31-12N-24W", "31-12N-24W (1/2 min)",
                   "$10 & other valuable consideration", "Mineral", "SRC-001 p.204/330", _county_img("204", "330"),
                   "Reserved 1/2 minerals into Mercer Family Trust."),
        Instrument("PRB-1990-0044", "Decree of Distribution", "311", "210", "1990-11-05", "1990-11-19",
                   ["Estate of Walter S. Boyd, deceased"], ["Helen Boyd Carter", "Raymond W. Boyd"],
                   "Surface to Helen Boyd Carter; undivided 1/2 minerals equally to Helen Boyd Carter and Raymond W. Boyd (1/4 each)",
                   "31-12N-24W (surf + 1/2 min)", "Probate Case PB-1990-44", "Mineral", "SRC-005 PB-1990-44", URL_OSCN,
                   "Surface to Carter; Boyd 1/2 minerals split 1/4 + 1/4."),
        Instrument("MD-2015-0502", "Mineral Deed", "502", "18", "2015-07-22", "2015-08-03",
                   ["Raymond W. Boyd"], ["Cardinal Minerals LLC"],
                   "Undivided 1/4 of all minerals in Section 31-12N-24W", "31-12N-24W (1/4 min)",
                   "$96,000.00", "Mineral", "SRC-001 p.502/18", _county_img("502", "18"),
                   "Boyd 1/4 minerals to Cardinal Minerals LLC."),
        Instrument("OGL-2018-0118A", "Oil & Gas Lease", "OGL-118", "77", "2018-05-10", "2018-05-21",
                   ["Mercer Family Trust"], ["Redbud Exploration LLC"],
                   "All minerals owned in Section 31-12N-24W; 3/16 royalty; 3-yr paid-up; Pugh & pooling clauses",
                   "31-12N-24W (1/2 min)", "$400/ac bonus", "Leasehold", "SRC-001 p.OGL-118/77",
                   _county_img("OGL-118", "77"), "Lease of Trust's 1/2; 3/16 royalty."),
        Instrument("OGL-2018-0118B", "Oil & Gas Lease", "OGL-118", "80", "2018-05-12", "2018-05-21",
                   ["Helen Boyd Carter"], ["Redbud Exploration LLC"],
                   "All minerals owned in Section 31-12N-24W; 3/16 royalty; 3-yr paid-up", "31-12N-24W (1/4 min)",
                   "$400/ac bonus", "Leasehold", "SRC-001 p.OGL-118/80", _county_img("OGL-118", "80"),
                   "Lease of Carter 1/4; 3/16 royalty."),
        Instrument("OGL-2018-0118C", "Oil & Gas Lease", "OGL-118", "84", "2018-05-15", "2018-05-21",
                   ["Cardinal Minerals LLC"], ["Redbud Exploration LLC"],
                   "All minerals owned in Section 31-12N-24W; 3/16 royalty; 3-yr paid-up", "31-12N-24W (1/4 min)",
                   "$400/ac bonus", "Leasehold", "SRC-001 p.OGL-118/84", _county_img("OGL-118", "84"),
                   "Lease of Cardinal 1/4; 3/16 royalty."),
        Instrument("ROW-2019-0022", "Right-of-Way Easement", "ROW-22", "5", "2019-08-01", "2019-08-09",
                   ["Helen Boyd Carter"], ["Sundown Operating LLC"],
                   "Pipeline easement 30 ft wide across the SW/4 of Section 31-12N-24W", "31-12N-24W SW/4",
                   "$5,000.00", "Surface", "SRC-001 p.ROW-22/5", _county_img("ROW-22", "5"),
                   "Surface easement; no mineral title effect."),
        Instrument("ASG-2020-0077", "Assignment of OGL (with ORRI reservation)", "A-77", "410", "2020-01-20", "2020-02-03",
                   ["Redbud Exploration LLC"], ["Sundown Operating LLC"],
                   "Assigns 100% of leasehold/WI in the three leases, RESERVING an undivided 1/32 overriding royalty",
                   "31-12N-24W (all leases)", "$10 & other consideration", "Leasehold", "SRC-001 p.A-77/410",
                   _county_img("A-77", "410"), "100% WI to Sundown; 1/32 ORRI reserved to Redbud."),
        Instrument("MTG-2021-0090", "Mortgage", "M-90", "233", "2021-06-15", "2021-06-18",
                   ["Helen Boyd Carter"], ["Western Plains Bank"],
                   "Mortgage on surface & grantor's mineral interest in Section 31-12N-24W securing $120,000.00",
                   "31-12N-24W (Carter int.)", "$120,000.00", "Lien", "SRC-001 p.M-90/233", _county_img("M-90", "233"),
                   "Lien on Carter interest; see release MTG-REL below."),
        Instrument("REL-2024-0110", "Release of Mortgage", "M-110", "11", "2024-02-28", "2024-03-02",
                   ["Western Plains Bank"], ["Helen Boyd Carter"],
                   "Full release of mortgage recorded at Book M-90, Page 233", "31-12N-24W (Carter int.)",
                   "Paid in full", "Lien", "SRC-001 p.M-110/11", _county_img("M-110", "11"),
                   "Releases MTG-2021-0090 of record."),
    ]

    NONE = "None of record"

    abstractions = [
        Abstraction("PAT-1903-0001",
                    "United States grants the described lands to the patentee in fee.",
                    NONE, "No royalty; fee grant.", NONE, NONE, NONE,
                    "No pooling.", NONE, NONE, ["patent", "root"], F(99, 100), False, "SRC-003 Patent 1903"),
        Abstraction("WD-1935-0088",
                    "Grant, bargain, sell and convey unto grantee the described land.",
                    "Grantors reserve an undivided 1/2 of all oil, gas and other minerals, perpetual.",
                    "Royalty N/A (fee deed).", "Subject to easements and reservations of record.",
                    NONE, "No depth limit; reservation covers all depths.", "No pooling.", NONE, NONE,
                    ["deed", "mineral-reservation"], F(98, 100), False, "SRC-001 p.88/145"),
        Abstraction("MD-1972-0204",
                    "Grant and convey undivided 1/2 minerals to the Trust.",
                    NONE, "Royalty N/A.", NONE, NONE, "All depths.", "No pooling.", NONE, NONE,
                    ["mineral-deed", "trust"], F(97, 100), False, "SRC-001 p.204/330"),
        Abstraction("OGL-2018-0118A",
                    "Lessor grants, leases and lets the land for oil and gas exploration and production.",
                    "Lessor reserves 3/16 royalty.", "Royalty three-sixteenths (3/16) of production.",
                    "Subject to existing surface uses.",
                    "Pugh clause: severs unpooled depths below base of Atoka at primary term end; shut-in royalty $1/ac/yr.",
                    "Pugh depth severance below base of Atoka formation.",
                    "Pooling authorized up to 640-ac unit (OCC Orders 700123/700456).",
                    NONE, NONE, ["lease", "royalty", "pugh", "pooling"], F(96, 100), False, "SRC-001 p.OGL-118/77"),
        Abstraction("OGL-2018-0118B",
                    "Lessor grants and leases the land for oil and gas purposes.",
                    "Lessor reserves 3/16 royalty.", "Royalty three-sixteenths (3/16).",
                    "Subject to existing surface uses.", "Shut-in royalty clause; no Pugh clause.",
                    "No depth limit.", "Pooling authorized up to 640 ac.", NONE, NONE,
                    ["lease", "royalty", "pooling"], F(96, 100), False, "SRC-001 p.OGL-118/80"),
        Abstraction("OGL-2018-0118C",
                    "Lessor grants and leases the land for oil and gas purposes.",
                    "Lessor reserves 3/16 royalty.", "Royalty three-sixteenths (3/16).",
                    "Subject to existing surface uses.", "Shut-in royalty clause; no Pugh clause.",
                    "No depth limit.", "Pooling authorized up to 640 ac.", NONE, NONE,
                    ["lease", "royalty", "pooling"], F(96, 100), False, "SRC-001 p.OGL-118/84"),
        Abstraction("ASG-2020-0077",
                    "Assignor assigns all right, title and interest in the described leases to assignee.",
                    "Assignor reserves an undivided 1/32 overriding royalty interest (ORRI).",
                    "ORRI 1/32 of 8/8 production, proportionately reduced.", NONE, NONE,
                    "All depths covered by the assigned leases.",
                    "Assignee succeeds to pooling rights under the leases.", NONE, NONE,
                    ["assignment", "orri", "wi"], F(97, 100), False, "SRC-001 p.A-77/410"),
        Abstraction("MTG-2021-0090",
                    NONE, NONE, NONE, NONE, NONE, "All depths (mortgage on mineral & surface).", NONE,
                    "Mortgage lien securing $120,000.00 to Western Plains Bank.",
                    NONE, ["lien", "mortgage"], F(98, 100), False, "SRC-001 p.M-90/233"),
        Abstraction("REL-2024-0110",
                    "Mortgagee releases and discharges the mortgage of record.", NONE, NONE, NONE, NONE, NONE, NONE,
                    "Releases the lien created by Book M-90, Page 233 in full.", NONE,
                    ["release", "curative"], F(99, 100), False, "SRC-001 p.M-110/11"),
        Abstraction("PRB-1990-0044",
                    "Court decrees distribution of the decedent's estate to the named heirs.",
                    NONE, NONE, NONE, NONE, NONE, NONE, NONE,
                    "Decree of distribution: surface to Carter; 1/2 minerals split 1/4 + 1/4 to Carter and Boyd.",
                    ["probate", "distribution"], F(95, 100), False, "SRC-005 PB-1990-44"),
    ]

    chain = [
        # mineral / surface chain
        ChainLink("mineral_surface", 1, "PAT-1903-0001", "1903-09-02", "US Patent",
                  "United States of America", "Elias J. Thornton", "Full fee (surface + 8/8 minerals)",
                  "", "SRC-003 Patent 1903"),
        ChainLink("mineral_surface", 2, "WD-1921-0047", "1921-04-25", "Warranty Deed",
                  "Elias J. Thornton et ux.", "Caleb T. Mercer", "Full fee", "", "SRC-001 p.47/512"),
        ChainLink("mineral_surface", 3, "WD-1935-0088", "1935-07-08", "Warranty Deed w/ reservation",
                  "Caleb T. Mercer et ux.", "Walter S. Boyd",
                  "Surface + 1/2 minerals to Boyd; 1/2 minerals reserved to Mercer", "", "SRC-001 p.88/145"),
        ChainLink("mineral_surface", 4, "PRB-1958-0021", "1958-03-20", "Decree of Distribution",
                  "Estate of Caleb T. Mercer", "Ada B. Mercer", "Reserved 1/2 minerals", "", "SRC-005 P-58-21"),
        ChainLink("mineral_surface", 5, "MD-1972-0204", "1972-09-14", "Mineral Deed",
                  "Ada B. Mercer", "Mercer Family Trust", "1/2 minerals", "", "SRC-001 p.204/330"),
        ChainLink("mineral_surface", 6, "PRB-1990-0044", "1990-11-19", "Decree of Distribution",
                  "Estate of Walter S. Boyd", "Helen Boyd Carter (surf + 1/4 min); Raymond W. Boyd (1/4 min)",
                  "Surface to Carter; Boyd 1/2 minerals split 1/4 + 1/4", "", "SRC-005 PB-1990-44"),
        ChainLink("mineral_surface", 7, "MD-2015-0502", "2015-08-03", "Mineral Deed",
                  "Raymond W. Boyd", "Cardinal Minerals LLC", "1/4 minerals", "", "SRC-001 p.502/18"),
        # leasehold / WI / burdens chain
        ChainLink("leasehold_wi_burdens", 1, "OGL-2018-0118A", "2018-05-21", "Oil & Gas Lease",
                  "Mercer Family Trust (lessor)", "Redbud Exploration LLC (lessee)",
                  "Leasehold on 1/2 minerals; 3/16 royalty reserved", "", "SRC-001 p.OGL-118/77"),
        ChainLink("leasehold_wi_burdens", 2, "OGL-2018-0118B", "2018-05-21", "Oil & Gas Lease",
                  "Helen Boyd Carter (lessor)", "Redbud Exploration LLC (lessee)",
                  "Leasehold on 1/4 minerals; 3/16 royalty reserved", "", "SRC-001 p.OGL-118/80"),
        ChainLink("leasehold_wi_burdens", 3, "OGL-2018-0118C", "2018-05-21", "Oil & Gas Lease",
                  "Cardinal Minerals LLC (lessor)", "Redbud Exploration LLC (lessee)",
                  "Leasehold on 1/4 minerals; 3/16 royalty reserved", "", "SRC-001 p.OGL-118/84"),
        ChainLink("leasehold_wi_burdens", 4, "ASG-2020-0077", "2020-02-03", "Assignment of OGL",
                  "Redbud Exploration LLC", "Sundown Operating LLC",
                  "100% WI assigned; 1/32 ORRI reserved to Redbud", "", "SRC-001 p.A-77/410"),
    ]

    wells = [
        Well("35-129-24567", "Thornton 1-31MH", "Sundown Operating LLC", "Woodford (Anadarko Basin)",
             "OCC Order 700123 (640-ac unit)", "OCC Order 700456 (pooling)", "2021-03-18",
             "Producing (active)", "Supported", "SRC-002 / SRC-004 / SRC-007"),
    ]

    curative = [
        Curative("CUR-001", "Authority — Trust", "OGL-2018-0118A",
                 "Confirm the acting trustee of the Mercer Family Trust was authorized to execute the 2018 lease covering 1/2 of the minerals.",
                 "High", "1", "Open",
                 "Obtain trust certificate / successor-trustee affidavit confirming authority to lease.",
                 "SRC-001 p.204/330"),
        Curative("CUR-002", "Lease — Pugh/Depth", "OGL-2018-0118A",
                 "Pugh clause severs unpooled depths below base of Atoka at end of primary term; confirm whether deep rights are held or expired.",
                 "Medium", "2", "Open",
                 "Confirm production/operations holding deep rights; obtain release or top lease for expired depths.",
                 "SRC-001 p.OGL-118/77"),
        Curative("CUR-003", "Entity Standing", "MD-2015-0502",
                 "Verify Cardinal Minerals LLC is in good standing and authorized to hold OK minerals (and Redbud/Sundown for leasehold).",
                 "Medium", "2", "Open",
                 "Run OK SOS good-standing checks on Cardinal, Redbud, and Sundown.",
                 "SRC-006 Entity filings"),
        Curative("CUR-004", "Mortgage — Released", "MTG-2021-0090",
                 "Mortgage to Western Plains Bank on the Carter interest; full release recorded 2024-03-02 (Book M-110, Pg 11).",
                 "Low", "3", "Cleared",
                 "None — release of record; confirm release indexed against all affected legals.",
                 "SRC-001 p.M-110/11"),
        Curative("CUR-005", "Surface — ROW", "ROW-2019-0022",
                 "Pipeline easement across SW/4 to Sundown; confirm scope and that it raises no mineral-title defect.",
                 "Low", "3", "Open",
                 "Confirm easement is within the unit and limited to surface use; no curative to mineral title.",
                 "SRC-001 p.ROW-22/5"),
    ]

    ownership = [
        OwnershipEntry("Mercer Family Trust", "royalty", mineral_interest=F(1, 2),
                       lease_royalty=F(3, 16),
                       basis_language="1/2 minerals (MD-1972-0204) leased at 3/16 (OGL-2018-0118A).",
                       citation="SRC-001 p.OGL-118/77"),
        OwnershipEntry("Helen Boyd Carter", "royalty", mineral_interest=F(1, 4),
                       lease_royalty=F(3, 16),
                       basis_language="1/4 minerals (PRB-1990-0044) leased at 3/16 (OGL-2018-0118B).",
                       citation="SRC-001 p.OGL-118/80"),
        OwnershipEntry("Cardinal Minerals LLC", "royalty", mineral_interest=F(1, 4),
                       lease_royalty=F(3, 16),
                       basis_language="1/4 minerals (MD-2015-0502) leased at 3/16 (OGL-2018-0118C).",
                       citation="SRC-001 p.OGL-118/84"),
        OwnershipEntry("Sundown Operating LLC", "working_interest", working_interest=F(1, 1),
                       burdens=F(7, 32),
                       basis_language="100% WI via ASG-2020-0077; burdens = 3/16 royalty + 1/32 ORRI = 7/32.",
                       citation="SRC-001 p.A-77/410"),
        OwnershipEntry("Redbud Exploration LLC", "overriding_royalty", override_royalty=F(1, 32),
                       basis_language="1/32 ORRI reserved in assignment ASG-2020-0077.",
                       citation="SRC-001 p.A-77/410"),
    ]

    return TitleReport(cfg, sources, instruments, abstractions, chain, wells, curative, ownership)
