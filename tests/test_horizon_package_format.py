"""Section 13/15 format and 2026-09-22 exact-N membership."""

from __future__ import annotations

import json
from pathlib import Path

import openpyxl
import pytest

from horizon.image_account import WORK_DATE, WORK_DATE_TOKEN
from horizon.package_format import (
    PackageFormatError,
    apply_letter_format,
    assemble_exact_package,
    contract_for,
    dated_zip_name,
    main,
    portfolio_status,
)
from horizon.tournament_loop import run_tournament


PENTERRA_HEADERS = [
    "Document Type",
    "Grantor",
    "Grantee",
    "Doc No",
    "Book-Page",
    "Date of Doc",
    "Rec Date",
    "Legal Description",
    "Comments",
]
MINIMAL_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de"
    "0000000c49444154789c636000020000050001d5c8c94e0000000049454e44ae426082"
)
ONE_PAGE_PDF = (
    b"%PDF-1.1\n"
    b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n"
    b"2 0 obj<< /Type /Pages /Count 1 /Kids [3 0 R] >>endobj\n"
    b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>endobj\n"
    b"trailer<< /Root 1 0 R >>\n"
)


def _penterra_workbook(path: Path) -> None:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Index"
    for label in (
        "Index County",
        "Lands",
        "Date",
        "Starting Date",
        "Date Posted Thru",
        "Indexed By",
        "Project",
    ):
        sheet.append([label, "SYNTH"])
    sheet.append(PENTERRA_HEADERS)
    sheet.append(
        [
            "Mineral Deed",
            "SYNTH ALPHA LLC",
            "SYNTH BETA LLC",
            "2026-09901",
            "",
            "1/1/2026",
            "1/2/2026",
            "SYNTH TRACT 15-45N-76W",
            "",
        ]
    )
    workbook.save(path)
    workbook.close()


def test_letter_format_matches_section_13_and_15(tmp_path: Path) -> None:
    source = tmp_path / "source.xlsx"
    isolated = tmp_path / "section15-letter.xlsx"
    _penterra_workbook(source)
    receipt = apply_letter_format(source, isolated)
    assert receipt.work_date == WORK_DATE.isoformat()
    assert receipt.technical_pass
    assert receipt.packages_complete is False
    workbook = openpyxl.load_workbook(isolated)
    sheet = workbook["Index"]
    assert sheet.page_setup.orientation == "landscape"
    assert sheet.page_setup.paperSize == sheet.PAPERSIZE_LETTER
    assert str(sheet.print_title_rows).replace("$", "") in {"1:8", "1:$8"}
    workbook.close()


def test_exact5_zip_is_dated_20260922(tmp_path: Path) -> None:
    members = []
    for name in (
        "45N-76W-13_Campbell_Co_Penterra_Abstract_Index.xlsx",
        "WYW-000001 Campbell Co. Penterra Abstract Index.xlsx",
        "Abstract_Checklist_13-45N-76W.xlsx",
        "Section13_Title_Certification.docx",
        "Accuracy_and_Completeness_Report.xlsx",
    ):
        path = tmp_path / name
        path.write_bytes(b"synth-member")
        members.append(path)
    dest = tmp_path / dated_zip_name(contract_for("P13"))
    receipt = assemble_exact_package(
        package_id="P13",
        members=members,
        output_zip=dest,
    )
    assert receipt.work_date == WORK_DATE.isoformat()
    assert receipt.exact_n == 5
    assert receipt.zip_name.endswith(f"DATED_{WORK_DATE_TOKEN}_EXACT5.zip")
    assert receipt.packages_complete is False
    assert dest.is_file()


def test_frozen_p15_cannot_be_rebuilt(tmp_path: Path) -> None:
    member = tmp_path / "member.xlsx"
    member.write_bytes(b"synth")
    with pytest.raises(PackageFormatError, match="format_donor"):
        assemble_exact_package(
            package_id="P15",
            members=[member] * 6,
            output_zip=tmp_path
            / f"P15_45N-76W-15__SUPERSEDING_TURNIN_DATED_{WORK_DATE_TOKEN}_EXACT6.zip",
        )


def test_portfolio_keeps_unknown_counts() -> None:
    payload = portfolio_status()
    assert payload["work_date"] == WORK_DATE.isoformat()
    assert len(payload["packages"]) == 12
    assert all(item["status"] == "UNKNOWN" for item in payload["packages"])
    assert all(item["image_count"] == "UNKNOWN" for item in payload["packages"])
    assert all(item["packages_complete"] is False for item in payload["packages"])


def test_tournament_accounts_every_image_and_formats_letter(tmp_path: Path) -> None:
    bind = tmp_path / "faces"
    bind.mkdir()
    (bind / "scan.png").write_bytes(MINIMAL_PNG)
    (bind / "face.pdf").write_bytes(ONE_PAGE_PDF)
    source = tmp_path / "source.xlsx"
    _penterra_workbook(source)
    receipt = run_tournament(
        bind_dir=bind,
        packet_id="SYNTH-TOUR-001",
        workbook=source,
        letter_dir=tmp_path / "letters",
        max_loops=3,
    )
    assert receipt.work_date == WORK_DATE.isoformat()
    assert receipt.image_count == 2
    assert receipt.every_image_accounted is True
    assert receipt.passes[0].format_pass is True
    assert receipt.packages_complete is False
    assert receipt.portfolio["work_date"] == WORK_DATE.isoformat()


def test_package_format_portfolio_cli(tmp_path: Path) -> None:
    output = tmp_path / "portfolio.json"
    assert main(["--portfolio", "--receipt", str(output)]) == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["work_date"] == "2026-09-22"
