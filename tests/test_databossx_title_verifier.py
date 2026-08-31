from __future__ import annotations

from fractions import Fraction
from databossx.title_verifier import (
    LegalDescriptionSTR,
    TitleDocumentFact,
    TitleVerifier,
    normalize_party_name,
    parse_legal_description_str,
    parse_recording_references,
    parse_standard_date,
)


def test_normalize_party_name():
    assert normalize_party_name("Acme Minerals, LLC") == "ACME MINERALS"
    assert normalize_party_name("John Doe et al.") == "JOHN DOE"
    assert normalize_party_name("Big Basin Resources, Inc.") == "BIG BASIN RESOURCES"


def test_parse_legal_description_str():
    parsed = parse_legal_description_str("NE/4 of Section 31, Township 12N, Range 24W")
    assert parsed is not None
    assert parsed.section == "31"
    assert parsed.township == "12"
    assert parsed.township_dir == "N"
    assert parsed.range == "24"
    assert parsed.range_dir == "W"
    assert parsed.canonical_str == "NE/4 Sec 31-12N-24W"


def test_parse_recording_references():
    instr, book, page = parse_recording_references("Book 1234, Page 567; Reception #2023000987")
    assert book == "1234"
    assert page == "567"
    assert instr == "2023000987"


def test_parse_standard_date():
    assert parse_standard_date("2023-04-15") == "2023-04-15"
    assert parse_standard_date("04/15/2023") == "2023-04-15"
    assert parse_standard_date("April 15, 2023") == "2023-04-15"
    assert parse_standard_date("invalid-date") is None


def test_title_verifier_single_doc_validation():
    verifier = TitleVerifier()

    valid_doc = TitleDocumentFact(
        doc_id="DOC-001",
        doc_type="Warranty Deed",
        grantor="John Doe",
        grantee="Acme Minerals LLC",
        execution_date="2020-01-15",
        recording_date="2020-01-20",
        instrument_number="2020-1001",
        legal_description_raw="NE4 Sec 31-12N-24W",
        gross_acres=Fraction(160, 1),
        conveyed_interest=Fraction(1, 2),
        net_mineral_acres=Fraction(80, 1),
        source_citation="D:/DataBoss/source_docs/01_deed.pdf",
    )

    findings = verifier.verify_document_fact(valid_doc)
    assert len(findings) == 0, f"Expected 0 findings on valid doc, got: {findings}"

    # Now test with inverted chronology and math mismatch
    invalid_doc = TitleDocumentFact(
        doc_id="DOC-002",
        doc_type="Mineral Deed",
        grantor="Acme Minerals LLC",
        grantee="Zenith Oil Co",
        execution_date="2022-05-10",
        recording_date="2021-05-10",  # Inverted date!
        legal_description_raw="NE4 Sec 31-12N-24W",
        gross_acres=Fraction(160, 1),
        conveyed_interest=Fraction(1, 4),
        net_mineral_acres=Fraction(99, 1),  # Expected 40!
        source_citation="",  # Missing citation!
    )

    findings2 = verifier.verify_document_fact(invalid_doc)
    check_types = {f.check_type for f in findings2}
    assert "PROVENANCE_MISSING" in check_types
    assert "CHRONOLOGY_INVERTED" in check_types
    assert "NMA_CALCULATION_MISMATCH" in check_types
    assert "RECORDING_REF_MISSING" in check_types


def test_title_chain_audit_continuity():
    verifier = TitleVerifier()

    doc1 = TitleDocumentFact(
        doc_id="DOC-001",
        doc_type="Patent",
        grantor="USA",
        grantee="Original Settler",
        recording_date="1920-01-01",
        instrument_number="1920-01",
        legal_description_raw="Sec 31-12N-24W",
        source_citation="vault/01.pdf",
    )
    doc2 = TitleDocumentFact(
        doc_id="DOC-002",
        doc_type="Warranty Deed",
        grantor="Original Settler",
        grantee="First Producer LLC",
        recording_date="1950-06-01",
        instrument_number="1950-02",
        legal_description_raw="Sec 31-12N-24W",
        source_citation="vault/02.pdf",
    )
    doc3 = TitleDocumentFact(
        doc_id="DOC-003",
        doc_type="Mineral Deed",
        grantor="Unknown Third Party",  # Continuity break!
        grantee="Final Buyer Inc",
        recording_date="1980-08-01",
        instrument_number="1980-03",
        legal_description_raw="Sec 31-12N-24W",
        source_citation="vault/03.pdf",
    )

    result = verifier.audit_title_chain([doc1, doc2, doc3])
    assert result.documents_verified == 3
    assert len(result.chain_breaks) == 1
    assert result.chain_breaks[0]["grantor"] == "Unknown Third Party"
    assert not result.is_deliverable_ready
