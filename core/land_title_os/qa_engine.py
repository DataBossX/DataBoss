"""Title-report QA engine (Move #7) — deterministic checks, exact fractions.

Checks operate on plain data: ``sheets`` is a dict of sheet name -> list of
row dicts, so the same engine works whether rows came from CSV, openpyxl, or
a Google Sheet export. Every finding names the sheet, row, column, severity,
and a recommended correction.

All interest math uses ``fractions.Fraction`` — never floats (Move #15/#64).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from fractions import Fraction

SEVERITIES = ("critical", "high", "medium", "low")


@dataclass
class Finding:
    rule: str
    severity: str
    sheet: str
    message: str
    row: int | None = None          # 1-based data row
    column: str | None = None
    recommendation: str = ""


def parse_interest(value) -> Fraction | None:
    """Parse '1/2', 'UND 20/260', '0.125', 20, or Fraction into an exact Fraction.

    Returns None for blank/unparseable values (caller decides severity).
    """
    if value is None:
        return None
    if isinstance(value, Fraction):
        return value
    if isinstance(value, int):
        return Fraction(value)
    if isinstance(value, float):
        return Fraction(str(value))      # exact per displayed value
    text = str(value).strip()
    if not text:
        return None
    m = re.search(r"(-?\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)", text)
    if m:
        return Fraction(m.group(1)) / Fraction(m.group(2))
    m = re.fullmatch(r"-?\d+(?:\.\d+)?", text)
    if m:
        return Fraction(text)
    return None


# --------------------------------------------------------------------------
# Individual checks — each returns a list[Finding]
# --------------------------------------------------------------------------

def check_negative_interests(sheet: str, rows: list[dict], column: str) -> list[Finding]:
    out = []
    for n, row in enumerate(rows, 1):
        f = parse_interest(row.get(column))
        if f is not None and f < 0:
            out.append(Finding(
                "negative_interest", "critical", sheet,
                f"{column} is negative ({row.get(column)!r}) — current ownership can never be negative",
                row=n, column=column,
                recommendation="Re-derive the chain for this owner; a conveyance was double-counted or mis-signed."))
    return out


def check_total(sheet: str, rows: list[dict], column: str, expected: Fraction,
                label: str = "ownership_total") -> list[Finding]:
    """Exact-fraction total check (ownership sums to 1, tract acres to 640, …)."""
    total = Fraction(0)
    counted = 0
    for row in rows:
        f = parse_interest(row.get(column))
        if f is not None:
            total += f
            counted += 1
    if counted and total != expected:
        return [Finding(
            label, "critical", sheet,
            f"{column} totals {total} ({float(total):.10f}); expected exactly {expected}",
            column=column,
            recommendation="Reconcile row-by-row against the evidence ledger; do not force-balance.")]
    return []


def check_duplicate_values(sheet: str, rows: list[dict], column: str,
                           rule: str = "duplicate_owner",
                           severity: str = "high") -> list[Finding]:
    seen: dict[str, int] = {}
    out = []
    for n, row in enumerate(rows, 1):
        key = str(row.get(column, "")).strip().lower()
        if not key:
            continue
        if key in seen:
            out.append(Finding(
                rule, severity, sheet,
                f"{column} value {row.get(column)!r} duplicates row {seen[key]}",
                row=n, column=column,
                recommendation="Merge rows only if identity is evidenced; otherwise disambiguate the names."))
        else:
            seen[key] = n
    return out


def check_missing(sheet: str, rows: list[dict], column: str,
                  rule: str, severity: str = "high") -> list[Finding]:
    out = []
    for n, row in enumerate(rows, 1):
        if not str(row.get(column, "") or "").strip():
            out.append(Finding(
                rule, severity, sheet, f"{column} is blank",
                row=n, column=column,
                recommendation=f"Locate the {column} in source evidence; flag REVIEW REQUIRED if unfound."))
    return out


_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")


def check_chronology(sheet: str, rows: list[dict], date_column: str) -> list[Finding]:
    """Runsheet rows must be in non-decreasing date order (ISO dates)."""
    out = []
    prev, prev_row = None, None
    for n, row in enumerate(rows, 1):
        m = _DATE_RE.match(str(row.get(date_column, "") or "").strip())
        if not m:
            continue
        cur = m.group(0)
        if prev is not None and cur < prev:
            out.append(Finding(
                "chronological_chain_break", "high", sheet,
                f"{date_column} {cur} (row {n}) precedes {prev} (row {prev_row}) — chain out of order",
                row=n, column=date_column,
                recommendation="Re-sort the runsheet by recorded date, or verify the transcribed date."))
        prev, prev_row = cur, n
    return out


def check_template_sheets(actual: list[str], expected: list[str],
                          allowed_extras: tuple = ()) -> list[Finding]:
    """Sheet names AND order must match the approved template (Move #19)."""
    out = []
    missing = [s for s in expected if s not in actual]
    extras = [s for s in actual if s not in expected and s not in allowed_extras]
    for s in missing:
        out.append(Finding("template_missing_sheet", "critical", s,
                           f"required sheet {s!r} is absent",
                           recommendation="Restore the sheet from the approved template."))
    for s in extras:
        out.append(Finding("template_unexpected_sheet", "high", s,
                           f"sheet {s!r} is not in the approved template",
                           recommendation="Remove or get explicit authorization for the extra sheet."))
    core = [s for s in actual if s in expected]
    if not missing and core != expected:
        out.append(Finding("template_sheet_order", "high", "(workbook)",
                           f"sheet order {core} deviates from template {expected}",
                           recommendation="Reorder sheets to match the approved template exactly."))
    return out


# --------------------------------------------------------------------------
# Convenience runner
# --------------------------------------------------------------------------

DEFAULT_CONFIG = {
    "ownership_sheet": "Title",
    "ownership_column": "Interest",
    "owner_name_column": "Owner",
    "runsheet_sheet": "Runsheet",
    "runsheet_date_column": "Recorded_Date",
    "runsheet_instrument_column": "Instrument_Number",
    "expected_ownership_total": Fraction(1),
}


def run_standard_checks(sheets: dict[str, list[dict]], config: dict | None = None,
                        expected_sheet_order: list[str] | None = None) -> list[Finding]:
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    findings: list[Finding] = []

    own_sheet = cfg["ownership_sheet"]
    if own_sheet in sheets:
        rows = sheets[own_sheet]
        findings += check_negative_interests(own_sheet, rows, cfg["ownership_column"])
        findings += check_total(own_sheet, rows, cfg["ownership_column"],
                                cfg["expected_ownership_total"])
        findings += check_duplicate_values(own_sheet, rows, cfg["owner_name_column"])
        findings += check_missing(own_sheet, rows, cfg["owner_name_column"],
                                  "unsupported_owner_name", "critical")

    run_sheet = cfg["runsheet_sheet"]
    if run_sheet in sheets:
        rows = sheets[run_sheet]
        findings += check_chronology(run_sheet, rows, cfg["runsheet_date_column"])
        findings += check_missing(run_sheet, rows, cfg["runsheet_instrument_column"],
                                  "missing_instrument", "high")

    if expected_sheet_order:
        findings += check_template_sheets(list(sheets), expected_sheet_order)

    order = {s: n for n, s in enumerate(SEVERITIES)}
    findings.sort(key=lambda f: order[f.severity])
    return findings
