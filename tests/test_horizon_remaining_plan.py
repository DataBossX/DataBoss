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
    bundle = json.loads((receipts / "remaining-plan.json").read_text(encoding="utf-8"))
    assert bundle["schema_id"] == "dbx.remaining_plan_bundle"
    assert [item["section"] for item in bundle["sections"]] == [15, 13, 11]
    assert bundle["packages_complete"] is False
    assert any("remaining-plan.json" in action for action in receipt.next_actions)
    write_remaining_plan_bundle(bundle["sections"], tmp_path / "copy.json")
    copied = json.loads((tmp_path / "copy.json").read_text(encoding="utf-8"))
    assert copied["priority_sections"] == [15, 13, 11]
