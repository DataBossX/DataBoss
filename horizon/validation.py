"""Validation gate -- checks a report against the Golden Source of Truth.

``project_notes_updated.xlsx`` is treated as the Golden Source: it defines which
columns must exist and (optionally) which instrument numbers / requirements the
final report must satisfy. This module loads those requirements when the file is
present, and otherwise falls back to the built-in canonical schema so validation
still runs (and is testable) without the operator's workbook.

Validation NEVER fabricates data. A missing/undetermined value produces a
``review`` or ``escalated`` issue; it does not get auto-filled.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Set

from .interest import reconcile, try_parse_interest
from .models import (
    CANONICAL_COLUMNS,
    ESCALATED_TAG,
    REVIEW_TAG,
    ReportModel,
    TitleRow,
    ValidationIssue,
)


# Header names that denote an instrument/document *number* (not a type/date).
_INSTRUMENT_NUMBER_HEADERS = {
    "instrument_number", "instrument_no", "instrument#", "instrument",
    "doc_no", "doc_number", "document_no", "document_number",
    "reception", "reception_no", "reception_number", "file_no", "recording_no",
}


def _is_instrument_number_header(col: str) -> bool:
    """True only for instrument/document *number* headers.

    Rejects related-but-different columns such as "instrument_type",
    "instrument_date" or "instrument_kind" that would otherwise be mistaken for
    a number column and load deed types/dates as required instruments.
    """
    c = (col or "").strip().lower().replace(" ", "_")
    if not c:
        return False
    if any(bad in c for bad in ("type", "date", "kind", "desc")):
        return False
    if c in _INSTRUMENT_NUMBER_HEADERS:
        return True
    if ("instrument" in c or "document" in c) and ("number" in c or c.endswith("_no")):
        return True
    return False


@dataclass
class Requirements:
    """Requirements pulled from the Golden Source (or the built-in defaults)."""

    required_columns: List[str] = field(default_factory=lambda: list(CANONICAL_COLUMNS))
    required_instruments: Set[str] = field(default_factory=set)
    source: str = "builtin-defaults"


def load_requirements(golden_path: Optional[Path]) -> Requirements:
    """Load requirements from ``project_notes_updated.xlsx`` if it exists.

    We read the header row for required columns and, if a column literally named
    like an instrument list is present, collect those instrument numbers as
    "must appear in the final report" gates. Missing file -> built-in defaults.
    """
    if golden_path is None or not Path(golden_path).exists():
        return Requirements()

    try:
        import openpyxl  # local import so the module imports without openpyxl
        from .chaining import normalize_instrument
    except ImportError:
        return Requirements(source=f"builtin-defaults (openpyxl unavailable; "
                                   f"{golden_path} NOT read)")

    try:
        wb = openpyxl.load_workbook(golden_path, read_only=True, data_only=True)
    except Exception as exc:
        # The Golden Source exists but could not be opened. Do NOT silently fall
        # back as if no gates were requested -- surface the failure in `source`
        # (which main logs) so the operator knows their gates were not applied.
        return Requirements(source=f"ERROR reading Golden Source {golden_path}: {exc}")

    req = Requirements(required_columns=[], source=str(golden_path))
    instruments: Set[str] = set()
    seen_cols: List[str] = []
    for ws in wb.worksheets:
        rows = ws.iter_rows(values_only=True)
        header = None
        inst_col = None
        for i, row in enumerate(rows):
            if header is None:
                header = [str(c).strip().lower().replace(" ", "_") if c else "" for c in row]
                for c in header:
                    if c and c not in seen_cols:
                        seen_cols.append(c)
                for j, c in enumerate(header):
                    if inst_col is None and _is_instrument_number_header(c):
                        inst_col = j
                continue
            if inst_col is not None and inst_col < len(row) and row[inst_col]:
                k = normalize_instrument(row[inst_col])
                # A real instrument/document number contains a digit. This guards
                # against a bare "Instrument" column that actually holds document
                # *types* ("Warranty Deed") being loaded as required instruments
                # and then reported as false "missing instrument" errors.
                if k and any(ch.isdigit() for ch in k):
                    instruments.add(k)
    wb.close()
    req.required_columns = seen_cols or list(CANONICAL_COLUMNS)
    req.required_instruments = instruments
    return req


@dataclass
class ValidationReport:
    passed: bool
    issues: List[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def reviews(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity in ("review", "escalated")]

    def summary(self) -> str:
        by = {}
        for i in self.issues:
            by[i.severity] = by.get(i.severity, 0) + 1
        return ", ".join(f"{k}={v}" for k, v in sorted(by.items())) or "clean"


def validate_report(report: ReportModel, requirements: Requirements) -> ValidationReport:
    """Run every gate. ``passed`` is True only when there are zero *error*-level
    issues (review/escalated issues are expected and do not fail the gate -- they
    are what a correct cursory report carries)."""
    issues: List[ValidationIssue] = []

    # Gate 1: interest reconciliation ties out per row (exact math).
    for idx, row in enumerate(report.rows):
        issues.extend(_validate_row_interest(idx, row))
        issues.extend(_validate_row_schema(idx, row))

    # Gate 2: required instruments from the Golden Source are all present.
    present = set(report.instrument_index().keys())
    for inst in sorted(requirements.required_instruments - present):
        issues.append(ValidationIssue(
            row_index=-1, field="instrument_number", severity="error",
            message=f"Required instrument {inst} from Golden Source is missing.",
        ))

    # Gate 3: every Golden-Source-required column maps to a report column.
    issues.extend(_validate_columns(requirements))

    passed = not any(i.severity == "error" for i in issues)
    return ValidationReport(passed=passed, issues=issues)


def _known_columns() -> Set[str]:
    """All column names the report schema can represent (canonical + synonyms)."""
    from .report_io import _HEADER_SYNONYMS  # local import avoids a cycle
    known: Set[str] = set(CANONICAL_COLUMNS)
    known.update(_HEADER_SYNONYMS.keys())
    known.update(_HEADER_SYNONYMS.values())
    return known


def _validate_columns(requirements: Requirements) -> List[ValidationIssue]:
    """Warn for any required Golden-Source column the report cannot carry.

    A missing column is a *warning*, not a hard error: the Golden Source may list
    bookkeeping columns unrelated to the report. But surfacing them means the
    gate actually consumes ``required_columns`` instead of ignoring it.
    """
    known = _known_columns()
    issues: List[ValidationIssue] = []
    for col in requirements.required_columns:
        norm = (col or "").strip().lower().replace(" ", "_")
        if norm and norm not in known:
            issues.append(ValidationIssue(
                row_index=-1, field=norm, severity="warn",
                message=(f"Golden Source column {col!r} is not represented in the "
                         f"report's canonical schema."),
            ))
    return issues


def _validate_row_interest(idx: int, row: TitleRow) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    # A row already tagged for examiner review (e.g. an over-conveyance) is
    # headed to a human; re-running the interest gate on it would only raise a
    # redundant error and stall the improvement loop. Skip it.
    if row.status != "ok":
        return issues
    # Only reconcile rows that actually claim an interest transfer.
    if not (row.conveyed_interest or row.retained_interest):
        return issues
    grantor_side = None
    if row.retained_interest and row.conveyed_interest:
        c = try_parse_interest(row.conveyed_interest)
        ret = try_parse_interest(row.retained_interest)
        if c is not None and ret is not None:
            grantor_side = c + ret  # implied grantor holding
            # The implied holding (conveyed + retained) cannot exceed the full
            # 8/8 estate. Reconstructing grantor_side from the row's own numbers
            # makes reconcile() trivially "balanced", so this is the only gate
            # that can catch an impossible/fabricated retained interest.
            if grantor_side > 1:
                issues.append(ValidationIssue(
                    row_index=idx, field="retained_interest", severity="error",
                    message=(f"Conveyed + retained = {grantor_side} implies a "
                             f"grantor holding greater than the full 8/8 estate."),
                ))
                return issues
    rc = reconcile(grantor_side, row.conveyed_interest)
    if rc.status == "over_conveyance":
        issues.append(ValidationIssue(
            row_index=idx, field="conveyed_interest", severity="error",
            message=rc.note,
        ))
    elif rc.status == "examiner_review":
        issues.append(ValidationIssue(
            row_index=idx, field="retained_interest", severity="review",
            message=rc.note,
        ))
    return issues


def _validate_row_schema(idx: int, row: TitleRow) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    if ESCALATED_TAG.lower() in (row.remarks or "").lower():
        issues.append(ValidationIssue(
            row_index=idx, field="remarks", severity="escalated",
            message="Row carries an ESCALATED flag (unsupported/missing fact).",
        ))
    elif REVIEW_TAG.lower() in (row.remarks or "").lower() or row.status != "ok":
        issues.append(ValidationIssue(
            row_index=idx, field="status", severity="review",
            message=f"Row flagged for examiner review (status={row.status!r}).",
        ))
    # An instrument reference is the primary key of the whole chain.
    if not row.instrument_key and (row.grantor or row.grantee):
        issues.append(ValidationIssue(
            row_index=idx, field="instrument_number", severity="warn",
            message="Conveyance row has no instrument number (chain-break risk).",
        ))
    return issues
