from __future__ import annotations

import sys
from pathlib import Path

import pytest
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from databossx.config import KernelConfig  # noqa: E402
from databossx.products.title.ledger import calculate_ownership  # noqa: E402
from databossx.products.title.render import safe_cell  # noqa: E402
from databossx.service import KernelService  # noqa: E402


def config_for(tmp_path: Path) -> KernelConfig:
    runtime = tmp_path / "runtime"
    return KernelConfig(
        repo_root=ROOT,
        runtime_root=runtime,
        database_path=runtime / "kernel.sqlite3",
        vault_root=runtime / "vault",
        projects_root=runtime / "projects",
        migrations_root=ROOT / "migrations",
    )


def reviewed_instrument(
    sequence: int,
    recording: str,
    grantor: str,
    grantee: str,
    numerator: int,
    denominator: int,
    asset_id: str,
    text_length: int,
    basis: str = "ABSOLUTE_ESTATE",
) -> dict:
    return {
        "sequence_no": sequence,
        "instrument_type": "Mineral Deed",
        "recording_reference": recording,
        "effective_date": f"202{sequence}-01-01",
        "grantor_name": grantor,
        "grantee_name": grantee,
        "conveyed_interest": {
            "numerator": numerator,
            "denominator": denominator,
        },
        "interest_basis": basis,
        "evidence_asset_version_id": asset_id,
        "evidence_char_start": 0,
        "evidence_char_end": text_length,
        "review_status": "REVIEWED",
    }


def test_branching_exact_ownership_preserves_all_owner_balances() -> None:
    opening = [{"owner_name": "Alpha", "interest_num": 1, "interest_den": 1}]
    evidence = "evidence"
    instruments = [
        {
            **reviewed_instrument(1, "BK1-P1", "Alpha", "Beta", 1, 2, evidence, 1),
            "conveyed_num": 1,
            "conveyed_den": 2,
        },
        {
            **reviewed_instrument(
                2, "BK1-P2", "Beta", "Gamma", 1, 2, evidence, 1, "OF_GRANTOR"
            ),
            "conveyed_num": 1,
            "conveyed_den": 2,
        },
    ]
    result = calculate_ownership(opening, instruments)
    assert str(result.ownership["Alpha"]) == "1/2"
    assert str(result.ownership["Beta"]) == "1/4"
    assert str(result.ownership["Gamma"]) == "1/4"
    assert sum(result.ownership.values()) == 1
    assert not result.blocking_defects
    assert all(entry.estate_total == 1 for entry in result.entries)


def test_duplicate_and_overconveyance_are_blocking_and_not_applied() -> None:
    opening = [{"owner_name": "Alpha", "interest_num": 1, "interest_den": 1}]
    base = {
        **reviewed_instrument(1, "DUP-1", "Alpha", "Beta", 3, 2, "asset", 1),
        "conveyed_num": 3,
        "conveyed_den": 2,
    }
    duplicate = {
        **reviewed_instrument(2, "DUP-1", "Alpha", "Gamma", 1, 2, "asset", 1),
        "conveyed_num": 1,
        "conveyed_den": 2,
    }
    result = calculate_ownership(opening, [base, duplicate])
    assert result.ownership == {"Alpha": 1}
    assert {defect.code for defect in result.blocking_defects} == {
        "OVER_CONVEYANCE",
        "DUPLICATE_INSTRUMENT",
    }
    assert safe_cell("=HYPERLINK(\"https://evil.example\")").startswith("'=")


def test_title_package_xlsx_pdf_hash_review_end_to_end(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    first_text = "Mineral Deed Alpha conveys an undivided 1/2 to Beta. Book 1 Page 1."
    second_text = "Mineral Deed Beta conveys 1/2 of grantor interest to Gamma. Book 1 Page 2."
    (source / "deed-1.txt").write_text(first_text, encoding="utf-8")
    (source / "deed-2.txt").write_text(second_text, encoding="utf-8")
    service = KernelService(config_for(tmp_path))
    project = service.create_project("Synthetic Title Case", source)
    service.ingest_project(project["id"])
    assets = {asset["rel_path"]: asset for asset in service.list_assets(project["id"])}
    payload = {
        "name": "Synthetic Branching Ownership",
        "legal_description": "SYNTHETIC Section 1, T1N, R1W",
        "gross_acres": {"numerator": 160, "denominator": 1},
        "opening_ownership": [
            {
                "owner_name": "Alpha",
                "interest": {"numerator": 1, "denominator": 1},
            }
        ],
        "instruments": [
            reviewed_instrument(
                1,
                "BK1-P1",
                "Alpha",
                "Beta",
                1,
                2,
                assets["deed-1.txt"]["id"],
                len(first_text),
            ),
            reviewed_instrument(
                2,
                "BK1-P2",
                "Beta",
                "Gamma",
                1,
                2,
                assets["deed-2.txt"]["id"],
                len(second_text),
                "OF_GRANTOR",
            ),
        ],
    }
    title_case = service.create_title_case(project["id"], payload)
    package = service.build_title_package(title_case["id"])
    assert (source / "deed-1.txt").read_text(encoding="utf-8") == first_text
    assert (source / "deed-2.txt").read_text(encoding="utf-8") == second_text
    assert package["run_status"] == "WAITING_HUMAN"
    assert package["blocking_defect_count"] == 0
    artifacts = {item["rel_path"]: item for item in package["artifacts"]}
    assert {
        "Title_Examiner_Packet.xlsx",
        "Draft_Abstract_Aid.pdf",
        "title_case_summary.json",
        "package_manifest.json",
    } <= artifacts.keys()

    _, workbook_path = service.artifact(
        artifacts["Title_Examiner_Packet.xlsx"]["id"]
    )
    with workbook_path.open("rb") as workbook_file:
        workbook = load_workbook(workbook_file, read_only=True, data_only=False)
        assert set(workbook.sheetnames) == {
            "Case Summary",
            "Runsheet",
            "Current Ownership",
            "Ownership Ledger",
            "Defects and Curative",
            "Evidence Index",
        }
        ownership_rows = list(
            workbook["Current Ownership"].iter_rows(values_only=True)
        )
        workbook.close()
    assert ("Alpha", "1/2", 1, 2, "160", "80") in ownership_rows
    assert ("Beta", "1/4", 1, 4, "160", "40") in ownership_rows
    assert ("Gamma", "1/4", 1, 4, "160", "40") in ownership_rows

    with pytest.raises(ValueError, match="does not match"):
        service.review_title_package(
            package["pipeline_run_id"], "0" * 64, "Qualified Examiner", "APPROVE"
        )
    approved = service.review_title_package(
        package["pipeline_run_id"],
        package["package_manifest_sha256"],
        "Qualified Examiner",
        "APPROVE",
        "Synthetic test approval only",
    )
    assert approved["review_status"] == "APPROVED"
    assert service.get_title_case(title_case["id"])["status"] == "APPROVED_FOR_EXPORT"
    rebuilt = service.build_title_package(title_case["id"])
    assert rebuilt["review_status"] == "AWAITING_REVIEW"
    assert rebuilt["approved_manifest_sha256"] is None
    assert service.health()["audit_chain_valid"] is True


def test_unreviewed_instrument_blocks_approval(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "notice.txt").write_text("Unresolved title evidence", encoding="utf-8")
    service = KernelService(config_for(tmp_path))
    project = service.create_project("Defect Case", source)
    service.ingest_project(project["id"])
    payload = {
        "name": "Needs Examiner",
        "legal_description": "SYNTHETIC TRACT",
        "gross_acres": {"numerator": 40, "denominator": 1},
        "opening_ownership": [
            {"owner_name": "Alpha", "interest": {"numerator": 1, "denominator": 1}}
        ],
        "instruments": [
            {
                "sequence_no": 1,
                "instrument_type": "Mineral Deed",
                "recording_reference": "UNKNOWN-1",
                "grantor_name": "Alpha",
                "grantee_name": "Beta",
                "conveyed_interest": {"numerator": 1, "denominator": 2},
                "interest_basis": "ABSOLUTE_ESTATE",
                "review_status": "NEEDS_REVIEW",
            }
        ],
    }
    title_case = service.create_title_case(project["id"], payload)
    package = service.build_title_package(title_case["id"])
    assert package["blocking_defect_count"] == 1
    assert package["defects"][0]["code"] == "INSTRUMENT_NEEDS_REVIEW"
    with pytest.raises(ValueError, match="Blocking defects"):
        service.review_title_package(
            package["pipeline_run_id"],
            package["package_manifest_sha256"],
            "Examiner",
            "APPROVE",
        )
