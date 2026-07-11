from pathlib import Path

from openpyxl import Workbook, load_workbook

from automation.writer import create_staging_copy, update_workbook


HEADERS = [
    "Name (Owner)",
    "Verified Address",
    "Status",
    "Last Affecting Doc No",
    "Last Doc Type",
    "Last Doc Date",
    "Source URL",
    "Notes",
    "Confidence%",
]


def make_workbook(path: Path) -> None:
    workbook = Workbook()
    target = workbook.active
    target.title = "DSU NOTICE LIST"
    target.append(HEADERS)
    target.append(["Ella Pearl Kirk"])
    supporting = workbook.create_sheet("Supporting Evidence")
    supporting["A1"] = "=1+1"
    supporting["B2"] = "must survive"
    workbook.save(path)


def test_writer_preserves_source_and_unrelated_sheets(tmp_path):
    source = tmp_path / "source.xlsx"
    make_workbook(source)
    source_before = source.read_bytes()
    staging = create_staging_copy(source, tmp_path / "staging")

    changed = update_workbook(
        staging,
        "DSU NOTICE LIST",
        "ella pearl kirk",
        {
            "status": "Verified",
            "doc_no": "2026-123",
            "confidence": 0.97,
        },
    )

    assert changed is True
    assert source.read_bytes() == source_before
    workbook = load_workbook(staging, data_only=False)
    assert workbook.sheetnames == ["DSU NOTICE LIST", "Supporting Evidence"]
    assert workbook["Supporting Evidence"]["A1"].value == "=1+1"
    assert workbook["Supporting Evidence"]["B2"].value == "must survive"
    assert workbook["DSU NOTICE LIST"]["C2"].value == "Verified"
    assert workbook["DSU NOTICE LIST"]["I2"].value == 97
    workbook.close()


def test_writer_does_not_save_when_owner_is_missing(tmp_path):
    workbook_path = tmp_path / "staging.xlsx"
    make_workbook(workbook_path)
    before = workbook_path.read_bytes()
    assert update_workbook(workbook_path, "DSU NOTICE LIST", "Unknown Owner", {}) is False
    assert workbook_path.read_bytes() == before
