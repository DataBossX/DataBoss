import pandas as pd

FIELDS = [
    "Verified Address",
    "Status",
    "Last Affecting Doc No",
    "Last Doc Type",
    "Last Doc Date",
    "Source URL",
    "Notes",
    "Confidence%",
]


def update_workbook(path: str, sheet: str, owner: str, row_data: dict):
    df = pd.read_excel(path, sheet_name=sheet)
    mask = df["Name (Owner)"].astype(str).str.strip().str.upper() == owner.strip().upper()
    if not mask.any():
        return False
    df.loc[mask, "Verified Address"] = row_data.get("verified_address")
    df.loc[mask, "Status"] = row_data.get("status")
    df.loc[mask, "Last Affecting Doc No"] = row_data.get("doc_no")
    df.loc[mask, "Last Doc Type"] = row_data.get("instrument")
    df.loc[mask, "Last Doc Date"] = row_data.get("recording_date")
    df.loc[mask, "Source URL"] = row_data.get("source_url")
    df.loc[mask, "Notes"] = row_data.get("notes")
    df.loc[mask, "Confidence%"] = int(round((row_data.get("confidence") or 0) * 100))
    with pd.ExcelWriter(path, engine="openpyxl", mode="w") as w:
        df.to_excel(w, index=False, sheet_name=sheet)
    return True
