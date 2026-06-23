"""Illustrative placeholder dataset for Section 31-11N-24W, Roger Mills Co., OK.

IMPORTANT: This is NOT an examined title. No live county, OCC, BLM, or court
records were available in the build environment, so the rows below are
clearly-flagged *illustrative placeholders* that exercise every schedule and
formula end to end. Their purpose is to demonstrate the report structure, not
to assert facts about real chain of title.

``config.is_placeholder`` is True; the workbook cover sheet surfaces this
prominently and the QA report records it. Replace :func:`build_sample_report`
with examined data to produce a real report.
"""

from __future__ import annotations

from fractions import Fraction

from .models import (
    ProjectConfig,
    Source,
    Instrument,
    Abstraction,
    ChainLink,
    Well,
    Curative,
    OwnershipEntry,
    TitleReport,
    UNKNOWN,
)


def build_sample_report(report_date: str = "2026-06-23") -> TitleReport:
    config = ProjectConfig(
        section="31",
        township="11N",
        range_="24W",
        county="Roger Mills",
        state="OK",
        gross_acres=Fraction(640),          # nominal full-section assumption
        net_mineral_acres=Fraction(640),    # 100% basis assumption (stated)
        acreage_basis="Nominal full-section (640 ac) assumption; not survey-verified",
        report_date=report_date,
        source_cutoff_date="2026-06-19",
        prepared_for="ILLUSTRATIVE / PLACEHOLDER",
        preparer="DataBoss Title Report Engine (placeholder run)",
        report_type="Cursory Title Report",
        is_placeholder=True,
        assumptions=[
            "PLACEHOLDER DATA: no live county/OCC/BLM/court records were examined.",
            "Acreage assumed at 640 nominal acres for the full section; not survey-verified.",
            "Mineral acreage assumed at 100% of the section absent a contrary instrument.",
            "All UNKNOWN fields require examination of the underlying instrument.",
            "Cursory scope: index-level review only; not a full stand-up abstract.",
        ],
    )

    sources = [
        Source("SRC-001", "County Index", "Roger Mills County Clerk grantor/grantee index",
               location="OKCountyRecords / county clerk portal", accessed_date=UNKNOWN,
               credential_required=True, notes="Login via approved credential manager; not pulled here."),
        Source("SRC-002", "OCC", "OCC RBDMS well & case data",
               location="https://oklahoma.gov/occ", accessed_date=UNKNOWN,
               notes="Spacing/pooling orders, completions, production -- not pulled here."),
        Source("SRC-003", "BLM/GLO", "BLM GLO patents & MLRS records",
               location="https://glorecords.blm.gov", accessed_date=UNKNOWN),
        Source("SRC-004", "OTC", "Oklahoma Tax Commission gross production",
               location="https://oklahoma.gov/tax", accessed_date=UNKNOWN),
        Source("SRC-005", "Court", "OSCN / ODCR civil & probate dockets",
               location="https://www.oscn.net", accessed_date=UNKNOWN),
    ]

    instruments = [
        Instrument(
            instrument_no="SAMPLE-0001", instrument_type="Patent",
            book="P-1", page="001", instrument_date="1904-05-02", recording_date="1904-06-10",
            grantors=["United States of America"], grantees=["John Q. Settler"],
            legal_raw="Section 31, Township 11 North, Range 24 West I.M.",
            legal_normalized="31-11N-24W", consideration="Homestead patent",
            classification="Mineral", citation="SRC-003 p.1",
            notes="ILLUSTRATIVE root-of-title patent."),
        Instrument(
            instrument_no="SAMPLE-0002", instrument_type="Warranty Deed",
            book="142", page="318", instrument_date="1948-03-15", recording_date="1948-03-20",
            grantors=["John Q. Settler", "Mary Settler"], grantees=["Settler Family Trust"],
            legal_raw="All of Section 31-11N-24W", legal_normalized="31-11N-24W",
            consideration="$10 and love and affection", classification="Mineral",
            citation="SRC-001 p.142/318", notes="ILLUSTRATIVE surface+minerals conveyance."),
        Instrument(
            instrument_no="SAMPLE-0003", instrument_type="Oil & Gas Lease",
            book="OGL-7", page="221", instrument_date="2019-08-01", recording_date="2019-08-14",
            grantors=["Settler Family Trust"], grantees=["Acme Operating LLC"],
            legal_raw="SW/4 of Section 31-11N-24W", legal_normalized="31-11N-24W SW/4",
            consideration=UNKNOWN, classification="Leasehold",
            citation="SRC-001 p.OGL-7/221", notes="ILLUSTRATIVE lease; 3/16 royalty per abstraction."),
        Instrument(
            instrument_no="SAMPLE-0004", instrument_type="Mortgage",
            book="M-55", page="099", instrument_date="2020-01-10", recording_date="2020-01-12",
            grantors=["Settler Family Trust"], grantees=["First Prairie Bank"],
            legal_raw="Section 31-11N-24W", legal_normalized="31-11N-24W",
            consideration=UNKNOWN, classification="Lien",
            citation="SRC-001 p.M-55/099", notes="ILLUSTRATIVE mortgage; release not located."),
    ]

    abstractions = [
        Abstraction(
            instrument_no="SAMPLE-0003",
            grant_clause="Lessor grants and leases the described land for oil and gas purposes.",
            reservations=UNKNOWN,
            royalty_wi_language="Lessor royalty of three-sixteenths (3/16).",
            exceptions=UNKNOWN,
            pugh_shutin="Shut-in royalty clause present; Pugh clause UNKNOWN.",
            depth_limits=UNKNOWN,
            pooling_refs="Pooling authorized up to 640 acres.",
            liens=UNKNOWN, probate=UNKNOWN,
            tags=["lease", "royalty", "pooling"], confidence=Fraction(9, 10),
            needs_review=True, citation="SRC-001 p.OGL-7/221"),
        Abstraction(
            instrument_no="SAMPLE-0004",
            grant_clause=UNKNOWN, reservations=UNKNOWN, royalty_wi_language=UNKNOWN,
            exceptions=UNKNOWN, pugh_shutin=UNKNOWN, depth_limits=UNKNOWN,
            pooling_refs=UNKNOWN, liens="Mortgage lien securing UNKNOWN principal.",
            probate=UNKNOWN, tags=["lien", "mortgage"], confidence=Fraction(8, 10),
            needs_review=True, citation="SRC-001 p.M-55/099"),
    ]

    chain_links = [
        ChainLink("mineral_surface", 1, "SAMPLE-0001", date="1904-06-10",
                  conveyance="US Patent", from_party="United States",
                  to_party="John Q. Settler", interest="Full fee (surface + minerals)",
                  citation="SRC-003 p.1"),
        ChainLink("mineral_surface", 2, "SAMPLE-0002", date="1948-03-20",
                  conveyance="Warranty Deed", from_party="John Q. Settler et ux.",
                  to_party="Settler Family Trust", interest="Full fee",
                  gap_note="44-yr gap 1904-1948 not abstracted (cursory scope).",
                  citation="SRC-001 p.142/318"),
        ChainLink("leasehold_wi_burdens", 1, "SAMPLE-0003", date="2019-08-14",
                  conveyance="Oil & Gas Lease", from_party="Settler Family Trust (lessor)",
                  to_party="Acme Operating LLC (lessee)", interest="Leasehold, 3/16 royalty reserved",
                  citation="SRC-001 p.OGL-7/221"),
    ]

    wells = [
        Well(api_number="35-129-SAMPLE", well_name="Settler 31-1H",
             operator="Acme Operating LLC", formation="UNKNOWN",
             spacing_order="SAMPLE-SP-0001", pooling_order="SAMPLE-PO-0001",
             first_production=UNKNOWN, status="UNKNOWN",
             hbp_support="Unknown", citation="SRC-002"),
    ]

    curative = [
        Curative(issue_id="CUR-001", issue_type="Mortgage",
                 instrument_no="SAMPLE-0004",
                 description="Mortgage to First Prairie Bank; no release located.",
                 materiality="High", priority="1",
                 status="Open",
                 recommended_action="Obtain release or payoff; confirm lien status.",
                 citation="SRC-001 p.M-55/099"),
        Curative(issue_id="CUR-002", issue_type="Trust",
                 instrument_no="SAMPLE-0002",
                 description="Settler Family Trust authority/trustee succession not verified.",
                 materiality="Medium", priority="2", status="Open",
                 recommended_action="Obtain trust instrument and trustee certification.",
                 citation="SRC-001 p.142/318"),
        Curative(issue_id="CUR-003", issue_type="Gap",
                 instrument_no="SAMPLE-0001",
                 description="Unabstracted 1904-1948 ownership gap (cursory scope).",
                 materiality="Low", priority="3", status="Open",
                 recommended_action="Full abstract if a stand-up opinion is required.",
                 citation="SRC-001 p.142/318"),
    ]

    ownership = [
        OwnershipEntry(
            owner="Settler Family Trust", role="royalty",
            mineral_interest=Fraction(1, 1), lease_royalty=Fraction(3, 16),
            basis_language="3/16 lessor royalty per SAMPLE-0003; 100% mineral assumption.",
            citation="SRC-001 p.OGL-7/221"),
        OwnershipEntry(
            owner="Acme Operating LLC", role="working_interest",
            working_interest=Fraction(1, 1), burdens=Fraction(3, 16),
            basis_language="100% WI lessee under SAMPLE-0003 burdened by 3/16 royalty.",
            citation="SRC-001 p.OGL-7/221"),
        OwnershipEntry(
            owner="Unleased mineral owner (if any)", role="royalty",
            mineral_interest=UNKNOWN, lease_royalty=UNKNOWN,
            basis_language=UNKNOWN, citation=UNKNOWN),
    ]

    return TitleReport(
        config=config,
        sources=sources,
        instruments=instruments,
        abstractions=abstractions,
        chain_links=chain_links,
        wells=wells,
        curative=curative,
        ownership=ownership,
    )
