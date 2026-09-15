"""Remaining-gates plans report unfinished gates; they do not invent facts."""

from __future__ import annotations

import json
from pathlib import Path

from horizon.isolated_delta import sha256_file
from horizon.remaining_plan import remaining_plan, write_remaining_plan_bundle
from horizon.pc_operator import build_work_order


def _green_finish(letter: Path) -> dict[str, object]:
    digest = sha256_file(letter)
    return {
        "schema_id": "dbx.package_finish_receipt",
        "gates": [
            {
                "name": name,
                "ran": True,
                "technical_pass": True,
                "detail": (
                    {"isolated_copy": True, "workbook_sha256": digest}
                    if name == "drive_readback"
                    else (
                        {
                            "blank_required_count": 0,
                            "conflict_count": 0,
                            "candidate_from": "workbook",
                            "workbook_sha256": digest,
                        }
                        if name == "index_reconciliation"
                        else (
                            {"workbook_sha256": digest}
                            if name
                            in {"workbook_qa", "native_print", "human_release"}
                            else {}
                        )
                    )
                ),
            }
            for name in (
                "source_acquisition",
                "reextraction",
                "occurrence_ledger",
                "index_reconciliation",
                "workbook_qa",
                "native_print",
                "drive_readback",
                "human_release",
            )
        ],
    }


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
    assert plan["open_queues"]["examiner_queue"] == "section15-examiner-queue.json"
    assert "onesource_template" not in plan["open_queues"]
    assert str(tmp_path) not in json.dumps(plan["open_queues"])
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
    assert plan["schema_version"] == "1.5"
    assert plan["missing_required_roles"] == ["index", "handwritten_index"]
    assert plan["unauthorized_classified_roles"] == []
    assert "missing required role index" in plan["missing"]
    assert "missing required role handwritten_index" in plan["missing"]
    assert plan["packages_complete"] is False
    assert "legal" not in json.dumps(plan["missing"])


def test_remaining_plan_names_classified_roles_awaiting_phase2(
    tmp_path: Path,
) -> None:
    plan = remaining_plan(
        section=15,
        finish=None,
        receipt_dir=tmp_path,
        missing_required_roles=["index", "handwritten_index"],
        missing_candidate_roles=[],
        unauthorized_classified_roles=["index", "handwritten_index"],
    )
    assert plan["schema_version"] == "1.5"
    assert plan["unauthorized_classified_roles"] == [
        "index",
        "handwritten_index",
    ]
    assert (
        "required role index is classified but not Phase-2 authorized"
        in plan["missing"]
    )
    assert "missing required role index" not in plan["missing"]
    assert any("authority_promote" in item for item in plan["missing"])
    assert plan["next_commands"][0].startswith(
        "Promote classified files with horizon.authority_promote "
        "--confirm-section 15"
    )
    assert plan["packages_complete"] is False


def test_remaining_plan_prefers_phase2_finish_over_stale_unauthorized(
    tmp_path: Path,
) -> None:
    finish = {
        "schema_id": "dbx.package_finish_receipt",
        "gates": [
            {
                "name": "source_acquisition",
                "ran": True,
                "technical_pass": True,
                "detail": {
                    "phase": "phase2_snapshot",
                    "sections": [
                        {
                            "section": 15,
                            "ready_for_extraction": True,
                            "missing_required_roles": [],
                        }
                    ],
                },
            }
        ],
    }
    plan = remaining_plan(
        section=15,
        finish=finish,
        receipt_dir=tmp_path,
        missing_required_roles=["index", "handwritten_index"],
        missing_candidate_roles=[],
        unauthorized_classified_roles=["index", "handwritten_index"],
    )
    assert plan["missing_required_roles"] == []
    assert plan["unauthorized_classified_roles"] == []
    assert "missing required role index" not in plan["missing"]
    assert "Phase-2 authorized" not in "".join(plan["missing"])
    assert not any("authority_promote" in item for item in plan["missing"])
    assert not any("authority_promote" in item for item in plan["next_commands"])


def test_remaining_plan_separates_missing_files_from_unauthorized_roles(
    tmp_path: Path,
) -> None:
    plan = remaining_plan(
        section=15,
        finish=None,
        receipt_dir=tmp_path,
        missing_required_roles=["index", "handwritten_index"],
        missing_candidate_roles=["handwritten_index"],
        unauthorized_classified_roles=["index"],
    )
    assert plan["schema_version"] == "1.5"
    assert plan["unauthorized_classified_roles"] == ["index"]
    assert (
        "required role index is classified but not Phase-2 authorized"
        in plan["missing"]
    )
    assert "missing required role handwritten_index" in plan["missing"]
    assert "missing required role index" not in plan["missing"]
    assert (
        "required role handwritten_index is classified but not Phase-2 authorized"
        not in plan["missing"]
    )
    assert any("authority_promote" in item for item in plan["missing"])


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


def test_remaining_plan_queue_blanks_block_completion_when_finish_gates_pass(
    tmp_path: Path,
) -> None:
    letter = tmp_path / "section15-letter.xlsx"
    letter.write_bytes(b"SYNTH-LETTER")
    queue = tmp_path / "section15-examiner-queue.json"
    queue.write_text(
        json.dumps(
            {
                "schema_id": "dbx.examiner_fill_queue",
                "schema_version": "1.0",
                "workbook_sha256": sha256_file(letter),
                "blank_count": 2,
                "conflict_count": 0,
            }
        ),
        encoding="utf-8",
    )
    plan = remaining_plan(
        section=15,
        finish=_green_finish(letter),
        receipt_dir=tmp_path,
        isolated_workbook=letter,
    )
    assert plan["packages_complete"] is False
    assert "index has 2 blank required field(s)" in plan["missing"]
    assert "Print Preview section15-letter.xlsx on Windows Excel" not in plan["missing"]
    assert (
        "Copy section15-letter.xlsx into Drive Section 15/Isolated/"
        not in plan["missing"]
    )
    assert "Attest owner-review of section15-letter.xlsx" not in plan["missing"]


def test_remaining_plan_leftover_unhashed_examiner_queue_does_not_apply_counts(
    tmp_path: Path,
) -> None:
    letter = tmp_path / "section15-letter.xlsx"
    letter.write_bytes(b"SYNTH-LETTER")
    queue = tmp_path / "section15-examiner-queue.json"
    queue.write_text(
        json.dumps(
            {
                "schema_id": "dbx.examiner_fill_queue",
                "schema_version": "1.0",
                "blank_count": 99,
                "conflict_count": 0,
            }
        ),
        encoding="utf-8",
    )
    plan = remaining_plan(
        section=15,
        finish=_green_finish(letter),
        receipt_dir=tmp_path,
        isolated_workbook=letter,
    )
    assert plan["packages_complete"] is False
    assert "index has 99 blank required field(s)" not in plan["missing"]
    assert "examiner queue is missing a workbook hash" in plan["missing"]
    assert "examiner queue is bound to a different workbook" not in plan["missing"]


def test_remaining_plan_leftover_current_empty_queue_ignores_stale_hash_gap(
    tmp_path: Path,
) -> None:
    letter = tmp_path / "section15-letter.xlsx"
    letter.write_bytes(b"SYNTH-LETTER")
    digest = sha256_file(letter)
    (tmp_path / "section15-examiner-queue.json").write_text(
        json.dumps(
            {
                "schema_id": "dbx.examiner_fill_queue",
                "packet_id": "SECTION15-EXAMINER",
                "workbook_sha256": "0" * 64,
                "blank_count": 0,
                "conflict_count": 0,
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "aaa-p15-examiner-queue.json").write_text(
        json.dumps(
            {
                "schema_id": "dbx.examiner_fill_queue",
                "packet_id": "SECTION15-EXAMINER",
                "workbook_sha256": digest,
                "blank_count": 0,
                "conflict_count": 0,
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "section15-onesource-template.json").write_text(
        json.dumps(
            {
                "schema_id": "dbx.source_proved_delta_template",
                "status": "UNAPPROVED_DRAFT",
                "deltas": [{"row_key": "k1", "field": "legal_description", "value": ""}],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "aaa-p15-onesource-template.json").write_text(
        json.dumps(
            {
                "schema_id": "dbx.source_proved_delta_template",
                "packet_id": "SECTION15-ONESOURCE",
                "status": "UNAPPROVED_DRAFT",
                "source_workbook_sha256": digest,
                "deltas": [],
            }
        ),
        encoding="utf-8",
    )
    plan = remaining_plan(
        section=15,
        finish=_green_finish(letter),
        receipt_dir=tmp_path,
        isolated_workbook=letter,
    )
    assert "examiner queue is bound to a different workbook" not in plan["missing"]
    assert "examiner queue is missing a workbook hash" not in plan["missing"]
    assert "onesource template is missing a workbook hash" not in plan["missing"]
    assert "2 one-source row(s) still need writer-held text" not in plan["missing"]
    assert "1 one-source row(s) still need writer-held text" not in plan["missing"]
    assert plan["open_queues"]["examiner_queue"] == "aaa-p15-examiner-queue.json"
    assert plan["open_queues"]["onesource_template"] == "aaa-p15-onesource-template.json"
    assert str(tmp_path) not in json.dumps(plan["open_queues"])
    assert plan["packages_complete"] is True


def test_remaining_plan_scores_leftover_hash_matched_examiner_queue(
    tmp_path: Path,
) -> None:
    letter = tmp_path / "section15-letter.xlsx"
    letter.write_bytes(b"SYNTH-LETTER")
    digest = sha256_file(letter)
    (tmp_path / "section15-examiner-queue.json").write_text(
        json.dumps(
            {
                "schema_id": "dbx.examiner_fill_queue",
                "packet_id": "SECTION15-EXAMINER",
                "workbook_sha256": "0" * 64,
                "blank_count": 0,
                "conflict_count": 0,
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "aaa-p15-examiner-queue.json").write_text(
        json.dumps(
            {
                "schema_id": "dbx.examiner_fill_queue",
                "packet_id": "SECTION15-EXAMINER",
                "workbook_sha256": digest,
                "blank_count": 3,
                "conflict_count": 1,
                "items": [
                    {
                        "field": "legal_description",
                        "action": "source_proved_fill",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    plan = remaining_plan(
        section=15,
        finish=_green_finish(letter),
        receipt_dir=tmp_path,
        isolated_workbook=letter,
    )
    assert plan["packages_complete"] is False
    assert plan["field_gaps"]["blank_required_count"] == 3
    assert plan["field_gaps"]["conflict_count"] == 1
    assert "index has 3 blank required field(s)" in plan["missing"]
    assert "legal_description has 1 blank(s)" in plan["missing"]
    assert plan["open_queues"]["examiner_queue"] == "aaa-p15-examiner-queue.json"
    dumped = json.dumps(plan)
    assert "DO NOT COPY" not in dumped
    assert str(tmp_path) not in json.dumps(plan["open_queues"])


def test_remaining_plan_prefers_conventional_hash_matched_examiner_queue(
    tmp_path: Path,
) -> None:
    letter = tmp_path / "section15-letter.xlsx"
    letter.write_bytes(b"SYNTH-LETTER")
    digest = sha256_file(letter)
    (tmp_path / "aaa-p15-examiner-queue.json").write_text(
        json.dumps(
            {
                "schema_id": "dbx.examiner_fill_queue",
                "packet_id": "SECTION15-EXAMINER",
                "workbook_sha256": digest,
                "blank_count": 99,
                "conflict_count": 0,
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "section15-examiner-queue.json").write_text(
        json.dumps(
            {
                "schema_id": "dbx.examiner_fill_queue",
                "packet_id": "SECTION15-EXAMINER",
                "workbook_sha256": digest,
                "blank_count": 0,
                "conflict_count": 0,
            }
        ),
        encoding="utf-8",
    )
    plan = remaining_plan(
        section=15,
        finish=_green_finish(letter),
        receipt_dir=tmp_path,
        isolated_workbook=letter,
    )
    assert "index has 99 blank required field(s)" not in plan["missing"]
    assert plan["field_gaps"].get("blank_required_count") == 0


def test_remaining_plan_ignores_other_section_leftover_examiner_queue(
    tmp_path: Path,
) -> None:
    letter = tmp_path / "section15-letter.xlsx"
    letter.write_bytes(b"SYNTH-LETTER")
    digest = sha256_file(letter)
    (tmp_path / "aaa-p13-examiner-queue.json").write_text(
        json.dumps(
            {
                "schema_id": "dbx.examiner_fill_queue",
                "packet_id": "SECTION13-EXAMINER",
                "workbook_sha256": digest,
                "blank_count": 7,
                "conflict_count": 0,
            }
        ),
        encoding="utf-8",
    )
    plan = remaining_plan(
        section=15,
        finish=_green_finish(letter),
        receipt_dir=tmp_path,
        isolated_workbook=letter,
    )
    assert "index has 7 blank required field(s)" not in plan["missing"]


def test_remaining_plan_scores_leftover_empty_text_queue(
    tmp_path: Path,
) -> None:
    letter = tmp_path / "section15-letter.xlsx"
    letter.write_bytes(b"SYNTH-LETTER")
    (tmp_path / "aaa-p15-empty-text-queue.json").write_text(
        json.dumps(
            {
                "schema_id": "dbx.empty_text_pdf_queue",
                "packet_id": "SECTION15-EMPTY-TEXT",
                "items": [{"path": "face.pdf"}],
            }
        ),
        encoding="utf-8",
    )
    plan = remaining_plan(
        section=15,
        finish=_green_finish(letter),
        receipt_dir=tmp_path,
        isolated_workbook=letter,
    )
    assert plan["packages_complete"] is False
    assert "1 image-only PDF(s) still have empty extracted text" in plan["missing"]
    dumped = json.dumps(plan)
    assert "face.pdf" not in dumped


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
    letter = tmp_path / "section15-letter.xlsx"
    letter.write_bytes(b"SYNTH-LETTER")
    plan = remaining_plan(
        section=15,
        finish=None,
        receipt_dir=tmp_path,
        isolated_workbook=letter,
    )
    assert plan["schema_version"] == "1.5"
    assert plan["isolated_workbook"]["name"] == "section15-letter.xlsx"
    assert plan["isolated_workbook"]["sha256"] == sha256_file(letter)
    assert "Print Preview section15-letter.xlsx on Windows Excel" in plan["missing"]
    assert (
        "Copy section15-letter.xlsx into Drive Section 15/Isolated/"
        in plan["missing"]
    )
    assert "Attest owner-review of section15-letter.xlsx" in plan["missing"]
    assert "path" not in plan["isolated_workbook"]
    assert str(tmp_path) not in json.dumps(plan["isolated_workbook"])
    assert str(tmp_path) not in "".join(plan["missing"])
    assert "SYNTH-LETTER" not in json.dumps(plan)


def test_remaining_plan_keeps_named_drive_and_review_hops_after_print(
    tmp_path: Path,
) -> None:
    letter = tmp_path / "section15-letter.xlsx"
    letter.write_bytes(b"SYNTH-LETTER")
    finish = {
        "schema_id": "dbx.package_finish_receipt",
        "gates": [
            {
                "name": "native_print",
                "ran": True,
                "technical_pass": True,
                "detail": {"workbook_sha256": sha256_file(letter)},
            }
        ],
    }
    plan = remaining_plan(
        section=15,
        finish=finish,
        receipt_dir=tmp_path,
        isolated_workbook=letter,
    )
    assert "Print Preview section15-letter.xlsx on Windows Excel" not in plan["missing"]
    assert (
        "Copy section15-letter.xlsx into Drive Section 15/Isolated/"
        in plan["missing"]
    )
    assert "Attest owner-review of section15-letter.xlsx" in plan["missing"]
    assert plan["packages_complete"] is False
    assert str(tmp_path) not in "".join(plan["missing"])


def test_remaining_plan_drops_named_drive_and_review_hops_when_those_gates_pass(
    tmp_path: Path,
) -> None:
    letter = tmp_path / "section15-letter.xlsx"
    letter.write_bytes(b"SYNTH-LETTER")
    finish = {
        "schema_id": "dbx.package_finish_receipt",
        "gates": [
            {
                "name": "native_print",
                "ran": True,
                "technical_pass": True,
                "detail": {"workbook_sha256": sha256_file(letter)},
            },
            {
                "name": "drive_readback",
                "ran": True,
                "technical_pass": True,
                "detail": {
                    "isolated_copy": True,
                    "workbook_sha256": sha256_file(letter),
                },
            },
            {
                "name": "human_release",
                "ran": True,
                "technical_pass": True,
                "detail": {"workbook_sha256": sha256_file(letter)},
            },
        ],
    }
    plan = remaining_plan(
        section=15,
        finish=finish,
        receipt_dir=tmp_path,
        isolated_workbook=letter,
    )
    assert "Print Preview section15-letter.xlsx on Windows Excel" not in plan["missing"]
    assert (
        "Copy section15-letter.xlsx into Drive Section 15/Isolated/"
        not in plan["missing"]
    )
    assert "Attest owner-review of section15-letter.xlsx" not in plan["missing"]
    assert plan["isolated_workbook"]["name"] == "section15-letter.xlsx"
    assert plan["packages_complete"] is False


def test_remaining_plan_keeps_isolated_hop_until_drive_isolated_copy(
    tmp_path: Path,
) -> None:
    letter = tmp_path / "section15-letter.xlsx"
    letter.write_bytes(b"SYNTH-LETTER")
    finish = {
        "schema_id": "dbx.package_finish_receipt",
        "gates": [
            {
                "name": "native_print",
                "ran": True,
                "technical_pass": True,
                "detail": {"workbook_sha256": sha256_file(letter)},
            },
            {
                "name": "drive_readback",
                "ran": True,
                "technical_pass": True,
                "detail": {"isolated_copy": False},
            },
            {
                "name": "human_release",
                "ran": True,
                "technical_pass": True,
                "detail": {"workbook_sha256": sha256_file(letter)},
            },
        ],
    }
    plan = remaining_plan(
        section=15,
        finish=finish,
        receipt_dir=tmp_path,
        isolated_workbook=letter,
    )
    assert (
        "Copy section15-letter.xlsx into Drive Section 15/Isolated/"
        in plan["missing"]
    )
    assert "Print Preview section15-letter.xlsx on Windows Excel" not in plan["missing"]
    assert "Attest owner-review of section15-letter.xlsx" not in plan["missing"]
    assert plan["packages_complete"] is False
    assert str(tmp_path) not in "".join(plan["missing"])


def test_remaining_plan_keeps_isolated_hop_when_drive_hash_is_stale(
    tmp_path: Path,
) -> None:
    letter = tmp_path / "section15-letter.xlsx"
    letter.write_bytes(b"SYNTH-LETTER")
    finish = {
        "schema_id": "dbx.package_finish_receipt",
        "gates": [
            {
                "name": "drive_readback",
                "ran": True,
                "technical_pass": True,
                "detail": {
                    "isolated_copy": True,
                    "workbook_sha256": "c" * 64,
                    "readback_sha256": "c" * 64,
                },
            }
        ],
    }
    plan = remaining_plan(
        section=15,
        finish=finish,
        receipt_dir=tmp_path,
        isolated_workbook=letter,
    )
    assert (
        "Copy section15-letter.xlsx into Drive Section 15/Isolated/"
        in plan["missing"]
    )
    assert plan["packages_complete"] is False


def test_remaining_plan_fill_queues_block_completion(
    tmp_path: Path,
) -> None:
    letter = tmp_path / "section15-letter.xlsx"
    letter.write_bytes(b"SYNTH-LETTER")
    (tmp_path / "section15-handwritten-scan-queue.json").write_text(
        json.dumps(
            {
                "schema_id": "dbx.handwritten_scan_queue",
                "items": [{"page": 1, "action": "transcribe_to_penterra"}],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "section15-empty-text-queue.json").write_text(
        json.dumps(
            {
                "schema_id": "dbx.empty_text_pdf_queue",
                "items": [{"action": "face_review"}],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "section15-supporting-record-queue.json").write_text(
        json.dumps(
            {
                "schema_id": "dbx.supporting_record_queue",
                "items": [{"action": "review_only"}],
            }
        ),
        encoding="utf-8",
    )
    plan = remaining_plan(
        section=15,
        finish=_green_finish(letter),
        receipt_dir=tmp_path,
        isolated_workbook=letter,
        holds=["2 chat/OCR file(s) are review-only"],
    )
    assert plan["packages_complete"] is False
    assert "1 handwritten scan(s) still need a Penterra xlsx" in plan["missing"]
    assert "1 image-only PDF(s) still have empty extracted text" in plan["missing"]
    assert "review-only" not in "".join(plan["missing"])
    dumped = json.dumps(plan)
    assert "DO NOT COPY" not in dumped


def test_remaining_plan_crop_fill_queue_blocks_section_11_only(
    tmp_path: Path,
) -> None:
    letter15 = tmp_path / "section15-letter.xlsx"
    letter15.write_bytes(b"SYNTH-LETTER-15")
    letter11 = tmp_path / "section11-letter.xlsx"
    letter11.write_bytes(b"SYNTH-LETTER-11")
    (tmp_path / "section15-crop-fill-queue.json").write_text(
        json.dumps(
            {
                "schema_id": "dbx.crop_fill_queue",
                "packet_id": "SECTION15-CROPS",
                "items": [
                    {"page": 1, "action": "source_proved_fill"},
                    {"page": 2, "action": "source_proved_fill"},
                ],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "section11-crop-fill-queue.json").write_text(
        json.dumps(
            {
                "schema_id": "dbx.crop_fill_queue",
                "packet_id": "SECTION11-CROPS",
                "items": [{"page": 1, "action": "source_proved_fill"}],
            }
        ),
        encoding="utf-8",
    )
    plan15 = remaining_plan(
        section=15,
        finish=_green_finish(letter15),
        receipt_dir=tmp_path,
        isolated_workbook=letter15,
    )
    plan11 = remaining_plan(
        section=11,
        finish=_green_finish(letter11),
        receipt_dir=tmp_path,
        isolated_workbook=letter11,
    )
    assert plan15["packages_complete"] is True
    assert "page-render crop" not in "".join(plan15["missing"])
    assert "crop fill queue" not in "".join(plan15["missing"])
    assert plan11["packages_complete"] is False
    assert "1 page-render crop(s) still need face text" in plan11["missing"]


def test_remaining_plan_other_section_fill_queue_does_not_apply_counts(
    tmp_path: Path,
) -> None:
    letter = tmp_path / "section11-letter.xlsx"
    letter.write_bytes(b"SYNTH-LETTER")
    (tmp_path / "section11-crop-fill-queue.json").write_text(
        json.dumps(
            {
                "schema_id": "dbx.crop_fill_queue",
                "packet_id": "SECTION15-CROPS",
                "items": [
                    {"page": 1, "action": "source_proved_fill"},
                    {"page": 2, "action": "source_proved_fill"},
                ],
            }
        ),
        encoding="utf-8",
    )
    plan = remaining_plan(
        section=11,
        finish=_green_finish(letter),
        receipt_dir=tmp_path,
        isolated_workbook=letter,
    )
    assert plan["packages_complete"] is False
    assert "2 page-render crop(s) still need face text" not in plan["missing"]
    assert "crop fill queue is bound to another section" in plan["missing"]


def test_remaining_plan_leftover_exclusive_queue_ignores_stale_other_section(
    tmp_path: Path,
) -> None:
    letter = tmp_path / "section11-letter.xlsx"
    letter.write_bytes(b"SYNTH-LETTER")
    (tmp_path / "section11-crop-fill-queue.json").write_text(
        json.dumps(
            {
                "schema_id": "dbx.crop_fill_queue",
                "packet_id": "SECTION15-CROPS",
                "items": [
                    {"page": 1, "action": "source_proved_fill"},
                    {"page": 2, "action": "source_proved_fill"},
                ],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "aaa-p11-crop-fill-queue.json").write_text(
        json.dumps(
            {
                "schema_id": "dbx.crop_fill_queue",
                "packet_id": "SECTION11-CROPS",
                "items": [],
            }
        ),
        encoding="utf-8",
    )
    plan = remaining_plan(
        section=11,
        finish=_green_finish(letter),
        receipt_dir=tmp_path,
        isolated_workbook=letter,
    )
    assert "crop fill queue is bound to another section" not in plan["missing"]
    assert "page-render crop" not in "".join(plan["missing"])
    assert plan["open_queues"]["crop_fill_queue"] == "aaa-p11-crop-fill-queue.json"
    assert str(tmp_path) not in json.dumps(plan["open_queues"])
    assert plan["packages_complete"] is True


def test_remaining_plan_supporting_queue_does_not_block_completion(
    tmp_path: Path,
) -> None:
    letter = tmp_path / "section15-letter.xlsx"
    letter.write_bytes(b"SYNTH-LETTER")
    (tmp_path / "section15-supporting-record-queue.json").write_text(
        json.dumps(
            {
                "schema_id": "dbx.supporting_record_queue",
                "items": [{"action": "review_only"}],
            }
        ),
        encoding="utf-8",
    )
    plan = remaining_plan(
        section=15,
        finish=_green_finish(letter),
        receipt_dir=tmp_path,
        isolated_workbook=letter,
        holds=["1 chat/OCR file(s) are review-only"],
    )
    assert plan["packages_complete"] is True
    assert "review-only" not in "".join(plan["missing"])
    assert "crop" not in "".join(plan["missing"])


def test_remaining_plan_requires_isolated_workbook(tmp_path: Path) -> None:
    letter = tmp_path / "section15-letter.xlsx"
    letter.write_bytes(b"SYNTH-LETTER")
    plan = remaining_plan(
        section=15,
        finish=_green_finish(letter),
        receipt_dir=tmp_path,
    )
    assert plan["packages_complete"] is False
    assert plan["isolated_workbook"] == {}
    assert any("isolated workbook hash is required" in item for item in plan["missing"])


def test_remaining_plan_onesource_and_delta_drafts_block_completion(
    tmp_path: Path,
) -> None:
    letter = tmp_path / "section15-letter.xlsx"
    letter.write_bytes(b"SYNTH-LETTER")
    digest = sha256_file(letter)
    (tmp_path / "section15-onesource-template.json").write_text(
        json.dumps(
            {
                "schema_id": "dbx.source_proved_delta_template",
                "status": "UNAPPROVED_DRAFT",
                "source_workbook_sha256": digest,
                "deltas": [
                    {"row_key": "k1", "field": "legal_description", "value": ""},
                    {"row_key": "k2", "field": "recorded_date", "value": ""},
                ],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "section15-delta-draft.json").write_text(
        json.dumps(
            {
                "schema_id": "dbx.source_proved_delta_draft",
                "status": "UNAPPROVED_DRAFT",
                "source_workbook_sha256": digest,
                "deltas": [{"row_key": "k3", "field": "grantor", "value": "x"}],
            }
        ),
        encoding="utf-8",
    )
    plan = remaining_plan(
        section=15,
        finish=_green_finish(letter),
        receipt_dir=tmp_path,
        isolated_workbook=letter,
    )
    assert plan["packages_complete"] is False
    assert "2 one-source row(s) still need writer-held text" in plan["missing"]
    assert "1 source-proved delta(s) still need attest" in plan["missing"]
    dumped = json.dumps(plan)
    assert "DO NOT COPY" not in dumped
    assert "k1" not in dumped


def test_remaining_plan_leftover_unhashed_onesource_does_not_apply_counts(
    tmp_path: Path,
) -> None:
    letter = tmp_path / "section15-letter.xlsx"
    letter.write_bytes(b"SYNTH-LETTER")
    (tmp_path / "section15-onesource-template.json").write_text(
        json.dumps(
            {
                "schema_id": "dbx.source_proved_delta_template",
                "status": "UNAPPROVED_DRAFT",
                "deltas": [
                    {"row_key": "k1", "field": "legal_description", "value": ""},
                    {"row_key": "k2", "field": "recorded_date", "value": ""},
                ],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "section15-delta-draft.json").write_text(
        json.dumps(
            {
                "schema_id": "dbx.source_proved_delta_draft",
                "status": "UNAPPROVED_DRAFT",
                "deltas": [{"row_key": "k3", "field": "grantor", "value": "x"}],
            }
        ),
        encoding="utf-8",
    )
    plan = remaining_plan(
        section=15,
        finish=_green_finish(letter),
        receipt_dir=tmp_path,
        isolated_workbook=letter,
    )
    assert plan["packages_complete"] is False
    assert "2 one-source row(s) still need writer-held text" not in plan["missing"]
    assert "1 source-proved delta(s) still need attest" not in plan["missing"]
    assert "onesource template is missing a workbook hash" in plan["missing"]
    assert "delta draft is missing a workbook hash" in plan["missing"]
    dumped = json.dumps(plan)
    assert "k1" not in dumped
    assert "k3" not in dumped


def test_remaining_plan_ignores_stale_hash_onesource_draft(
    tmp_path: Path,
) -> None:
    letter = tmp_path / "section15-letter.xlsx"
    letter.write_bytes(b"SYNTH-LETTER")
    (tmp_path / "section15-onesource-template.json").write_text(
        json.dumps(
            {
                "schema_id": "dbx.source_proved_delta_template",
                "status": "UNAPPROVED_DRAFT",
                "source_workbook_sha256": "d" * 64,
                "deltas": [
                    {"row_key": "k1", "field": "legal_description", "value": ""},
                ],
            }
        ),
        encoding="utf-8",
    )
    plan = remaining_plan(
        section=15,
        finish=_green_finish(letter),
        receipt_dir=tmp_path,
        isolated_workbook=letter,
    )
    assert plan["packages_complete"] is True
    assert "one-source" not in "".join(plan["missing"])


def test_remaining_plan_keeps_print_hop_when_finish_hash_is_stale(
    tmp_path: Path,
) -> None:
    letter = tmp_path / "section15-letter.xlsx"
    letter.write_bytes(b"SYNTH-LETTER")
    finish = {
        "schema_id": "dbx.package_finish_receipt",
        "gates": [
            {
                "name": "native_print",
                "ran": True,
                "technical_pass": True,
                "detail": {"workbook_sha256": "a" * 64},
            },
            {
                "name": "human_release",
                "ran": True,
                "technical_pass": True,
                "detail": {"workbook_sha256": "b" * 64},
            },
        ],
    }
    plan = remaining_plan(
        section=15,
        finish=finish,
        receipt_dir=tmp_path,
        isolated_workbook=letter,
    )
    assert "Print Preview section15-letter.xlsx on Windows Excel" in plan["missing"]
    assert "Attest owner-review of section15-letter.xlsx" in plan["missing"]
    assert plan["packages_complete"] is False


def test_remaining_plan_keeps_print_hop_when_finish_omits_hash(
    tmp_path: Path,
) -> None:
    letter = tmp_path / "section15-letter.xlsx"
    letter.write_bytes(b"SYNTH-LETTER")
    finish = {
        "schema_id": "dbx.package_finish_receipt",
        "gates": [
            {
                "name": "native_print",
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
        isolated_workbook=letter,
    )
    assert "Print Preview section15-letter.xlsx on Windows Excel" in plan["missing"]
    assert plan["packages_complete"] is False


def test_remaining_plan_holds_stale_repair_and_queue_hashes(
    tmp_path: Path,
) -> None:
    letter = tmp_path / "section15-letter.xlsx"
    letter.write_bytes(b"SYNTH-LETTER")
    digest = sha256_file(letter)
    finish = {
        "schema_id": "dbx.package_finish_receipt",
        "gates": [
            {
                "name": name,
                "ran": True,
                "technical_pass": True,
                "detail": (
                    {
                        "remaining_blanks": 0,
                        "remaining_conflicts": 0,
                        "final_workbook_sha256": "e" * 64,
                    }
                    if name == "repair_loop"
                    else (
                        {"isolated_copy": True, "workbook_sha256": digest}
                        if name == "drive_readback"
                        else (
                            {"workbook_sha256": digest}
                            if name
                            in {"workbook_qa", "native_print", "human_release"}
                            else {}
                        )
                    )
                ),
            }
            for name in (
                "source_acquisition",
                "reextraction",
                "occurrence_ledger",
                "repair_loop",
                "workbook_qa",
                "native_print",
                "drive_readback",
                "human_release",
            )
        ],
    }
    (tmp_path / "section15-examiner-queue.json").write_text(
        json.dumps(
            {
                "schema_id": "dbx.examiner_fill_queue",
                "schema_version": "1.0",
                "workbook_sha256": "e" * 64,
                "blank_count": 0,
                "conflict_count": 0,
            }
        ),
        encoding="utf-8",
    )
    plan = remaining_plan(
        section=15,
        finish=finish,
        receipt_dir=tmp_path,
        isolated_workbook=letter,
    )
    assert plan["schema_version"] == "1.5"
    assert plan["packages_complete"] is False
    assert (
        "repair loop scored a different workbook, not section15-letter.xlsx"
        in plan["missing"]
    )
    assert "examiner queue is bound to a different workbook" in plan["missing"]


def test_remaining_plan_uses_finish_gaps_when_examiner_queue_hash_is_stale(
    tmp_path: Path,
) -> None:
    letter = tmp_path / "section15-letter.xlsx"
    letter.write_bytes(b"SYNTH-LETTER")
    finish = {
        "schema_id": "dbx.package_finish_receipt",
        "gates": [
            {
                "name": "index_reconciliation",
                "ran": True,
                "technical_pass": True,
                "detail": {
                    "blank_required_count": 3,
                    "conflict_count": 1,
                    "candidate_from": "workbook",
                    "workbook_sha256": sha256_file(letter),
                },
            }
        ],
    }
    (tmp_path / "section15-examiner-queue.json").write_text(
        json.dumps(
            {
                "schema_id": "dbx.examiner_fill_queue",
                "schema_version": "1.0",
                "workbook_sha256": "f" * 64,
                "blank_count": 0,
                "conflict_count": 0,
            }
        ),
        encoding="utf-8",
    )
    plan = remaining_plan(
        section=15,
        finish=finish,
        receipt_dir=tmp_path,
        isolated_workbook=letter,
    )
    assert plan["field_gaps"]["blank_required_count"] == 3
    assert plan["field_gaps"]["conflict_count"] == 1
    assert "index has 3 blank required field(s)" in plan["missing"]
    assert "examiner queue is bound to a different workbook" in plan["missing"]
    assert plan["packages_complete"] is False


def test_remaining_plan_holds_recon_without_candidate_from(
    tmp_path: Path,
) -> None:
    letter = tmp_path / "section15-letter.xlsx"
    letter.write_bytes(b"SYNTH-LETTER")
    finish = {
        "schema_id": "dbx.package_finish_receipt",
        "gates": [
            {
                "name": "index_reconciliation",
                "ran": True,
                "technical_pass": True,
                "detail": {
                    "blank_required_count": 0,
                    "conflict_count": 0,
                    "workbook_sha256": sha256_file(letter),
                },
            }
        ],
    }
    plan = remaining_plan(
        section=15,
        finish=finish,
        receipt_dir=tmp_path,
        isolated_workbook=letter,
    )
    assert (
        "index reconciliation did not score section15-letter.xlsx"
        in plan["missing"]
    )
    assert plan["packages_complete"] is False


def test_remaining_plan_requires_recon_on_isolated_workbook(
    tmp_path: Path,
) -> None:
    letter = tmp_path / "section15-letter.xlsx"
    letter.write_bytes(b"SYNTH-LETTER")
    finish = {
        "schema_id": "dbx.package_finish_receipt",
        "gates": [
            {
                "name": "index_reconciliation",
                "ran": True,
                "technical_pass": True,
                "detail": {
                    "candidate_from": "index_packet",
                    "blank_required_count": 0,
                    "conflict_count": 0,
                },
            }
        ],
    }
    plan = remaining_plan(
        section=15,
        finish=finish,
        receipt_dir=tmp_path,
        isolated_workbook=letter,
    )
    assert (
        "index reconciliation scored index_packet, not section15-letter.xlsx"
        in plan["missing"]
    )
    assert plan["packages_complete"] is False


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
    assert bundle["schema_version"] == "1.2"
    assert [item["section"] for item in bundle["sections"]] == [15, 13, 11]
    assert bundle["packages_complete"] is False
    assert bundle["next"]["section"] == 15
    assert isinstance(bundle["next"]["action"], str) and bundle["next"]["action"]
    assert str(tmp_path) not in bundle["next"]["action"]
    assert "/" not in bundle["next"]["action"] or "Isolated/" in bundle["next"]["action"]
    assert bundle["connections"]["packages_complete"] is False
    assert "pc" in {item["label"] for item in bundle["connections"]["roots"]}
    assert any(
        "cursor worker" in action for action in bundle["connections"]["next_actions"]
    )
    assert "path" not in json.dumps(bundle["connections"]["roots"])
    assert any(
        "Review remaining-plan.json and do next first" in action
        for action in receipt.next_actions
    )
    assert any(
        action.startswith("Next (section 15):") for action in receipt.next_actions
    )
    assert not any(str(tmp_path) in action for action in receipt.next_actions if "Next" in action)
    write_remaining_plan_bundle(bundle["sections"], tmp_path / "copy.json")
    copied = json.loads((tmp_path / "copy.json").read_text(encoding="utf-8"))
    assert copied["priority_sections"] == [15, 13, 11]
    assert copied["schema_version"] == "1.2"
    assert copied["next"]["section"] == 15


def test_remaining_plan_bundle_next_is_connection_when_no_roots(
    tmp_path: Path,
) -> None:
    plans = [
        {
            "section": 13,
            "packages_complete": False,
            "missing": ["index has 1 blank required field(s)"],
        },
        {
            "section": 15,
            "packages_complete": False,
            "missing": ["missing required role handwritten_index"],
        },
    ]
    dest = tmp_path / "remaining-plan.json"
    bundle = write_remaining_plan_bundle(
        plans,
        dest,
        connections={
            "connected_root_count": 0,
            "technical_pass": False,
            "next_actions": [
                "Pass --root pc=<abs> and --root drive=<abs> on the machine "
                "that can see section 15/13/11 files",
                "Mount or grant read access to pc=/secret/host/path",
            ],
        },
    )
    assert bundle["schema_version"] == "1.2"
    assert bundle["next"] == {
        "section": None,
        "action": (
            "Pass --root pc=<abs> and --root drive=<abs> on the machine "
            "that can see section 15/13/11 files"
        ),
    }
    assert "/secret/host/path" not in json.dumps(bundle["next"])
    rooted = write_remaining_plan_bundle(
        plans,
        tmp_path / "rooted.json",
        connections={"connected_root_count": 1, "technical_pass": True},
    )
    assert rooted["next"] == {
        "section": 15,
        "action": "missing required role handwritten_index",
    }
