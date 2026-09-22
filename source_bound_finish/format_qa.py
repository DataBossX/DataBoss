"""Format and schema checks. Format copy is allowed; fact copy is not."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .constants import (
    COUNTY_COLUMNS,
    FEDERAL_COLUMNS,
    FORBIDDEN_PROCESS_COLUMNS,
    REDUCED_FEDERAL_COLUMNS,
)

SCHEMA_PROFILES = {
    "county": COUNTY_COLUMNS,
    "federal": FEDERAL_COLUMNS,
    "reduced_federal": REDUCED_FEDERAL_COLUMNS,
}


@dataclass(frozen=True)
class FormatFinding:
    field: str
    code: str
    message: str
    row: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def check_columns(columns: list[str], profile: str) -> list[FormatFinding]:
    if profile not in SCHEMA_PROFILES:
        raise ValueError(f"unknown schema profile: {profile}")
    expected = list(SCHEMA_PROFILES[profile])
    findings: list[FormatFinding] = []
    names = [name.strip() for name in columns]
    for name in names:
        if name.lower() in FORBIDDEN_PROCESS_COLUMNS:
            findings.append(
                FormatFinding(name, "PROCESS_COLUMN", "process column is not a client field")
            )
    if profile == "reduced_federal":
        for forbidden in ("File No", "Comments", "Part"):
            if forbidden in names:
                findings.append(
                    FormatFinding(
                        forbidden,
                        "REDUCED_SCHEMA_REGRESSION",
                        f"{forbidden} is not part of the reduced federal schema",
                    )
                )
    for name in (
        "Document Type",
        "Grantor",
        "Grantee",
        "Page",
        "Legal Description",
    ):
        if name not in names:
            findings.append(FormatFinding(name, "MISSING_COLUMN", f"required column {name}"))
    if names[: len(expected)] != expected and set(names) >= set(expected):
        findings.append(
            FormatFinding("columns", "ORDER", "column order differs from profile")
        )
    return findings


def check_format(
    rows: list[dict],
    columns: list[str] | None = None,
    profile: str = "county",
) -> list[FormatFinding]:
    findings: list[FormatFinding] = []
    if columns is not None:
        findings.extend(check_columns(columns, profile))
    for index, row in enumerate(rows, start=1):
        page = str(row.get("Page") or "").strip()
        if "-" in page and page.replace("-", "").replace(" ", "").isdigit():
            findings.append(
                FormatFinding("Page", "PAGE_RANGE", "Page must not be a range", index)
            )
        if profile == "reduced_federal" and row.get("Part"):
            findings.append(
                FormatFinding(
                    "Part",
                    "REDUCED_SCHEMA_REGRESSION",
                    "Part is not used on the reduced federal schema",
                    index,
                )
            )
        if (
            profile != "federal"
            and row.get("Part") not in (None, "")
            and not row.get("part_required")
        ):
            findings.append(
                FormatFinding(
                    "Part",
                    "PART_NOT_REQUIRED",
                    "Part is present without a required-part flag",
                    index,
                )
            )
    return findings
