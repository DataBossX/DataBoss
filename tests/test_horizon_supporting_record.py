"""Chat/OCR supporting records are review-only and never legal fills."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from horizon.isolated_delta import sha256_file
from horizon.pc_operator import _discover_json_packets, build_work_order
from horizon.supporting_record import (
    SupportingRecordError,
    supporting_record_queue_from_draft,
    write_supporting_record_draft,
)


def test_supporting_draft_hashes_chat_without_legal_fields(tmp_path: Path) -> None:
    bind = tmp_path / "supporting"
    bind.mkdir()
    chat = bind / "slack-transcript.md"
    chat.write_text("SYNTH CHAT ONLY", encoding="utf-8")
    draft = write_supporting_record_draft(
        output=tmp_path / "draft.json",
        packet_id="SECTION15-SUPPORTING",
        bind_dir=bind,
    )
    assert draft["schema_id"] == "dbx.supporting_record_draft"
    assert draft["status"] == "UNAPPROVED_DRAFT"
    assert draft["files"][0]["path"] == "slack-transcript.md"
    assert draft["files"][0]["role"] == "chat_export"
    assert draft["files"][0]["source_sha256"] == sha256_file(chat)
    queue = supporting_record_queue_from_draft(draft)
    assert queue["schema_id"] == "dbx.supporting_record_queue"
    assert queue["items"][0]["action"] == "review_only"
    assert queue["items"][0]["legal_authority"] is False
    assert "legal" not in queue["items"][0]
    assert "grantor" not in queue["items"][0]
    discovered = _discover_json_packets([tmp_path / "draft.json"])
    assert "delta_packet" not in discovered
    assert "page_render_packet" not in discovered


def test_supporting_draft_rejects_escaped_paths(tmp_path: Path) -> None:
    bind = tmp_path / "supporting"
    bind.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("NOPE", encoding="utf-8")
    with pytest.raises(SupportingRecordError, match="escapes"):
        write_supporting_record_draft(
            output=tmp_path / "draft.json",
            packet_id="SECTION15-SUPPORTING",
            bind_dir=bind,
            paths=[outside],
        )


def test_operator_writes_supporting_queue_from_examiner_dir(tmp_path: Path) -> None:
    root = tmp_path / "pc-root"
    (root / "Section 15").mkdir(parents=True)
    receipts = tmp_path / "private-receipts"
    chats = receipts / "section15-chat"
    chats.mkdir(parents=True)
    page = chats / "notes.txt"
    page.write_text("SYNTH OCR NOTES", encoding="utf-8")
    receipt = build_work_order(
        roots=[f"pc={root}"],
        sections=[15],
        receipt_dir=receipts,
        execute=True,
    )
    assert receipt.packages_complete is False
    draft = json.loads(
        (receipts / "section15-supporting-record-draft.json").read_text(
            encoding="utf-8"
        )
    )
    assert draft["files"][0]["source_sha256"] == sha256_file(page)
    assert draft["files"][0]["role"] == "chat_export"
    queue = json.loads(
        (receipts / "section15-supporting-record-queue.json").read_text(
            encoding="utf-8"
        )
    )
    assert queue["items"][0]["legal_authority"] is False
    assert any("review-only" in hold for hold in receipt.sections[0].holds)
    plan = json.loads(
        (receipts / "section15-remaining-plan.json").read_text(encoding="utf-8")
    )
    assert "supporting_record_queue" in plan["open_queues"]


def test_operator_does_not_hash_phase1_live_chat_exports(tmp_path: Path) -> None:
    root = tmp_path / "pc-root"
    section = root / "Section 15"
    section.mkdir(parents=True)
    (section / "Slack Transcript.md").write_text("LIVE CHAT", encoding="utf-8")
    receipts = tmp_path / "private-receipts"
    receipt = build_work_order(
        roots=[f"pc={root}"],
        sections=[15],
        receipt_dir=receipts,
        execute=True,
    )
    assert receipt.packages_complete is False
    draft = json.loads(
        (receipts / "section15-supporting-record-draft.json").read_text(
            encoding="utf-8"
        )
    )
    assert draft["files"] == []
    assert not (receipts / "section15-supporting-record-queue.json").is_file()
