#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for Section 7 Title Engine, Google Drive Sync, Federal Lease Auditor,
and Multi-Pass Refiner.
"""

from __future__ import annotations

import shutil
import tempfile
from fractions import Fraction
from pathlib import Path

import pytest

from automation.gdrive_sync_engine import (
    calculate_sha256,
    compare_trees,
    export_comparison_manifest,
    initialize_section_folders,
    inventory_tree_parallel,
    save_chat_and_notes_to_drive,
    sync_files_parallel,
)
from horizon.conveyance_parser import (
    calculate_net_mineral_acres,
    format_nma_display,
    parse_conveyance_text,
    parse_fraction_word,
)
from horizon.federal_lease_auditor import (
    audit_federal_lease_pdf,
    generate_federal_lease_summary_table,
)
from horizon.multipass_refiner import (
    calculate_quality_score,
    run_multipass_refinement,
)
from horizon.section7_engine import (
    extract_core_name,
    normalize_party_name,
    resolve_grantor_in_ledger,
    run_section7_title_chain,
)
from horizon.section7_report_generator import (
    create_docx_title_report,
    create_excel_title_workbook,
    create_markdown_title_report,
)
from section7_master_pipeline import get_demo_section7_corpus, run_master_pipeline


# ---------------------------------------------------------------------------
# 1. Conveyance Parser Tests
# ---------------------------------------------------------------------------
def test_parse_conveyance_arti():
    text = "Grantor conveys all of our right, title and interest in and to Section 7-12N-24W."
    details = parse_conveyance_text(text, grantor_prior_interest=Fraction(1, 2))
    assert details.is_arti is True
    assert details.parsed_fraction == Fraction(1, 2)
    assert "ARTI" in details.conveyed_interest_display


def test_parse_conveyance_undivided_fraction():
    text = "Conveys an undivided 1/4 mineral interest in and to all oil and gas."
    details = parse_conveyance_text(text, grantor_prior_interest=Fraction(1, 1))
    assert details.is_undivided is True
    assert details.parsed_fraction == Fraction(1, 4)
    assert details.retained_interest_display == "3/4"


def test_parse_conveyance_fraction_of_grantor():
    text = "Conveys 1/2 of Grantor's remaining interest in Section 7."
    details = parse_conveyance_text(text, grantor_prior_interest=Fraction(1, 2))
    assert details.is_fraction_of_grantor is True
    assert details.parsed_fraction == Fraction(1, 2)
    assert "1/2 of Grantor" in details.conveyed_interest_display
    assert details.retained_interest_display == "1/4"


def test_parse_conveyance_reservations_and_depths():
    text = (
        "Conveys an undivided 1/2 interest, reserving an undivided 1/4 mineral interest "
        "unto Grantor, limited to depths from the surface down to the base of the Morrow formation, "
        "and subject to a 3/16th royalty rate."
    )
    details = parse_conveyance_text(text)
    assert details.has_reservation is True
    assert details.is_depth_severed is True
    assert "Morrow" in details.depth_clause
    assert details.royalty_stated == "3/16"


def test_parse_fraction_word():
    assert parse_fraction_word("half") == Fraction(1, 2)
    assert parse_fraction_word("one-fourth") == Fraction(1, 4)
    assert parse_fraction_word("1/8") == Fraction(1, 8)
    assert parse_fraction_word("100%") == Fraction(1, 1)


# ---------------------------------------------------------------------------
# 2. Entity Normalization & Section 7 Chaining Engine Tests
# ---------------------------------------------------------------------------
def test_extract_core_name():
    assert extract_core_name("William H. Harrison and Sarah Harrison, his wife") == "William H. Harrison and Sarah Harrison"
    assert extract_core_name("Estate of William H. Harrison, Deceased") == "William H. Harrison"
    assert extract_core_name("Harrison Family Mineral Trust (Robert Harrison, Trustee)") == "Harrison Family Mineral Trust"
    assert extract_core_name("Arthur M. Reynolds, a single person") == "Arthur M. Reynolds"
    assert extract_core_name("Blackwood Royalty Partners LLC") == "Blackwood Royalty Partners"


def test_resolve_grantor_in_ledger():
    ledger = {
        "William H. Harrison": Fraction(1, 1),
        "Arthur M. Reynolds": Fraction(1, 2),
    }
    k1, b1 = resolve_grantor_in_ledger("William H. Harrison and Sarah Harrison, his wife", ledger)
    assert k1 == "William H. Harrison"
    assert b1 == Fraction(1, 1)

    k2, b2 = resolve_grantor_in_ledger("Estate of William H. Harrison, Deceased", ledger)
    assert k2 == "William H. Harrison"
    assert b2 == Fraction(1, 1)


def test_run_section7_title_chain_balance():
    corpus = get_demo_section7_corpus()
    report = run_section7_title_chain(corpus, gross_tract_acres=640.0)
    assert report.is_balanced is True
    assert report.total_ownership_decimal == 1.0
    assert report.total_net_mineral_acres == 640.0
    assert len(report.current_mineral_owners) == 3

    # Check top owner has 320 acres
    top_owner = report.current_mineral_owners[0]
    assert "Harrison" in top_owner.owner_name
    assert top_owner.net_mineral_acres == 320.0
    assert top_owner.fraction_display == "1/2"


def test_chain_gap_detection():
    gap_corpus = [
        {
            "entry_no": 1,
            "instrument_date": "1950-01-01",
            "recorded_date": "1950-01-10",
            "doc_type": "Mineral Deed",
            "grantor": "Stranger With No Record Title",
            "grantee": "Acme Minerals LLC",
            "book": "50",
            "page": "100",
            "conveyance_text": "Conveys an undivided 1/2 interest in Section 7.",
            "gross_acres": 640.0,
        }
    ]
    report = run_section7_title_chain(gap_corpus, gross_tract_acres=640.0)
    assert len(report.assumptions_ledger) > 0
    assert len(report.curative_requirements) > 0
    assert "Chain Gap" in report.curative_requirements[0]["issue"]


# ---------------------------------------------------------------------------
# 3. Federal Lease Auditor Tests
# ---------------------------------------------------------------------------
def test_federal_lease_auditor_text_package(tmp_path):
    fed_file = tmp_path / "BLM_OKNM_999999_Serial.txt"
    fed_file.write_text(
        "--- PAGE 1 ---\nSERIAL REGISTER PAGE\nCASE TYPE: 221101 O&G LEASE\nSERIAL NR: OKNM 999999\nImage 1 of 3\n"
        "--- PAGE 2 ---\nASSIGNMENT OF RECORD TITLE\nImage 2 of 3\n"
        "--- PAGE 3 ---\nBLM APPROVAL DECISION\nImage 3 of 3\n",
        encoding="utf-8",
    )
    audit = audit_federal_lease_pdf(fed_file, known_serial="OKNM 999999")
    assert audit.serial_number == "OKNM 999999"
    assert audit.total_pages == 3
    assert audit.total_images == 3
    assert audit.is_continuity_intact is True
    assert len(audit.documents) >= 1

    summary_rows = generate_federal_lease_summary_table([audit])
    assert len(summary_rows) == 1
    assert summary_rows[0]["continuity_status"] == "VALID (No Gaps)"


def test_federal_lease_missing_image_gap(tmp_path):
    fed_file = tmp_path / "BLM_GAP_TEST.txt"
    fed_file.write_text(
        "--- PAGE 1 ---\nSERIAL REGISTER PAGE\nImage 1 of 4\n"
        "--- PAGE 2 ---\nASSIGNMENT\nImage 2 of 4\n"
        "--- PAGE 3 ---\nDECISION\nImage 4 of 4\n",  # Notice Image 3 is skipped
        encoding="utf-8",
    )
    audit = audit_federal_lease_pdf(fed_file, known_serial="OKNM 888888")
    assert audit.is_continuity_intact is False
    assert 3 in audit.missing_image_numbers
    assert len(audit.curative_issues) > 0


# ---------------------------------------------------------------------------
# 4. Multi-Pass Refinement Tests
# ---------------------------------------------------------------------------
def test_multipass_refiner_convergence():
    corpus = get_demo_section7_corpus()
    session = run_multipass_refinement(
        raw_instruments=corpus,
        gross_tract_acres=640.0,
        section_legal="Section 7-12N-24W, Roger Mills County, OK",
        max_passes=3,
    )
    assert session.converged is True
    assert session.final_score >= 90.0
    assert len(session.pass_history) >= 1
    assert session.final_report.is_balanced is True


# ---------------------------------------------------------------------------
# 5. Google Drive Sync & Comparison Tests
# ---------------------------------------------------------------------------
def test_gdrive_sync_and_comparison(tmp_path):
    pc_root = tmp_path / "PC"
    gd_root = tmp_path / "GDrive"

    pc_folders = initialize_section_folders(pc_root, "Section 7")
    gd_folders = initialize_section_folders(gd_root, "Section 7")

    assert pc_folders["1_Source_Documents"].exists()
    assert gd_folders["5_Final_Reports_Ready_To_Turn_In"].exists()

    # Create dummy report on PC
    sample_doc = pc_folders["5_Final_Reports_Ready_To_Turn_In"] / "Test_Report.txt"
    sample_doc.write_text("Final Deliverable Content", encoding="utf-8")

    # Sync to Drive
    res = sync_files_parallel(pc_root / "Section 7", gd_root / "Section 7")
    assert res["synced_count"] >= 1

    # Compare
    manifest = compare_trees(pc_root / "Section 7", gd_root / "Section 7", section_name="Section 7")
    assert manifest.total_matched >= 1
    assert manifest.total_drift == 0

    # Export comparison reports
    out_dir = tmp_path / "audit_out"
    exported = export_comparison_manifest(manifest, out_dir)
    assert Path(exported["json"]).exists()
    assert Path(exported["csv"]).exists()
    assert Path(exported["markdown"]).exists()


def test_save_chat_notes_to_drive(tmp_path):
    pc_root = tmp_path / "PC"
    gd_root = tmp_path / "GDrive"

    notes = "# Title Examiner Chat Log\n\nVerified Section 7 ownership."
    res = save_chat_and_notes_to_drive(notes, pc_root, gd_root, section_name="Section 7")
    assert Path(res["pc_path"]).exists()
    assert Path(res["gdrive_path"]).exists()


# ---------------------------------------------------------------------------
# 6. Report Generation & Master Pipeline E2E Test
# ---------------------------------------------------------------------------
def test_report_generators(tmp_path):
    corpus = get_demo_section7_corpus()
    report = run_section7_title_chain(corpus, gross_tract_acres=640.0)

    xlsx_path = tmp_path / "Section_7_Test_Report.xlsx"
    md_path = tmp_path / "Section_7_Test_Report.md"
    docx_path = tmp_path / "Section_7_Test_Report.docx"

    create_excel_title_workbook(report, output_path=xlsx_path)
    create_markdown_title_report(report, output_path=md_path)
    create_docx_title_report(report, output_path=docx_path)

    assert xlsx_path.exists() and xlsx_path.stat().st_size > 5000
    assert md_path.exists() and md_path.stat().st_size > 1000
    assert docx_path.exists() and docx_path.stat().st_size > 5000


def test_master_pipeline_e2e(tmp_path):
    pc_root = tmp_path / "PC_Dir"
    gd_root = tmp_path / "GDrive_Dir"

    results = run_master_pipeline(
        pc_root=pc_root,
        gdrive_root=gd_root,
        section_name="Section 7-12N-24W",
        gross_acres=640.0,
        max_passes=2,
        workers=4,
    )

    assert results["title_report"].is_balanced is True
    assert Path(results["excel_report"]).exists()
    assert Path(results["docx_report"]).exists()
    assert Path(results["markdown_report"]).exists()
    assert results["manifest"].total_matched >= 5
