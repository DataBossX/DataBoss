"""Synthetic-only tests for the fail-closed source-bound finish toolkit."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from source_bound_finish.access import probe_access
from source_bound_finish.cli import main
from source_bound_finish.dates import check_date_roles, check_date_table
from source_bound_finish.format_qa import check_columns, check_format
from source_bound_finish.hashing import sha256_file
from source_bound_finish.identity import (
    StableKeyError,
    find_duplicate_keys,
    reconcile_populations,
    stable_key,
)
from source_bound_finish.ledger import build_ledger
from source_bound_finish.package import verify_package
from source_bound_finish.pdf_census import count_pdf_pages
from source_bound_finish.purity import check_purity
from source_bound_finish.synthetic import clean_row, write_minimal_pdf
from source_bound_finish.tournament import run_tournament


def test_pdf_census_agrees_on_physical_pages(tmp_path: Path):
    pdf = write_minimal_pdf(tmp_path / "three.pdf", pages=3)
    census = count_pdf_pages(pdf)
    assert census.counted_pages == 3
    assert census.declared_pages == 3
    assert census.agree is True
    assert census.sha256 == sha256_file(pdf)


def test_pdf_census_does_not_guess_missing_file(tmp_path: Path):
    census = count_pdf_pages(tmp_path / "absent.pdf")
    assert census.counted_pages is None
    assert census.agree is False
    assert "MISSING_SOURCE" in census.issues


def test_ledger_does_not_equate_pages_with_rows(tmp_path: Path):
    pdf = write_minimal_pdf(tmp_path / "packet.pdf", pages=4)
    ledger = build_ledger(
        [pdf],
        {
            "packet.pdf": [
                "MATERIAL_START",
                "CONTINUATION",
                "OPERATIVE_EXHIBIT",
                "SRP_CURRENTNESS_SUPPORT",
            ]
        },
    )
    assert ledger.physical_page_count == 4
    assert ledger.material_start_count == 1
    assert [page.client_row for page in ledger.pages] == [True, False, False, False]


def test_unresolved_pages_are_not_promoted(tmp_path: Path):
    pdf = write_minimal_pdf(tmp_path / "open.pdf", pages=2)
    ledger = build_ledger([pdf])
    assert {page.disposition for page in ledger.pages} == {"UNRESOLVED"}
    assert ledger.material_start_count == 0


def test_stable_key_keeps_missing_halves_blank():
    key = stable_key(doc_no="1001", book_page=None)
    assert key.doc_no == "1001"
    assert key.book_page == ""
    assert key.key == "1001|"
    with pytest.raises(StableKeyError):
        stable_key(doc_no="not-a-doc")


def test_duplicate_physical_starts_are_reported():
    keys = [
        stable_key("1999-00011", None, "12"),
        stable_key("1999-00011", None, "12"),
        stable_key("1999-00012", None, "13"),
    ]
    assert find_duplicate_keys(keys) == ["1999-00011||p12"]


def test_populations_are_not_added_arithmetically():
    existing = ["A", "B", "C"]
    candidates = ["C", "D"]
    result = reconcile_populations(existing, candidates)
    assert result["existing"] == 3
    assert result["candidates"] == 2
    assert result["overlap"] == 1
    assert result["union"] == 4
    assert result["arithmetic_sum"] == 5
    assert result["arithmetic_sum_valid"] is False


def test_purity_rejects_process_text_and_page_ranges():
    rows = [
        clean_row(Comments="HOLD"),
        clean_row(Page="12-15", Grantor="John Doe et al"),
        clean_row(Comments="missing image"),
    ]
    findings = check_purity(rows)
    codes = {(item.row, item.code) for item in findings}
    assert (1, "FORBIDDEN_COMMENT") in codes
    assert (2, "PAGE_RANGE") in codes
    assert (2, "GENERIC_PARTY") in codes
    assert not any(item.row == 3 and item.field == "Comments" for item in findings)


def test_date_roles_do_not_bleed_or_use_prep_as_currentness():
    bleed = check_date_roles(
        {"execution": "1/1/1980", "copied_from": "execution", "copied_into": "recording"}
    )
    assert any(item.code == "ROLE_BLEED" for item in bleed)
    currentness = check_date_table(
        [{"preparation": "9/22/2026", "search_through": "9/22/2026"}]
    )
    assert any(item.code == "PREP_IS_NOT_CURRENTNESS" for item in currentness)
    filed_only = check_date_roles({"filed": "7/22/2026"})
    assert filed_only == []


def test_reduced_federal_schema_rejects_reintroduced_columns():
    findings = check_columns(
        [
            "Document Type",
            "Grantor",
            "Grantee",
            "Page",
            "Date of Doc",
            "Rec Date",
            "Legal Description",
            "File No",
            "Part",
        ],
        "reduced_federal",
    )
    codes = {item.code for item in findings}
    assert "REDUCED_SCHEMA_REGRESSION" in codes
    row_findings = check_format([{"Page": "1", "Part": "3"}], profile="reduced_federal")
    assert any(item.code == "REDUCED_SCHEMA_REGRESSION" for item in row_findings)


def test_package_membership_crc_and_hashes(tmp_path: Path):
    member = tmp_path / "report.txt"
    member.write_text("synthetic-client-face\n", encoding="utf-8")
    archive = tmp_path / "pkg.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.write(member, arcname="report.txt")
    ok = verify_package(
        archive,
        expected_members=["report.txt"],
        expected_sha256=sha256_file(archive),
        expected_member_sha={"report.txt": sha256_file(member)},
    )
    assert ok["pass"] is True
    assert ok["crc_pass"] is True
    bad = verify_package(archive, expected_members=["other.txt"])
    assert bad["pass"] is False


def test_access_is_blocked_without_a_source_root(tmp_path: Path):
    receipt = probe_access(tmp_path / "missing")
    assert receipt.status == "BLOCKED"
    assert receipt.report_writes == 0
    assert receipt.writable_client_targets is False
    assert "SOURCE_ROOT_UNAVAILABLE" in receipt.blockers


def test_access_counts_local_files_but_still_does_not_write(tmp_path: Path):
    (tmp_path / "a.pdf").write_bytes(b"%PDF-1.1\n")
    receipt = probe_access(tmp_path)
    assert receipt.status == "LOCAL_SOURCES_PRESENT"
    assert receipt.source_file_count == 1
    assert receipt.report_writes == 0


def _complete_packet(tmp_path: Path) -> dict:
    pdf = write_minimal_pdf(tmp_path / "src.pdf", pages=1)
    member = tmp_path / "face.txt"
    member.write_text("ok\n", encoding="utf-8")
    archive = tmp_path / "pkg.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.write(member, arcname="face.txt")
    return {
        "source_root": str(tmp_path),
        "source_paths": [str(pdf)],
        "dispositions_by_file": {"src.pdf": ["MATERIAL_START"]},
        "rows": [clean_row()],
        "columns": [
            "Document Type",
            "Grantor",
            "Grantee",
            "Book",
            "Page",
            "Doc No",
            "Date of Doc",
            "Rec Date",
            "Legal Description",
        ],
        "profile": "county",
        "stable_keys": [stable_key("1001", "12-8").__dict__],
        "date_rows": [{"execution": "1/15/1980", "recording": "1/20/1980"}],
        "native_reopen": {"reopened": True, "every_page_inspected": True},
        "package": {
            "zip_path": str(archive),
            "expected_members": ["face.txt"],
            "expected_sha256": sha256_file(archive),
        },
    }


def test_tournament_blocks_without_sources():
    result = run_tournament({})
    assert result.complete is False
    assert result.consecutive_complete == 0
    statuses = {item.name: item.status for item in result.dimensions}
    assert statuses["A_SOURCE_COMPLETENESS"] == "BLOCKED"
    assert statuses["D_NATIVE_EVERY_PAGE"] == "BLOCKED"
    assert statuses["E_BYTE_PACKAGE"] == "BLOCKED"


def test_tournament_complete_and_cached_pass_does_not_count(tmp_path: Path):
    packet = _complete_packet(tmp_path)
    first = run_tournament(packet, cycle=1)
    assert first.complete is True
    assert first.consecutive_complete == 1
    cached = run_tournament(
        packet,
        previous_evidence_sha=first.evidence_sha256,
        consecutive_complete=first.consecutive_complete,
        cycle=2,
    )
    assert cached.cached is True
    assert cached.complete is False
    assert cached.consecutive_complete == 1


def test_tournament_correction_resets_clean_count(tmp_path: Path):
    packet = _complete_packet(tmp_path)
    first = run_tournament(packet, cycle=1)
    broken = dict(packet)
    broken["rows"] = [clean_row(Comments="UNKNOWN")]
    reset = run_tournament(
        broken,
        previous_evidence_sha=first.evidence_sha256,
        consecutive_complete=first.consecutive_complete,
        cycle=2,
    )
    assert reset.complete is False
    assert reset.consecutive_complete == 0


def test_five_blocked_cycles_cannot_cure_missing_source():
    sha = None
    consecutive = 0
    for cycle in range(1, 6):
        result = run_tournament(
            {},
            previous_evidence_sha=sha,
            consecutive_complete=consecutive,
            cycle=cycle,
        )
        sha = result.evidence_sha256
        consecutive = result.consecutive_complete
        assert result.complete is False
    assert consecutive == 0


def test_cli_access_exit_code(tmp_path: Path, capsys):
    assert main(["access", "--root", str(tmp_path / "nope")]) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["report_writes"] == 0
    assert payload["status"] == "BLOCKED"
