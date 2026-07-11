import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from openpyxl import load_workbook

FIELDS = [
    "Verified Address", "Status", "Last Affecting Doc No", "Last Doc Type",
    "Last Doc Date", "Source URL", "Notes", "Confidence%",
]


def create_staging_copy(path: str | Path, staging_dir: str | Path = "data/staging") -> Path:
    """Create a timestamped working copy; the supplied workbook remains untouched."""
    source = Path(path)
    destination_dir = Path(staging_dir)
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / (
        f"{source.stem}_staging_{datetime.now():%Y%m%d_%H%M%S_%f}{source.suffix}"
    )
    shutil.copy2(source, destination)
    return destination


def update_workbook(path: str | Path, sheet: str, owner: str, row_data: dict) -> bool:
    """Update a complete workbook atomically without dropping unrelated sheets."""
    path = Path(path)
    keep_vba = path.suffix.lower() == ".xlsm"
    workbook = load_workbook(path, keep_vba=keep_vba)
    if sheet not in workbook.sheetnames:
        raise KeyError(f"worksheet not found: {sheet}")
    worksheet = workbook[sheet]
    headers = {
        str(cell.value).strip(): cell.column
        for cell in worksheet[1]
        if cell.value is not None
    }
    required = {"Name (Owner)", *FIELDS}
    missing = required - headers.keys()
    if missing:
        raise ValueError(f"missing required columns in {sheet}: {sorted(missing)}")

    owner_key = owner.strip().upper()
    matching_rows = [
        row
        for row in range(2, worksheet.max_row + 1)
        if str(worksheet.cell(row, headers["Name (Owner)"]).value or "").strip().upper() == owner_key
    ]
    if not matching_rows:
        workbook.close()
        return False

    values = {
        "Verified Address": row_data.get("verified_address"),
        "Status": row_data.get("status"),
        "Last Affecting Doc No": row_data.get("doc_no"),
        "Last Doc Type": row_data.get("instrument"),
        "Last Doc Date": row_data.get("recording_date"),
        "Source URL": row_data.get("source_url"),
        "Notes": row_data.get("notes"),
        "Confidence%": int(round((row_data.get("confidence") or 0) * 100)),
    }
    for row in matching_rows:
        for field, value in values.items():
            worksheet.cell(row, headers[field], value)

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.stem}-", suffix=path.suffix, dir=path.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        workbook.save(temporary)
        workbook.close()
        load_workbook(temporary, read_only=True, keep_vba=keep_vba).close()
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return True
