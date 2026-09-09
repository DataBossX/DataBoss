"""Deterministic workbook inspection, validation, and rule-derived scoring."""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import unquote, urlparse

from .project_manifest import ControlFileError, sha256_file


EXCEL_ERROR_VALUES = {
    "#NULL!",
    "#DIV/0!",
    "#VALUE!",
    "#REF!",
    "#NAME?",
    "#NUM!",
    "#N/A",
    "#GETTING_DATA",
}
MATH_CHECKS = {
    "abstract_counts",
    "negative_current_ownership",
    "ownership_totals",
    "tract_acreage_totals",
    "lease_totals",
    "working_interest_totals",
    "no_duplicate_owners",
}
EVIDENCE_CHECKS = {
    "abstract_key_reconciliation",
    "abstract_required_fields",
    "source_manifest_complete",
    "evidence_crosswalk_complete",
    "evidence_links_resolve",
}
TEMPLATE_CHECKS = {
    "abstract_print_layout",
    "no_broken_formulas",
    "template_compliance",
    "print_rendering",
}
TOTAL_CHECKS = {
    "ownership_totals",
    "tract_acreage_totals",
    "lease_totals",
    "working_interest_totals",
}


@dataclass(frozen=True)
class QAFinding:
    check_id: str
    severity: str
    code: str
    message: str
    sheet: str = ""
    cell: str = ""
    repairable: bool = False


@dataclass
class CheckResult:
    check_id: str
    status: str
    score: float
    findings: List[QAFinding] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.status == "passed"


@dataclass(frozen=True)
class QAScore:
    completeness: float
    mathematical_accuracy: float
    evidence_support: float
    template_compliance: float
    unresolved_conflicts: int
    overall_score: float
    technical_pass: bool
    promotion_ready: bool = False


@dataclass
class QAReport:
    workbook: str
    sha256: str
    checks: List[CheckResult]
    score: QAScore
    inventory: Dict[str, Any]

    @property
    def findings(self) -> List[QAFinding]:
        return [finding for check in self.checks for finding in check.findings]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workbook": self.workbook,
            "sha256": self.sha256,
            "checks": [asdict(check) for check in self.checks],
            "score": asdict(self.score),
            "inventory": self.inventory,
        }


@dataclass
class AbstractTableView:
    table_id: str
    sheet: str
    columns: Dict[str, str]
    key_field: str
    key_normalization: str
    rows: List[Tuple[int, Dict[str, Any]]]
    rule: Dict[str, Any]


def load_workbook_profile(path: Optional[Path]) -> Dict[str, Any]:
    if path is None:
        return {}
    try:
        profile = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ControlFileError(f"Cannot read workbook profile {path}: {exc}") from exc
    if not isinstance(profile, dict):
        raise ControlFileError(f"Workbook profile {path} must be a JSON object")
    return profile


def _open_workbook(path: Path, *, data_only: bool = False):
    import openpyxl

    return openpyxl.load_workbook(
        path,
        data_only=data_only,
        read_only=False,
        keep_links=True,
        keep_vba=path.suffix.lower() == ".xlsm",
    )


def _formula_cells(workbook) -> Iterable[Tuple[str, str, str]]:
    for sheet in workbook.worksheets:
        for row in sheet.iter_rows():
            for cell in row:
                if cell.data_type == "f" or (
                    isinstance(cell.value, str) and cell.value.startswith("=")
                ):
                    yield sheet.title, cell.coordinate, str(cell.value)


def _is_broken_formula(formula: str) -> bool:
    upper = formula.upper()
    return upper.startswith("=#") or any(token in upper for token in EXCEL_ERROR_VALUES)


def _is_excel_error(value: Any) -> bool:
    return isinstance(value, str) and value.upper() in EXCEL_ERROR_VALUES


def _workbook_inventory(workbook) -> Dict[str, Any]:
    formula_count = sum(1 for _ in _formula_cells(workbook))
    return {
        "sheet_names": list(workbook.sheetnames),
        "sheet_states": {
            sheet.title: sheet.sheet_state for sheet in workbook.worksheets
        },
        "formula_count": formula_count,
        "defined_name_count": len(workbook.defined_names),
        "external_link_count": len(getattr(workbook, "_external_links", [])),
        "has_vba": getattr(workbook, "vba_archive", None) is not None,
    }


def _failed(
    check_id: str,
    code: str,
    message: str,
    *,
    status: str = "failed",
    sheet: str = "",
    cell: str = "",
    repairable: bool = False,
) -> CheckResult:
    return CheckResult(
        check_id=check_id,
        status=status,
        score=0.0,
        findings=[
            QAFinding(
                check_id=check_id,
                severity="blocking",
                code=code,
                message=message,
                sheet=sheet,
                cell=cell,
                repairable=repairable,
            )
        ],
    )


def _check_result(
    check_id: str,
    findings: List[QAFinding],
    metrics: Dict[str, Any],
) -> CheckResult:
    passed = not findings
    return CheckResult(
        check_id=check_id,
        status="passed" if passed else "failed",
        score=100.0 if passed else 0.0,
        findings=findings,
        metrics=metrics,
    )


def _check_formulas(workbook, values_workbook, template) -> CheckResult:
    findings: List[QAFinding] = []
    workbook_formulas = {
        (sheet, cell): formula for sheet, cell, formula in _formula_cells(workbook)
    }
    template_formulas = (
        {(sheet, cell): formula for sheet, cell, formula in _formula_cells(template)}
        if template
        else {}
    )
    formula_coordinates = sorted(set(workbook_formulas) | set(template_formulas))
    for sheet, cell in formula_coordinates:
        formula = workbook_formulas.get((sheet, cell), "")
        authoritative_formula = template_formulas.get((sheet, cell), "")
        if authoritative_formula and formula != authoritative_formula:
            findings.append(
                QAFinding(
                    check_id="no_broken_formulas",
                    severity="blocking",
                    code="authoritative_formula_mismatch",
                    message=(
                        f"Formula {formula!r} differs from template authority "
                        f"{authoritative_formula!r}"
                    ),
                    sheet=sheet,
                    cell=cell,
                    repairable=True,
                )
            )
            continue
        cached = values_workbook[sheet][cell].value
        formula_broken = _is_broken_formula(formula)
        cached_error = _is_excel_error(cached)
        cached_missing = cached is None
        if not formula_broken and not cached_error and not cached_missing:
            continue
        replacement = template_formulas.get((sheet, cell), "")
        repairable = bool(
            replacement
            and not _is_broken_formula(replacement)
            and (formula_broken or cached_error)
        )
        if formula_broken or cached_error:
            code = "broken_formula"
            message = (
                f"Formula {formula!r} has an invalid expression or cached "
                f"error value {cached!r}"
            )
        else:
            code = "formula_not_calculated"
            message = (
                f"Formula {formula!r} has no cached result; approved "
                "recalculation is required"
            )
        findings.append(
            QAFinding(
                check_id="no_broken_formulas",
                severity="blocking",
                code=code,
                message=message,
                sheet=sheet,
                cell=cell,
                repairable=repairable,
            )
        )
    return _check_result(
        "no_broken_formulas",
        findings,
        {
            "formula_cells_checked": len(formula_coordinates),
            "validation_mode": "formula_text_and_cached_results",
        },
    )


def _check_template(workbook, template, profile: Dict[str, Any]) -> CheckResult:
    expected_order = profile.get("required_sheet_order")
    if expected_order is None and template is not None:
        expected_order = list(template.sheetnames)
    if not expected_order:
        return _failed(
            "template_compliance",
            "template_authority_missing",
            "No template workbook or required_sheet_order was provided",
            status="not_evaluated",
        )

    actual = list(workbook.sheetnames)
    preserve_order = profile.get("preserve_sheet_order", True)
    allow_new = profile.get("allow_new_sheets", False)
    findings: List[QAFinding] = []
    missing = [name for name in expected_order if name not in actual]
    extras = [name for name in actual if name not in expected_order]
    if missing:
        findings.append(
            QAFinding(
                "template_compliance",
                "blocking",
                "missing_sheets",
                f"Missing sheets: {missing}",
            )
        )
    if extras and not allow_new:
        findings.append(
            QAFinding(
                "template_compliance",
                "blocking",
                "unexpected_sheets",
                f"Unexpected sheets: {extras}",
            )
        )
    if preserve_order and [name for name in actual if name in expected_order] != [
        name for name in expected_order if name in actual
    ]:
        findings.append(
            QAFinding(
                "template_compliance",
                "blocking",
                "sheet_order_changed",
                "Workbook sheet order differs from the template authority",
            )
        )
    if template is not None:
        for name in set(actual) & set(template.sheetnames):
            if workbook[name].sheet_state != template[name].sheet_state:
                findings.append(
                    QAFinding(
                        "template_compliance",
                        "blocking",
                        "sheet_visibility_changed",
                        "Sheet visibility differs from template",
                        sheet=name,
                    )
                )
    return _check_result(
        "template_compliance",
        findings,
        {"expected_sheet_count": len(expected_order), "actual_sheet_count": len(actual)},
    )


def _profile_cells(profile: Dict[str, Any], key: str) -> List[Dict[str, Any]]:
    value = profile.get(key, [])
    return value if isinstance(value, list) else []


_COLUMN_REFERENCE = re.compile(r"^[A-Z]{1,3}$")
_MAX_EXCEL_ROW = 1_048_576


def _is_populated(value: Any) -> bool:
    return value is not None and bool(str(value).strip())


def _normalize_header(value: Any) -> str:
    return " ".join(str(value or "").casefold().split())


def _normalize_table_key(value: Any, mode: str) -> str:
    text = str(value or "").strip()
    if mode == "text":
        return " ".join(text.casefold().split())
    if mode == "alnum_upper":
        return "".join(character for character in text.upper() if character.isalnum())
    raise ValueError(f"unsupported key_normalization {mode!r}")


def _load_abstract_tables(
    workbook,
    profile: Dict[str, Any],
    check_id: str,
) -> Tuple[Dict[str, AbstractTableView], List[QAFinding]]:
    raw_tables = profile.get("abstract_tables")
    if not isinstance(raw_tables, list) or not raw_tables:
        return {}, []

    views: Dict[str, AbstractTableView] = {}
    findings: List[QAFinding] = []
    for table_index, rule in enumerate(raw_tables):
        if not isinstance(rule, dict):
            findings.append(
                QAFinding(
                    check_id,
                    "blocking",
                    "abstract_table_profile_invalid",
                    f"abstract_tables[{table_index}] must be an object",
                )
            )
            continue

        table_id = str(rule.get("id", "")).strip()
        sheet_name = str(rule.get("sheet", "")).strip()
        columns = rule.get("columns")
        key_field = str(rule.get("key_field", "")).strip()
        normalization = str(rule.get("key_normalization", "text")).strip()
        try:
            header_row = rule.get("header_row", 1)
            start_row = rule.get("start_row", header_row + 1)
            end_row_value = rule.get("end_row")
            if (
                not table_id
                or table_id in views
                or sheet_name not in workbook.sheetnames
                or not isinstance(columns, dict)
                or not columns
                or not key_field
                or key_field not in columns
                or normalization not in {"text", "alnum_upper"}
                or type(header_row) is not int
                or type(start_row) is not int
                or not 1 <= header_row <= _MAX_EXCEL_ROW
                or not 1 <= start_row <= _MAX_EXCEL_ROW
                or start_row <= header_row
                or (
                    end_row_value is not None
                    and (
                        type(end_row_value) is not int
                        or not 1 <= end_row_value <= _MAX_EXCEL_ROW
                    )
                )
            ):
                raise ValueError
            normalized_columns = {
                str(field_name).strip(): str(column).strip().upper()
                for field_name, column in columns.items()
            }
            if (
                not all(normalized_columns)
                or not all(
                    _COLUMN_REFERENCE.fullmatch(column)
                    for column in normalized_columns.values()
                )
                or len(set(normalized_columns.values())) != len(normalized_columns)
            ):
                raise ValueError
            worksheet = workbook[sheet_name]
            end_row = (
                end_row_value
                if end_row_value is not None
                else max(start_row, worksheet.max_row)
            )
            if end_row < start_row:
                raise ValueError
        except (TypeError, ValueError):
            findings.append(
                QAFinding(
                    check_id,
                    "blocking",
                    "abstract_table_profile_invalid",
                    f"Invalid abstract table profile at index {table_index}",
                    sheet=sheet_name,
                )
            )
            continue

        expected_headers = rule.get("expected_headers", {})
        if not isinstance(expected_headers, dict):
            findings.append(
                QAFinding(
                    check_id,
                    "blocking",
                    "abstract_table_profile_invalid",
                    f"Table {table_id!r} expected_headers must be an object",
                    sheet=sheet_name,
                )
            )
            continue
        for field_name, expected in expected_headers.items():
            if field_name not in normalized_columns:
                findings.append(
                    QAFinding(
                        check_id,
                        "blocking",
                        "abstract_table_profile_invalid",
                        f"Table {table_id!r} header field {field_name!r} has no column",
                        sheet=sheet_name,
                    )
                )
                continue
            expected_values = expected if isinstance(expected, list) else [expected]
            expected_normalized = {
                _normalize_header(value)
                for value in expected_values
                if _is_populated(value)
            }
            coordinate = f"{normalized_columns[field_name]}{header_row}"
            actual = worksheet[coordinate].value
            if (
                not expected_normalized
                or _normalize_header(actual) not in expected_normalized
            ):
                findings.append(
                    QAFinding(
                        check_id,
                        "blocking",
                        "abstract_header_mismatch",
                        f"Table {table_id!r} field {field_name!r} expected header "
                        f"{expected_values!r}, found {actual!r}",
                        sheet=sheet_name,
                        cell=coordinate,
                    )
                )

        rows: List[Tuple[int, Dict[str, Any]]] = []
        for row_number in range(start_row, end_row + 1):
            values = {
                field_name: worksheet[f"{column}{row_number}"].value
                for field_name, column in normalized_columns.items()
            }
            if any(_is_populated(value) for value in values.values()):
                rows.append((row_number, values))
        views[table_id] = AbstractTableView(
            table_id=table_id,
            sheet=sheet_name,
            columns=normalized_columns,
            key_field=key_field,
            key_normalization=normalization,
            rows=rows,
            rule=rule,
        )
    return views, findings


def _check_abstract_required_fields(
    workbook,
    profile: Dict[str, Any],
) -> CheckResult:
    check_id = "abstract_required_fields"
    views, findings = _load_abstract_tables(workbook, profile, check_id)
    configured = [
        view
        for view in views.values()
        if "required_fields" in view.rule
    ]
    if not configured and not findings:
        return _failed(
            check_id,
            "rule_not_configured",
            "No abstract table required_fields are configured",
            status="not_evaluated",
        )

    rows_checked = 0
    fields_checked = 0
    for view in configured:
        required_fields = view.rule["required_fields"]
        if (
            not isinstance(required_fields, list)
            or not required_fields
            or not all(
                isinstance(item, str) and item.strip()
                for item in required_fields
            )
            or len(required_fields) != len(set(required_fields))
            or any(field_name not in view.columns for field_name in required_fields)
        ):
            findings.append(
                QAFinding(
                    check_id,
                    "blocking",
                    "abstract_table_profile_invalid",
                    f"Table {view.table_id!r} has invalid required_fields",
                    sheet=view.sheet,
                )
            )
            continue
        if not view.rows:
            findings.append(
                QAFinding(
                    check_id,
                    "blocking",
                    "abstract_table_empty",
                    f"Table {view.table_id!r} contains no populated data rows",
                    sheet=view.sheet,
                )
            )
            continue
        for row_number, values in view.rows:
            rows_checked += 1
            for field_name in required_fields:
                fields_checked += 1
                if not _is_populated(values.get(field_name)):
                    findings.append(
                        QAFinding(
                            check_id,
                            "blocking",
                            "abstract_required_field_blank",
                            f"Table {view.table_id!r} row {row_number} requires "
                            f"{field_name!r}",
                            sheet=view.sheet,
                            cell=f"{view.columns[field_name]}{row_number}",
                        )
                    )
    return _check_result(
        check_id,
        findings,
        {
            "tables_checked": len(configured),
            "rows_checked": rows_checked,
            "fields_checked": fields_checked,
        },
    )


def _table_keys(
    view: AbstractTableView,
    check_id: str,
) -> Tuple[List[str], List[QAFinding]]:
    keys: List[str] = []
    findings: List[QAFinding] = []
    for row_number, values in view.rows:
        key = _normalize_table_key(values.get(view.key_field), view.key_normalization)
        if not key:
            findings.append(
                QAFinding(
                    check_id,
                    "blocking",
                    "abstract_key_blank",
                    f"Table {view.table_id!r} row {row_number} has a blank key",
                    sheet=view.sheet,
                    cell=f"{view.columns[view.key_field]}{row_number}",
                )
            )
        else:
            keys.append(key)
    duplicate_keys = sorted(
        key for key, count in Counter(keys).items() if count > 1
    )
    for key in duplicate_keys:
        findings.append(
            QAFinding(
                check_id,
                "blocking",
                "abstract_key_duplicate",
                f"Table {view.table_id!r} contains duplicate key {key!r}",
                sheet=view.sheet,
            )
        )
    return keys, findings


def _check_abstract_counts(workbook, profile: Dict[str, Any]) -> CheckResult:
    check_id = "abstract_counts"
    views, findings = _load_abstract_tables(workbook, profile, check_id)
    configured = [
        view
        for view in views.values()
        if "expected_rows" in view.rule or "expected_unique_keys" in view.rule
    ]
    if not configured and not findings:
        return _failed(
            check_id,
            "rule_not_configured",
            "No expected abstract row or unique-key counts are configured",
            status="not_evaluated",
        )

    total_rows = 0
    total_unique_keys = 0
    for view in configured:
        keys, key_findings = _table_keys(view, check_id)
        findings.extend(key_findings)
        unique_key_count = len(set(keys))
        total_rows += len(view.rows)
        total_unique_keys += unique_key_count
        for field_name, actual in (
            ("expected_rows", len(view.rows)),
            ("expected_unique_keys", unique_key_count),
        ):
            if field_name not in view.rule:
                continue
            expected = view.rule[field_name]
            if (
                not isinstance(expected, int)
                or isinstance(expected, bool)
                or expected < 0
            ):
                findings.append(
                    QAFinding(
                        check_id,
                        "blocking",
                        "abstract_table_profile_invalid",
                        f"Table {view.table_id!r} {field_name} must be a "
                        "non-negative integer",
                        sheet=view.sheet,
                    )
                )
            elif actual != expected:
                findings.append(
                    QAFinding(
                        check_id,
                        "blocking",
                        "abstract_count_mismatch",
                        f"Table {view.table_id!r} {field_name}={expected}, "
                        f"found {actual}",
                        sheet=view.sheet,
                    )
                )
    return _check_result(
        check_id,
        findings,
        {
            "tables_checked": len(configured),
            "rows_counted": total_rows,
            "unique_keys_counted": total_unique_keys,
        },
    )


def _check_abstract_key_reconciliation(
    workbook,
    profile: Dict[str, Any],
) -> CheckResult:
    check_id = "abstract_key_reconciliation"
    rules = profile.get("abstract_key_reconciliations")
    if not isinstance(rules, list) or not rules:
        return _failed(
            check_id,
            "rule_not_configured",
            "No abstract key reconciliations are configured",
            status="not_evaluated",
        )
    views, findings = _load_abstract_tables(workbook, profile, check_id)
    comparisons = 0
    for index, rule in enumerate(rules):
        if not isinstance(rule, dict):
            findings.append(
                QAFinding(
                    check_id,
                    "blocking",
                    "abstract_reconciliation_profile_invalid",
                    f"abstract_key_reconciliations[{index}] must be an object",
                )
            )
            continue
        left_id = str(rule.get("left_table", ""))
        right_id = str(rule.get("right_table", ""))
        left = views.get(left_id)
        right = views.get(right_id)
        if (
            left is None
            or right is None
            or left_id == right_id
            or rule.get("mode", "exact") != "exact"
            or left.key_normalization != right.key_normalization
        ):
            findings.append(
                QAFinding(
                    check_id,
                    "blocking",
                    "abstract_reconciliation_profile_invalid",
                    f"Invalid reconciliation at index {index}: "
                    f"{left_id!r} -> {right_id!r}",
                )
            )
            continue
        left_keys, left_findings = _table_keys(left, check_id)
        right_keys, right_findings = _table_keys(right, check_id)
        findings.extend(left_findings)
        findings.extend(right_findings)
        comparisons += 1
        left_set = set(left_keys)
        right_set = set(right_keys)
        missing_left = sorted(right_set - left_set)
        missing_right = sorted(left_set - right_set)
        if missing_left:
            findings.append(
                QAFinding(
                    check_id,
                    "blocking",
                    "abstract_keys_missing_left",
                    f"{len(missing_left)} keys from {right_id!r} are absent from "
                    f"{left_id!r}: {missing_left[:10]}",
                )
            )
        if missing_right:
            findings.append(
                QAFinding(
                    check_id,
                    "blocking",
                    "abstract_keys_missing_right",
                    f"{len(missing_right)} keys from {left_id!r} are absent from "
                    f"{right_id!r}: {missing_right[:10]}",
                )
            )
    return _check_result(
        check_id,
        findings,
        {"comparisons_checked": comparisons},
    )


def _normalize_print_reference(value: Any) -> str:
    text = str(value or "").strip()
    if "!" in text:
        text = text.split("!", 1)[1]
    return text.replace("'", "")


def _valid_layout_value(setting: str, value: Any) -> bool:
    if setting == "orientation":
        return isinstance(value, str) and value in {"portrait", "landscape"}
    if setting == "paper_size":
        return type(value) is int and 1 <= value <= 118
    if setting in {"fit_to_width", "fit_to_height"}:
        return type(value) is int and 0 <= value <= 32_767
    if setting == "scale":
        return type(value) is int and 10 <= value <= 400
    if setting == "fit_to_page":
        return type(value) is bool
    if setting in {"print_area", "print_title_rows", "print_title_cols"}:
        return isinstance(value, str) and bool(value.strip())
    if setting == "freeze_panes":
        return isinstance(value, str)
    return False


def _check_abstract_print_layout(
    workbook,
    profile: Dict[str, Any],
) -> CheckResult:
    check_id = "abstract_print_layout"
    rules = profile.get("abstract_print_layout")
    if not isinstance(rules, list) or not rules:
        return _failed(
            check_id,
            "rule_not_configured",
            "No abstract print-layout assertions are configured",
            status="not_evaluated",
        )

    findings: List[QAFinding] = []
    assertions_checked = 0
    supported = {
        "orientation": lambda ws: ws.page_setup.orientation,
        "paper_size": lambda ws: ws.page_setup.paperSize,
        "fit_to_width": lambda ws: ws.page_setup.fitToWidth,
        "fit_to_height": lambda ws: ws.page_setup.fitToHeight,
        "scale": lambda ws: ws.page_setup.scale,
        "fit_to_page": lambda ws: ws.sheet_properties.pageSetUpPr.fitToPage,
        "print_area": lambda ws: _normalize_print_reference(ws.print_area),
        "print_title_rows": lambda ws: str(ws.print_title_rows or ""),
        "print_title_cols": lambda ws: str(ws.print_title_cols or ""),
        "freeze_panes": lambda ws: (
            ws.freeze_panes.coordinate
            if hasattr(ws.freeze_panes, "coordinate")
            else str(ws.freeze_panes or "")
        ),
    }
    allowed_keys = {"sheet", *supported}
    for index, rule in enumerate(rules):
        if not isinstance(rule, dict):
            findings.append(
                QAFinding(
                    check_id,
                    "blocking",
                    "abstract_layout_profile_invalid",
                    f"abstract_print_layout[{index}] must be an object",
                )
            )
            continue
        sheet_name = str(rule.get("sheet", ""))
        unknown_keys = sorted(set(rule) - allowed_keys)
        expected = {key: value for key, value in rule.items() if key in supported}
        invalid_values = sorted(
            setting
            for setting, value in expected.items()
            if not _valid_layout_value(setting, value)
        )
        if (
            sheet_name not in workbook.sheetnames
            or not expected
            or unknown_keys
            or invalid_values
        ):
            findings.append(
                QAFinding(
                    check_id,
                    "blocking",
                    "abstract_layout_profile_invalid",
                    f"Invalid print-layout assertion at index {index}: "
                    f"unknown={unknown_keys}, invalid_values={invalid_values}",
                    sheet=sheet_name,
                )
            )
            continue
        worksheet = workbook[sheet_name]
        for setting, expected_value in expected.items():
            assertions_checked += 1
            actual_value = supported[setting](worksheet)
            if setting in {"print_area", "print_title_rows", "print_title_cols"}:
                expected_value = _normalize_print_reference(expected_value)
            if actual_value != expected_value:
                findings.append(
                    QAFinding(
                        check_id,
                        "blocking",
                        "abstract_layout_mismatch",
                        f"{sheet_name!r} {setting} expected {expected_value!r}, "
                        f"found {actual_value!r}",
                        sheet=sheet_name,
                    )
                )
    return _check_result(
        check_id,
        findings,
        {
            "sheets_checked": len(rules),
            "assertions_checked": assertions_checked,
        },
    )


def _check_total_assertions(workbook, profile: Dict[str, Any], check_id: str) -> CheckResult:
    assertions = [
        item
        for item in _profile_cells(profile, "total_assertions")
        if item.get("check_id") == check_id
    ]
    if not assertions:
        return _failed(
            check_id,
            "rule_not_configured",
            f"No deterministic assertions configured for {check_id}",
            status="not_evaluated",
        )
    findings: List[QAFinding] = []
    for rule in assertions:
        sheet, cell = str(rule.get("sheet", "")), str(rule.get("cell", ""))
        if sheet not in workbook.sheetnames or not cell:
            findings.append(
                QAFinding(
                    check_id,
                    "blocking",
                    "assertion_target_missing",
                    f"Assertion target {sheet}!{cell} does not exist",
                    sheet,
                    cell,
                )
            )
            continue
        value = workbook[sheet][cell].value
        expected = rule.get("expected")
        try:
            actual_number = float(value)
            expected_number = float(expected)
            tolerance = float(rule.get("tolerance", 0))
            difference = abs(actual_number - expected_number)
            valid = (
                math.isfinite(actual_number)
                and math.isfinite(expected_number)
                and math.isfinite(tolerance)
                and tolerance >= 0
                and math.isfinite(difference)
            )
        except (TypeError, ValueError):
            difference = float("inf")
            tolerance = float("nan")
            valid = False
        if not valid or difference > tolerance:
            findings.append(
                QAFinding(
                    check_id,
                    "blocking",
                    "total_out_of_tolerance",
                    f"Expected {expected!r} ± {tolerance}, found {value!r}",
                    sheet,
                    cell,
                )
            )
    return _check_result(
        check_id,
        findings,
        {"assertions_checked": len(assertions)},
    )


def _check_negative_ownership(workbook, profile: Dict[str, Any]) -> CheckResult:
    ranges = _profile_cells(profile, "current_ownership_ranges")
    if not ranges:
        return _failed(
            "negative_current_ownership",
            "rule_not_configured",
            "No current_ownership_ranges are configured",
            status="not_evaluated",
        )
    findings: List[QAFinding] = []
    checked = 0
    for rule in ranges:
        sheet_name, cell_range = str(rule.get("sheet", "")), str(rule.get("range", ""))
        if sheet_name not in workbook.sheetnames or not cell_range:
            findings.append(
                QAFinding(
                    "negative_current_ownership",
                    "blocking",
                    "ownership_range_missing",
                    f"Ownership range {sheet_name}!{cell_range} does not exist",
                )
            )
            continue
        for row in workbook[sheet_name][cell_range]:
            for cell in row:
                if isinstance(cell.value, (int, float)):
                    checked += 1
                    if not math.isfinite(float(cell.value)) or cell.value < 0:
                        findings.append(
                            QAFinding(
                                "negative_current_ownership",
                                "blocking",
                                "negative_interest",
                                f"Invalid current ownership value {cell.value}",
                                sheet_name,
                                cell.coordinate,
                            )
                        )
    return _check_result(
        "negative_current_ownership",
        findings,
        {"numeric_cells_checked": checked},
    )


def _check_duplicate_owners(workbook, profile: Dict[str, Any]) -> CheckResult:
    tables = _profile_cells(profile, "current_owner_columns")
    if not tables:
        return _failed(
            "no_duplicate_owners",
            "rule_not_configured",
            "No current_owner_columns are configured",
            status="not_evaluated",
        )
    findings: List[QAFinding] = []
    checked = 0
    for rule in tables:
        sheet_name = str(rule.get("sheet", ""))
        column = str(rule.get("column", "A"))
        start_row = int(rule.get("start_row", 2))
        default_end_row = (
            workbook[sheet_name].max_row if sheet_name in workbook.sheetnames else 1
        )
        end_row = int(rule.get("end_row", default_end_row))
        if sheet_name not in workbook.sheetnames:
            findings.append(
                QAFinding(
                    "no_duplicate_owners",
                    "blocking",
                    "owner_sheet_missing",
                    f"Owner sheet {sheet_name!r} does not exist",
                )
            )
            continue
        seen: Dict[str, str] = {}
        for row_number in range(start_row, end_row + 1):
            cell = workbook[sheet_name][f"{column}{row_number}"]
            name = " ".join(str(cell.value or "").casefold().split())
            if not name:
                continue
            checked += 1
            if name in seen:
                findings.append(
                    QAFinding(
                        "no_duplicate_owners",
                        "blocking",
                        "duplicate_owner",
                        f"Owner duplicates {seen[name]}",
                        sheet_name,
                        cell.coordinate,
                    )
                )
            else:
                seen[name] = cell.coordinate
    return _check_result(
        "no_duplicate_owners",
        findings,
        {"owners_checked": checked},
    )


def _check_evidence_links(workbook, evidence_root: Path) -> CheckResult:
    findings: List[QAFinding] = []
    checked = 0
    resolved_root = evidence_root.resolve()
    for sheet in workbook.worksheets:
        for row in sheet.iter_rows():
            for cell in row:
                if not cell.hyperlink:
                    continue
                checked += 1
                target = str(cell.hyperlink.target or "")
                if not target:
                    findings.append(
                        QAFinding(
                            "evidence_links_resolve",
                            "blocking",
                            "empty_or_internal_evidence_link",
                            "Evidence hyperlink has no external target",
                            sheet.title,
                            cell.coordinate,
                        )
                    )
                    continue
                parsed = urlparse(target)
                if parsed.scheme in ("http", "https") and parsed.netloc:
                    findings.append(
                        QAFinding(
                            "evidence_links_resolve",
                            "blocking",
                            "remote_link_unverified",
                            f"Remote evidence link requires an acquisition receipt: {target!r}",
                            sheet.title,
                            cell.coordinate,
                        )
                    )
                    continue
                if parsed.scheme == "file":
                    local = Path(unquote(parsed.path))
                elif not parsed.scheme:
                    local = resolved_root / unquote(target)
                else:
                    local = None
                contained = False
                if local is not None:
                    resolved_local = local.resolve()
                    try:
                        resolved_local.relative_to(resolved_root)
                        contained = True
                    except ValueError:
                        contained = False
                if (
                    local is None
                    or not contained
                    or not resolved_local.is_file()
                ):
                    findings.append(
                        QAFinding(
                            "evidence_links_resolve",
                            "blocking",
                            "unresolved_evidence_link",
                            f"Evidence link does not resolve: {target!r}",
                            sheet.title,
                            cell.coordinate,
                        )
                    )
    if not checked:
        return _failed(
            "evidence_links_resolve",
            "no_evidence_links",
            "No workbook evidence links were available to validate",
            status="not_evaluated",
        )
    return _check_result(
        "evidence_links_resolve",
        findings,
        {"links_checked": checked},
    )


def _unsupported(check_id: str) -> CheckResult:
    return _failed(
        check_id,
        "validator_unavailable",
        f"No deterministic validator is registered for {check_id}",
        status="not_evaluated",
    )


def _component_score(results: Dict[str, CheckResult], check_ids: set) -> float:
    selected = [results[item].score for item in check_ids if item in results]
    return round(sum(selected) / len(selected), 2) if selected else 0.0


def inspect_workbook(
    workbook_path: Path,
    acceptance_tests: List[str],
    *,
    template_path: Optional[Path] = None,
    profile: Optional[Dict[str, Any]] = None,
) -> QAReport:
    """Run configured checks against one immutable workbook snapshot."""
    workbook_path = Path(workbook_path)
    profile = profile or {}
    workbook = _open_workbook(workbook_path)
    values_workbook = _open_workbook(workbook_path, data_only=True)
    template = _open_workbook(template_path) if template_path else None
    inventory = _workbook_inventory(workbook)
    results: List[CheckResult] = []

    try:
        for check_id in acceptance_tests:
            if check_id == "no_broken_formulas":
                result = _check_formulas(workbook, values_workbook, template)
            elif check_id == "template_compliance":
                result = _check_template(workbook, template, profile)
            elif check_id == "abstract_required_fields":
                result = _check_abstract_required_fields(values_workbook, profile)
            elif check_id == "abstract_counts":
                result = _check_abstract_counts(values_workbook, profile)
            elif check_id == "abstract_key_reconciliation":
                result = _check_abstract_key_reconciliation(
                    values_workbook, profile
                )
            elif check_id == "abstract_print_layout":
                result = _check_abstract_print_layout(workbook, profile)
            elif check_id == "negative_current_ownership":
                result = _check_negative_ownership(values_workbook, profile)
            elif check_id == "no_duplicate_owners":
                result = _check_duplicate_owners(workbook, profile)
            elif check_id in TOTAL_CHECKS:
                result = _check_total_assertions(
                    values_workbook, profile, check_id
                )
            elif check_id == "evidence_links_resolve":
                evidence_root = Path(
                    profile.get("evidence_root") or workbook_path.parent
                )
                result = _check_evidence_links(workbook, evidence_root)
            elif check_id == "human_landman_release":
                result = _failed(
                    check_id,
                    "human_approval_pending",
                    "Technical verification cannot satisfy the human release gate",
                    status="pending_approval",
                )
            else:
                result = _unsupported(check_id)
            results.append(result)
    finally:
        workbook.close()
        values_workbook.close()
        if template is not None:
            template.close()

    by_id = {result.check_id: result for result in results}
    technical = [
        result
        for result in results
        if result.check_id != "human_landman_release"
    ]
    technical_pass = bool(technical) and all(result.passed for result in technical)
    unresolved = sum(len(result.findings) for result in results if not result.passed)
    completeness = round(
        100.0 * sum(result.passed for result in results) / len(results), 2
    ) if results else 0.0
    math_score = _component_score(by_id, MATH_CHECKS)
    evidence_score = _component_score(by_id, EVIDENCE_CHECKS)
    template_score = _component_score(by_id, TEMPLATE_CHECKS)
    overall = round(
        0.25 * completeness
        + 0.35 * math_score
        + 0.20 * evidence_score
        + 0.20 * template_score,
        2,
    )
    score = QAScore(
        completeness=completeness,
        mathematical_accuracy=math_score,
        evidence_support=evidence_score,
        template_compliance=template_score,
        unresolved_conflicts=unresolved,
        overall_score=overall,
        technical_pass=technical_pass,
        promotion_ready=False,
    )
    return QAReport(
        workbook=str(workbook_path),
        sha256=sha256_file(workbook_path),
        checks=results,
        score=score,
        inventory=inventory,
    )
