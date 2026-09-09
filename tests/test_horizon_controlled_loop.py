"""Tests for hash-bound, deterministic workbook QA and repair runs."""

import hashlib
import json
import zipfile
from pathlib import Path
from typing import List, Optional, Tuple

import openpyxl
import pytest
from lxml import etree

from horizon.controlled_loop import ControlledWorkbookLoop
from horizon.project_manifest import (
    ControlFileError,
    load_project_manifest,
    load_work_order,
)
from horizon.workbook_qa import inspect_workbook


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _set_cached_value(path: Path, cell_reference: str, value: float) -> None:
    namespace = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    temporary = path.with_suffix(".cached.xlsx")
    with zipfile.ZipFile(path, "r") as source, zipfile.ZipFile(
        temporary, "w", zipfile.ZIP_DEFLATED
    ) as output:
        for item in source.infolist():
            data = source.read(item.filename)
            if item.filename == "xl/worksheets/sheet1.xml":
                root = etree.fromstring(data)
                cell = root.find(f".//{{{namespace}}}c[@r={cell_reference!r}]")
                cached = cell.find(f"{{{namespace}}}v")
                cached.text = str(value)
                data = etree.tostring(
                    root,
                    xml_declaration=True,
                    encoding="UTF-8",
                    standalone=True,
                )
            output.writestr(item, data)
    temporary.replace(path)


def _make_workbook(
    path: Path, formula: str = "=SUM(B2:B3)", *, cache_formula: bool = True
) -> None:
    workbook = openpyxl.Workbook()
    title = workbook.active
    title.title = "Title"
    title.append(["Owner", "Current NMA"])
    title.append(["Alpha LLC", 20])
    title.append(["Beta LLC", 20])
    title["B4"] = formula
    title["D2"] = 40
    workbook.create_sheet("Runsheet")
    workbook.save(path)
    workbook.close()
    if cache_formula:
        _set_cached_value(path, "B4", 40)


def _write_controls(
    root: Path,
    candidate: Path,
    template: Path,
    *,
    candidate_hash: str = "",
    allowed_repairs: Optional[List[str]] = None,
    profile_data: Optional[dict] = None,
    required_checks: Optional[List[str]] = None,
) -> Tuple[Path, Path, Path]:
    project = root / "project"
    project.mkdir()
    profile = project / "workbook_profile.json"
    profile_data = profile_data if profile_data is not None else {
        "required_sheet_order": ["Title", "Runsheet"],
        "preserve_sheet_order": True,
        "allow_new_sheets": False,
        "current_ownership_ranges": [
            {"sheet": "Title", "range": "B2:B3"}
        ],
        "current_owner_columns": [
            {
                "sheet": "Title",
                "column": "A",
                "start_row": 2,
                "end_row": 3,
            }
        ],
        "total_assertions": [
            {
                "check_id": "ownership_totals",
                "sheet": "Title",
                "cell": "D2",
                "expected": 40,
                "tolerance": 0.01,
            }
        ],
    }
    profile.write_text(
        json.dumps(profile_data),
        encoding="utf-8",
    )
    required_checks = required_checks if required_checks is not None else [
        "negative_current_ownership",
        "ownership_totals",
        "no_duplicate_owners",
        "no_broken_formulas",
        "template_compliance",
        "human_landman_release",
    ]
    reported_hash = candidate_hash or _sha256(candidate)
    manifest_path = project / "project_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_id": "dbx.project_manifest",
                "schema_version": "1.1",
                "project_id": "DBX-TEST",
                "source_policy": "IMMUTABLE_READ_ONLY",
                "authority_hashes": {
                    "template": _sha256(template),
                    "workbook_profile": _sha256(profile),
                },
                "candidate_deliverables": [
                    {
                        "path": "candidate.xlsx",
                        "reported_sha256": reported_hash,
                        "status": "CANDIDATE",
                    }
                ],
                "required_checks": required_checks,
                "release_policy": {
                    "technical_verification_is_not_release": True,
                    "approved_hash_required": True,
                    "human_gate": "G7",
                },
            }
        ),
        encoding="utf-8",
    )
    work_order_path = project / "work_order.json"
    work_order_path.write_text(
        json.dumps(
            {
                "schema_id": "dbx.work_order",
                "schema_version": "1.1",
                "work_order_id": "WO-TEST-001",
                "project_id": "DBX-TEST",
                "objective": "Repair and verify one workbook without releasing it",
                "candidate_path": "candidate.xlsx",
                "candidate_local_path": str(candidate),
                "template_path": str(template),
                "template_expected_sha256": _sha256(template),
                "profile_path": str(profile),
                "profile_expected_sha256": _sha256(profile),
                "staging_root": str(root / "runs"),
                "acceptance_tests": required_checks,
                "allowed_repairs": allowed_repairs or [],
                "constraints": {"edit_originals": False},
                "retry_policy": {
                    "max_attempts_per_defect": 3,
                    "stop_on_regression": True,
                },
                "promotion": {"require_human_approval": True},
            }
        ),
        encoding="utf-8",
    )
    return manifest_path, work_order_path, profile


def test_control_files_bind_work_order_to_manifest_candidate(tmp_path):
    candidate = tmp_path / "candidate.xlsx"
    template = tmp_path / "template.xlsx"
    _make_workbook(candidate)
    _make_workbook(template)
    manifest_path, work_order_path, _ = _write_controls(
        tmp_path, candidate, template
    )

    manifest = load_project_manifest(manifest_path)
    order = load_work_order(work_order_path, manifest)

    assert order.project_id == manifest.project_id
    assert order.expected_sha256 == _sha256(candidate)
    assert order.require_human_approval


def test_legacy_manifest_schema_requires_explicit_migration(tmp_path):
    candidate = tmp_path / "candidate.xlsx"
    template = tmp_path / "template.xlsx"
    _make_workbook(candidate)
    _make_workbook(template)
    manifest_path, _, _ = _write_controls(tmp_path, candidate, template)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["schema_version"] = "1.0"
    manifest_path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ControlFileError, match="expected 1.1"):
        load_project_manifest(manifest_path)


def test_legacy_work_order_schema_requires_explicit_migration(tmp_path):
    candidate = tmp_path / "candidate.xlsx"
    template = tmp_path / "template.xlsx"
    _make_workbook(candidate)
    _make_workbook(template)
    manifest_path, work_order_path, _ = _write_controls(
        tmp_path, candidate, template
    )
    data = json.loads(work_order_path.read_text(encoding="utf-8"))
    data["schema_version"] = "1.0"
    work_order_path.write_text(json.dumps(data), encoding="utf-8")

    manifest = load_project_manifest(manifest_path)
    with pytest.raises(ControlFileError, match="expected 1.1"):
        load_work_order(work_order_path, manifest)


def test_work_order_cannot_disable_human_approval(tmp_path):
    candidate = tmp_path / "candidate.xlsx"
    template = tmp_path / "template.xlsx"
    _make_workbook(candidate)
    _make_workbook(template)
    manifest_path, work_order_path, _ = _write_controls(
        tmp_path, candidate, template
    )
    data = json.loads(work_order_path.read_text(encoding="utf-8"))
    data["promotion"]["require_human_approval"] = False
    work_order_path.write_text(json.dumps(data), encoding="utf-8")

    manifest = load_project_manifest(manifest_path)
    with pytest.raises(
        ControlFileError, match="human approval cannot be disabled"
    ):
        load_work_order(work_order_path, manifest)


def test_work_order_cannot_omit_manifest_checks(tmp_path):
    candidate = tmp_path / "candidate.xlsx"
    template = tmp_path / "template.xlsx"
    _make_workbook(candidate)
    _make_workbook(template)
    manifest_path, work_order_path, _ = _write_controls(
        tmp_path, candidate, template
    )
    data = json.loads(work_order_path.read_text(encoding="utf-8"))
    data["acceptance_tests"].remove("ownership_totals")
    work_order_path.write_text(json.dumps(data), encoding="utf-8")

    manifest = load_project_manifest(manifest_path)
    with pytest.raises(ControlFileError, match="must exactly match"):
        load_work_order(work_order_path, manifest)


def test_work_order_cannot_self_authorize_a_substituted_profile(tmp_path):
    candidate = tmp_path / "candidate.xlsx"
    template = tmp_path / "template.xlsx"
    _make_workbook(candidate)
    _make_workbook(template)
    manifest_path, work_order_path, profile_path = _write_controls(
        tmp_path, candidate, template
    )
    profile_path.write_text("{}", encoding="utf-8")
    data = json.loads(work_order_path.read_text(encoding="utf-8"))
    data["profile_expected_sha256"] = _sha256(profile_path)
    work_order_path.write_text(json.dumps(data), encoding="utf-8")

    manifest = load_project_manifest(manifest_path)
    with pytest.raises(
        ControlFileError,
        match="profile_expected_sha256 differs from manifest authority",
    ):
        load_work_order(work_order_path, manifest)


@pytest.mark.parametrize(
    ("path_field", "hash_field", "error"),
    [
        (
            "template_path",
            "template_expected_sha256",
            "template_path is required by the manifest authority",
        ),
        (
            "profile_path",
            "profile_expected_sha256",
            "profile_path is required by the manifest authority",
        ),
    ],
)
def test_work_order_cannot_omit_manifest_authority(
    tmp_path, path_field, hash_field, error
):
    candidate = tmp_path / "candidate.xlsx"
    template = tmp_path / "template.xlsx"
    _make_workbook(candidate)
    _make_workbook(template)
    manifest_path, work_order_path, _ = _write_controls(
        tmp_path, candidate, template
    )
    data = json.loads(work_order_path.read_text(encoding="utf-8"))
    data.pop(path_field)
    data.pop(hash_field)
    work_order_path.write_text(json.dumps(data), encoding="utf-8")

    manifest = load_project_manifest(manifest_path)
    with pytest.raises(ControlFileError, match=error):
        load_work_order(work_order_path, manifest)


def test_deterministic_qa_reports_rule_based_failures(tmp_path):
    candidate = tmp_path / "candidate.xlsx"
    template = tmp_path / "template.xlsx"
    _make_workbook(candidate, formula="=#REF!")
    _make_workbook(template)
    manifest_path, work_order_path, profile_path = _write_controls(
        tmp_path, candidate, template
    )
    manifest = load_project_manifest(manifest_path)
    order = load_work_order(work_order_path, manifest)
    profile = json.loads(profile_path.read_text(encoding="utf-8"))

    report = inspect_workbook(
        candidate,
        order.acceptance_tests,
        template_path=template,
        profile=profile,
    )

    formula_check = next(
        check for check in report.checks if check.check_id == "no_broken_formulas"
    )
    assert not formula_check.passed
    assert formula_check.findings[0].cell == "B4"
    assert formula_check.findings[0].repairable
    assert report.score.mathematical_accuracy == 100
    assert not report.score.technical_pass
    assert not report.score.promotion_ready


def test_uncalculated_formula_is_blocking(tmp_path):
    candidate = tmp_path / "candidate.xlsx"
    template = tmp_path / "template.xlsx"
    _make_workbook(candidate, cache_formula=False)
    _make_workbook(template)
    manifest_path, work_order_path, profile_path = _write_controls(
        tmp_path, candidate, template
    )
    manifest = load_project_manifest(manifest_path)
    order = load_work_order(work_order_path, manifest)
    profile = json.loads(profile_path.read_text(encoding="utf-8"))

    report = inspect_workbook(
        candidate,
        order.acceptance_tests,
        template_path=template,
        profile=profile,
    )

    formula_check = next(
        check for check in report.checks if check.check_id == "no_broken_formulas"
    )
    assert formula_check.status == "failed"
    assert formula_check.findings[0].code == "formula_not_calculated"
    assert not report.score.technical_pass


def test_template_formula_replaced_by_constant_is_blocking(tmp_path):
    candidate = tmp_path / "candidate.xlsx"
    template = tmp_path / "template.xlsx"
    _make_workbook(candidate)
    _make_workbook(template)
    workbook = openpyxl.load_workbook(candidate)
    workbook["Title"]["B4"] = 40
    workbook.save(candidate)
    workbook.close()
    manifest_path, work_order_path, profile_path = _write_controls(
        tmp_path, candidate, template
    )
    manifest = load_project_manifest(manifest_path)
    order = load_work_order(work_order_path, manifest)
    profile = json.loads(profile_path.read_text(encoding="utf-8"))

    report = inspect_workbook(
        candidate,
        order.acceptance_tests,
        template_path=template,
        profile=profile,
    )

    formula_check = next(
        check for check in report.checks if check.check_id == "no_broken_formulas"
    )
    assert formula_check.findings[0].code == "authoritative_formula_mismatch"
    assert not report.score.technical_pass


def test_nan_total_cannot_pass_assertion(tmp_path):
    candidate = tmp_path / "candidate.xlsx"
    template = tmp_path / "template.xlsx"
    _make_workbook(candidate)
    _make_workbook(template)
    workbook = openpyxl.load_workbook(candidate)
    workbook["Title"]["D2"] = "NaN"
    workbook.save(candidate)
    workbook.close()
    _set_cached_value(candidate, "B4", 40)
    manifest_path, work_order_path, profile_path = _write_controls(
        tmp_path, candidate, template
    )
    manifest = load_project_manifest(manifest_path)
    order = load_work_order(work_order_path, manifest)
    profile = json.loads(profile_path.read_text(encoding="utf-8"))

    report = inspect_workbook(
        candidate,
        order.acceptance_tests,
        template_path=template,
        profile=profile,
    )

    totals = next(
        check for check in report.checks if check.check_id == "ownership_totals"
    )
    assert totals.status == "failed"
    assert totals.findings[0].code == "total_out_of_tolerance"


def test_loop_repairs_staging_only_then_requires_recalculation(tmp_path):
    candidate = tmp_path / "candidate.xlsx"
    template = tmp_path / "template.xlsx"
    _make_workbook(candidate, formula="=#REF!")
    _make_workbook(template)
    original_bytes = candidate.read_bytes()
    manifest_path, work_order_path, _ = _write_controls(
        tmp_path,
        candidate,
        template,
        allowed_repairs=["restore_formula_from_template"],
    )

    result = ControlledWorkbookLoop.from_files(
        manifest_path, work_order_path
    ).run()

    assert result.status == "blocked"
    assert result.attempts == 1
    assert candidate.read_bytes() == original_bytes
    assert result.staged_workbook is not None
    repaired = openpyxl.load_workbook(result.staged_workbook, data_only=False)
    assert repaired["Title"]["B4"].value == "=SUM(B2:B3)"
    repaired.close()

    receipt = json.loads(result.receipt_path.read_text(encoding="utf-8"))
    assert receipt["input"]["actual_sha256"] == _sha256(candidate)
    assert receipt["output"]["sha256"] == _sha256(result.staged_workbook)
    assert receipt["human_approval_required"] is True
    assert receipt["promotion_executed"] is False
    assert result.promotion_package is None
    assert receipt["authorities"]["template"]["sha256"] == _sha256(template)
    assert receipt["authorities"]["profile"]["sha256"] == _sha256(
        tmp_path / "project" / "workbook_profile.json"
    )


def test_clean_loop_stops_at_hash_bound_human_gate(tmp_path):
    candidate = tmp_path / "candidate.xlsx"
    template = tmp_path / "template.xlsx"
    _make_workbook(candidate)
    _make_workbook(template)
    manifest_path, work_order_path, _ = _write_controls(
        tmp_path, candidate, template
    )

    result = ControlledWorkbookLoop.from_files(
        manifest_path, work_order_path
    ).run()

    assert result.status == "technically_verified_pending_approval"
    assert result.promotion_package is not None
    receipt = json.loads(result.receipt_path.read_text(encoding="utf-8"))
    package = json.loads(result.promotion_package.read_text(encoding="utf-8"))
    assert package["status"] == "PENDING_HUMAN_APPROVAL"
    assert package["approval_must_name_sha256"] == receipt["output"]["sha256"]
    assert package["promotion_executed"] is False


ABSTRACT_CHECKS = [
    "abstract_required_fields",
    "abstract_counts",
    "abstract_key_reconciliation",
    "abstract_print_layout",
]
ABSTRACT_HEADERS = [
    "Instrument Number",
    "Document Type",
    "Grantor",
    "Grantee",
    "Recorded Date",
    "Legal Description",
]
ABSTRACT_ROWS = [
    ["2024-001", "Mineral Deed", "A", "B", "2024-01-02", "Section 15"],
    ["2024-002", "Assignment", "B", "C", "2024-02-03", "Section 15"],
]


def _make_abstract_workbook(path: Path) -> None:
    workbook = openpyxl.Workbook()
    master = workbook.active
    master.title = "Master"
    index = workbook.create_sheet("Index")
    for worksheet in (master, index):
        worksheet.append(ABSTRACT_HEADERS)
        for row in ABSTRACT_ROWS:
            worksheet.append(row)
        worksheet.page_setup.orientation = "landscape"
        worksheet.page_setup.paperSize = worksheet.PAPERSIZE_LETTER
        worksheet.page_setup.fitToWidth = 1
        worksheet.page_setup.fitToHeight = 0
        worksheet.sheet_properties.pageSetUpPr.fitToPage = True
        worksheet.print_area = "A1:F3"
        worksheet.print_title_rows = "1:1"
        worksheet.freeze_panes = "A2"
    workbook.save(path)
    workbook.close()


def _abstract_profile(expected_rows: int = 2) -> dict:
    def table(table_id: str, sheet: str) -> dict:
        return {
            "id": table_id,
            "sheet": sheet,
            "header_row": 1,
            "start_row": 2,
            "key_field": "instrument_number",
            "key_normalization": "alnum_upper",
            "columns": {
                "instrument_number": "A",
                "document_type": "B",
                "grantor": "C",
                "grantee": "D",
                "recorded_date": "E",
                "legal_description": "F",
            },
            "required_fields": [
                "instrument_number",
                "document_type",
                "grantor",
                "grantee",
                "recorded_date",
                "legal_description",
            ],
            "expected_rows": expected_rows,
            "expected_unique_keys": expected_rows,
        }

    return {
        "abstract_tables": [
            table("master", "Master"),
            table("index", "Index"),
        ],
        "abstract_key_reconciliations": [
            {
                "left_table": "master",
                "right_table": "index",
                "mode": "exact",
            }
        ],
        "abstract_print_layout": [
            {
                "sheet": sheet,
                "orientation": "landscape",
                "paper_size": 1,
                "fit_to_width": 1,
                "fit_to_height": 0,
                "fit_to_page": True,
                "print_area": "$A$1:$F$3",
                "print_title_rows": "$1:$1",
                "freeze_panes": "A2",
            }
            for sheet in ("Master", "Index")
        ],
    }


def test_controlled_loop_runs_all_abstract_gates_before_human_gate(tmp_path):
    candidate = tmp_path / "candidate.xlsx"
    template = tmp_path / "template.xlsx"
    _make_abstract_workbook(candidate)
    _make_abstract_workbook(template)
    manifest_path, work_order_path, _ = _write_controls(
        tmp_path,
        candidate,
        template,
        profile_data=_abstract_profile(),
        required_checks=[*ABSTRACT_CHECKS, "human_landman_release"],
    )

    result = ControlledWorkbookLoop.from_files(
        manifest_path, work_order_path
    ).run()

    assert result.status == "technically_verified_pending_approval"
    assert result.promotion_package is not None
    qa_after = json.loads(
        (result.run_directory / "qa_after.json").read_text(encoding="utf-8")
    )
    by_id = {check["check_id"]: check for check in qa_after["checks"]}
    assert all(
        by_id[check_id]["status"] == "passed" for check_id in ABSTRACT_CHECKS
    )
    assert by_id["human_landman_release"]["status"] == "pending_approval"


def test_controlled_loop_blocks_abstract_count_mismatch_without_repair(tmp_path):
    candidate = tmp_path / "candidate.xlsx"
    template = tmp_path / "template.xlsx"
    _make_abstract_workbook(candidate)
    _make_abstract_workbook(template)
    manifest_path, work_order_path, _ = _write_controls(
        tmp_path,
        candidate,
        template,
        profile_data=_abstract_profile(expected_rows=3),
        required_checks=[*ABSTRACT_CHECKS, "human_landman_release"],
    )

    result = ControlledWorkbookLoop.from_files(
        manifest_path, work_order_path
    ).run()

    assert result.status == "blocked"
    assert result.promotion_package is None
    assert result.staged_workbook is not None
    assert _sha256(result.staged_workbook) == _sha256(candidate)


def test_controlled_loop_blocks_missing_abstract_profile_rules(tmp_path):
    candidate = tmp_path / "candidate.xlsx"
    template = tmp_path / "template.xlsx"
    _make_abstract_workbook(candidate)
    _make_abstract_workbook(template)
    manifest_path, work_order_path, _ = _write_controls(
        tmp_path,
        candidate,
        template,
        profile_data={},
        required_checks=[*ABSTRACT_CHECKS, "human_landman_release"],
    )

    result = ControlledWorkbookLoop.from_files(
        manifest_path, work_order_path
    ).run()

    assert result.status == "blocked"
    qa_after = json.loads(
        (result.run_directory / "qa_after.json").read_text(encoding="utf-8")
    )
    by_id = {check["check_id"]: check for check in qa_after["checks"]}
    assert all(
        by_id[check_id]["status"] == "not_evaluated"
        for check_id in ABSTRACT_CHECKS
    )


def test_hash_mismatch_fails_before_copy_and_writes_receipt(tmp_path):
    candidate = tmp_path / "candidate.xlsx"
    template = tmp_path / "template.xlsx"
    _make_workbook(candidate)
    _make_workbook(template)
    manifest_path, work_order_path, _ = _write_controls(
        tmp_path,
        candidate,
        template,
        candidate_hash="0" * 64,
    )

    result = ControlledWorkbookLoop.from_files(
        manifest_path, work_order_path
    ).run()

    assert result.status == "failed"
    assert result.staged_workbook is None
    receipt = json.loads(result.receipt_path.read_text(encoding="utf-8"))
    assert receipt["error_type"] == "ControlFileError"
    assert "hash mismatch" in receipt["error"].lower()
    assert receipt["promotion_executed"] is False
