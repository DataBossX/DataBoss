"""Human-release token and fail-closed package completion."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from horizon.human_release import (
    OWNER_REVIEW_STATEMENT,
    HumanReleaseError,
    assess_human_release,
    evaluate_package_completion,
    write_human_release_token,
)
from horizon.isolated_delta import sha256_file
from horizon.package_finish import run_finish


def _token(workbook_sha: str, **overrides: object) -> dict[str, object]:
    payload = {
        "schema_id": "dbx.human_release_token",
        "schema_version": "1.0",
        "packet_id": "SYNTH-RELEASE",
        "sections": [15],
        "operator": "SYNTH OPERATOR",
        "workbook_sha256": workbook_sha,
        "statement": OWNER_REVIEW_STATEMENT,
        "external_release": False,
    }
    payload.update(overrides)
    return payload


def _gate(name: str, passed: bool = True, **detail: object) -> SimpleNamespace:
    return SimpleNamespace(
        name=name,
        ran=True,
        technical_pass=passed,
        detail=detail,
        error="",
    )


def test_owner_review_token_passes_and_forbids_promotion(tmp_path) -> None:
    workbook = tmp_path / "isolated.xlsx"
    workbook.write_bytes(b"SYNTH")
    digest = sha256_file(workbook)
    ok = assess_human_release(
        _token(digest),
        workbook=workbook,
        requested_sections=[15],
    )
    assert ok.technical_pass is True
    with pytest.raises(HumanReleaseError, match="invalid top-level"):
        assess_human_release(_token(digest, extra=True))
    promoted = assess_human_release(
        _token(
            digest,
            statement="READY_TO_SUBMIT for EXTERNAL_RELEASE",
            external_release=True,
        ),
        workbook=workbook,
        requested_sections=[15],
    )
    assert promoted.technical_pass is False
    assert any("external_release" in issue for issue in promoted.issues)


def test_completion_requires_every_required_gate() -> None:
    complete, missing = evaluate_package_completion([], requested_sections=[15])
    assert complete is False
    assert any("source_acquisition" in item for item in missing)

    gates = [
        _gate("source_acquisition"),
        _gate("reextraction"),
        _gate("occurrence_ledger"),
        _gate("index_reconciliation", blank_required_count=0, conflict_count=0),
        _gate("workbook_qa"),
        _gate("native_print"),
        _gate("drive_readback"),
        _gate("human_release"),
    ]
    complete, missing = evaluate_package_completion(gates, requested_sections=[15])
    assert complete is True
    assert missing == []

    gates[-2] = _gate("drive_readback", passed=False)
    complete, missing = evaluate_package_completion(gates, requested_sections=[15])
    assert complete is False
    assert any("drive_readback" in item for item in missing)


def test_repair_loop_can_satisfy_index_fields() -> None:
    gates = [
        _gate("source_acquisition"),
        _gate("reextraction"),
        _gate("occurrence_ledger"),
        _gate("repair_loop", remaining_blanks=0, remaining_conflicts=0),
        _gate("workbook_qa"),
        _gate("native_print"),
        _gate("drive_readback"),
        _gate("human_release"),
    ]
    complete, missing = evaluate_package_completion(gates, requested_sections=[15])
    assert complete is True
    assert missing == []
    gates[3] = _gate("repair_loop", remaining_blanks=2, remaining_conflicts=0)
    complete, _ = evaluate_package_completion(gates, requested_sections=[15])
    assert complete is False


def test_write_human_release_token_is_owner_review_only(tmp_path) -> None:
    workbook = tmp_path / "isolated.xlsx"
    workbook.write_bytes(b"SYNTH")
    output = tmp_path / "owner-review.json"
    token = write_human_release_token(
        workbook=workbook,
        output=output,
        operator="Pat Examiner",
        sections=[15],
        packet_id="SECTION15-OWNER-REVIEW",
    )
    assert token["external_release"] is False
    assert token["statement"] == OWNER_REVIEW_STATEMENT
    assert token["workbook_sha256"] == sha256_file(workbook)
    assert assess_human_release(
        token, workbook=workbook, requested_sections=[15]
    ).technical_pass
    with pytest.raises(HumanReleaseError, match="named examiner"):
        write_human_release_token(
            workbook=workbook,
            output=tmp_path / "bad.json",
            operator="EXAMINER_NAME",
            sections=[15],
            packet_id="SECTION15-OWNER-REVIEW",
        )


def test_finish_runner_stays_incomplete_without_full_evidence() -> None:
    receipt = run_finish(sections=[15, 13, 11])
    assert receipt.packages_complete is False
    assert any("human_release" in action for action in receipt.next_actions)
    assert any("required gate" in action for action in receipt.next_actions)
