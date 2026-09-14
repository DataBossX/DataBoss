"""Remaining-gates plans report unfinished gates; they do not invent facts."""

from __future__ import annotations

import json
from pathlib import Path

from horizon.remaining_plan import remaining_plan, write_remaining_plan_bundle
from horizon.pc_operator import build_work_order


def test_remaining_plan_lists_missing_required_gates(tmp_path: Path) -> None:
    finish = {
        "schema_id": "dbx.package_finish_receipt",
        "gates": [
            {
                "name": "connect_status",
                "ran": True,
                "technical_pass": True,
                "detail": {},
            }
        ],
    }
    plan = remaining_plan(
        section=15,
        finish=finish,
        receipt_dir=tmp_path,
        holds=["Hold SRP pull dates"],
        next_commands=["attest native print"],
    )
    assert plan["schema_id"] == "dbx.section_remaining_plan"
    assert plan["packages_complete"] is False
    assert any("native_print" in item for item in plan["missing"])
    assert any("human_release" in item for item in plan["missing"])
    assert plan["holds"] == ["Hold SRP pull dates"]
    assert "legal" not in json.dumps(plan["missing"])


def test_remaining_plan_records_open_queues_only(tmp_path: Path) -> None:
    queue = tmp_path / "section15-examiner-queue.json"
    queue.write_text("{}", encoding="utf-8")
    plan = remaining_plan(
        section=15,
        finish=None,
        receipt_dir=tmp_path,
    )
    assert plan["open_queues"]["examiner_queue"] == str(queue)
    assert "onesource_template" not in plan["open_queues"]
    assert "no finish receipt" in plan["missing"]


def test_remaining_plan_names_missing_index_roles_from_finish(tmp_path: Path) -> None:
    finish = {
        "schema_id": "dbx.package_finish_receipt",
        "gates": [
            {
                "name": "source_acquisition",
                "ran": True,
                "technical_pass": False,
                "detail": {
                    "sections": [
                        {
                            "section": 15,
                            "ready_for_extraction": False,
                            "missing_required_roles": ["index", "handwritten_index"],
                        }
                    ]
                },
            }
        ],
    }
    plan = remaining_plan(section=15, finish=finish, receipt_dir=tmp_path)
    assert plan["schema_version"] == "1.3"
    assert plan["missing_required_roles"] == ["index", "handwritten_index"]
    assert "missing required role index" in plan["missing"]
    assert "missing required role handwritten_index" in plan["missing"]
    assert plan["packages_complete"] is False
    assert "legal" not in json.dumps(plan["missing"])


def test_remaining_plan_names_blank_and_conflict_counts(tmp_path: Path) -> None:
    finish = {
        "schema_id": "dbx.package_finish_receipt",
        "gates": [
            {
                "name": "index_reconciliation",
                "ran": True,
                "technical_pass": False,
                "detail": {
                    "blank_required_count": 3,
                    "conflict_count": 1,
                    "low_confidence_blank_count": 2,
                },
            }
        ],
    }
    plan = remaining_plan(section=13, finish=finish, receipt_dir=tmp_path)
    assert plan["field_gaps"]["blank_required_count"] == 3
    assert plan["field_gaps"]["conflict_count"] == 1
    assert "index has 3 blank required field(s)" in plan["missing"]
    assert "index has 1 conflict(s)" in plan["missing"]
    assert "index has 2 low-confidence blank(s)" in plan["missing"]
    assert "SYNTH" not in json.dumps(plan)


def test_remaining_plan_prefers_examiner_queue_over_stale_finish(
    tmp_path: Path,
) -> None:
    finish = {
        "schema_id": "dbx.package_finish_receipt",
        "gates": [
            {
                "name": "index_reconciliation",
                "ran": True,
                "technical_pass": False,
                "detail": {
                    "blank_required_count": 5,
                    "conflict_count": 2,
                    "low_confidence_blank_count": 1,
                    "candidate_from": "index_packet",
                },
            }
        ],
    }
    queue = tmp_path / "section15-examiner-queue.json"
    queue.write_text(
        json.dumps(
            {
                "schema_id": "dbx.examiner_fill_queue",
                "schema_version": "1.0",
                "blank_count": 0,
                "conflict_count": 0,
            }
        ),
        encoding="utf-8",
    )
    plan = remaining_plan(section=15, finish=finish, receipt_dir=tmp_path)
    assert plan["field_gaps"]["blank_required_count"] == 0
    assert plan["field_gaps"]["conflict_count"] == 0
    assert plan["field_gaps"]["low_confidence_blank_count"] == 1
    assert "index has 5 blank required field(s)" not in plan["missing"]
    assert "index has 2 conflict(s)" not in plan["missing"]


def test_remaining_plan_reads_examiner_queue_counts(tmp_path: Path) -> None:
    queue = tmp_path / "section11-examiner-queue.json"
    queue.write_text(
        json.dumps(
            {
                "schema_id": "dbx.examiner_fill_queue",
                "schema_version": "1.0",
                "blank_count": 4,
                "conflict_count": 0,
            }
        ),
        encoding="utf-8",
    )
    plan = remaining_plan(section=11, finish=None, receipt_dir=tmp_path)
    assert plan["field_gaps"]["blank_required_count"] == 4
    assert "index has 4 blank required field(s)" in plan["missing"]
    assert "conflict" not in "".join(
        item for item in plan["missing"] if "index has" in item
    )


def test_remaining_plan_names_required_fields_without_copying_values(
    tmp_path: Path,
) -> None:
    queue = tmp_path / "section15-examiner-queue.json"
    queue.write_text(
        json.dumps(
            {
                "schema_id": "dbx.examiner_fill_queue",
                "schema_version": "1.0",
                "blank_count": 3,
                "conflict_count": 1,
                "items": [
                    {
                        "field": "legal_description",
                        "action": "source_proved_fill",
                        "candidate_value": "",
                        "proposed_value": "DO NOT COPY THIS LEGAL",
                    },
                    {
                        "field": "legal_description",
                        "action": "proposed_delta_pending",
                        "proposed_value": "ALSO DO NOT COPY",
                    },
                    {
                        "field": "recorded_date",
                        "action": "resolve_conflict",
                        "conflict_values": {"master": "1/1/2020"},
                    },
                    {
                        "field": "grantor",
                        "action": "source_proved_fill",
                    },
                    {
                        "field": "invented_secret",
                        "action": "source_proved_fill",
                        "proposed_value": "CLIENT PARTY NAME",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    plan = remaining_plan(section=15, finish=None, receipt_dir=tmp_path)
    by_field = plan["field_gaps"]["by_field"]
    assert by_field["legal_description"] == {"blank": 2, "conflict": 0}
    assert by_field["recorded_date"] == {"blank": 0, "conflict": 1}
    assert by_field["grantor"] == {"blank": 1, "conflict": 0}
    assert "invented_secret" not in by_field
    assert "legal_description has 2 blank(s)" in plan["missing"]
    assert "recorded_date has 1 conflict(s)" in plan["missing"]
    dumped = json.dumps(plan)
    assert "DO NOT COPY THIS LEGAL" not in dumped
    assert "ALSO DO NOT COPY" not in dumped
    assert "CLIENT PARTY NAME" not in dumped
    assert "1/1/2020" not in dumped


def test_remaining_plan_names_isolated_workbook_without_cell_text(
    tmp_path: Path,
) -> None:
    from horizon.isolated_delta import sha256_file

    letter = tmp_path / "section15-letter.xlsx"
    letter.write_bytes(b"SYNTH-LETTER")
    plan = remaining_plan(
        section=15,
        finish=None,
        receipt_dir=tmp_path,
        isolated_workbook=letter,
    )
    assert plan["schema_version"] == "1.3"
    assert plan["isolated_workbook"]["name"] == "section15-letter.xlsx"
    assert plan["isolated_workbook"]["sha256"] == sha256_file(letter)
    assert "Print Preview section15-letter.xlsx on Windows Excel" in plan["missing"]
    assert "path" not in plan["isolated_workbook"]
    assert str(tmp_path) not in json.dumps(plan["isolated_workbook"])


def test_operator_writes_priority_remaining_plan_bundle(tmp_path: Path) -> None:
    root = tmp_path / "pc-root"
    for section in (15, 13, 11):
        (root / f"Section {section}").mkdir(parents=True)
    receipts = tmp_path / "private-receipts"
    receipt = build_work_order(
        roots=[f"pc={root}"],
        sections=[15, 13, 11],
        receipt_dir=receipts,
        execute=True,
    )
    assert receipt.packages_complete is False
    for section in (15, 13, 11):
        path = receipts / f"section{section}-remaining-plan.json"
        assert path.is_file()
        plan = json.loads(path.read_text(encoding="utf-8"))
        assert plan["section"] == section
        assert plan["packages_complete"] is False
        assert plan["missing"]
        assert "handwritten_index" in plan["missing_required_roles"]
        assert "missing required role handwritten_index" in plan["missing"]
        assert "missing required role index" in plan["missing"]
    bundle = json.loads((receipts / "remaining-plan.json").read_text(encoding="utf-8"))
    assert bundle["schema_id"] == "dbx.remaining_plan_bundle"
    assert bundle["schema_version"] == "1.1"
    assert [item["section"] for item in bundle["sections"]] == [15, 13, 11]
    assert bundle["packages_complete"] is False
    assert bundle["connections"]["packages_complete"] is False
    assert "pc" in {item["label"] for item in bundle["connections"]["roots"]}
    assert any(
        "cursor worker" in action for action in bundle["connections"]["next_actions"]
    )
    assert "path" not in json.dumps(bundle["connections"]["roots"])
    assert any("remaining-plan.json" in action for action in receipt.next_actions)
    write_remaining_plan_bundle(bundle["sections"], tmp_path / "copy.json")
    copied = json.loads((tmp_path / "copy.json").read_text(encoding="utf-8"))
    assert copied["priority_sections"] == [15, 13, 11]
