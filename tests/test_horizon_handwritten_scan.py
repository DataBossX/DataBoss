"""Handwritten-scan drafts hash faces; they do not invent index rows."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from horizon.handwritten_scan import (
    HandwrittenScanError,
    handwritten_scan_queue_from_draft,
    write_handwritten_scan_draft,
)
from horizon.isolated_delta import sha256_file
from horizon.pc_operator import build_work_order


def test_handwritten_scan_draft_hashes_pages_without_inventing_rows(
    tmp_path: Path,
) -> None:
    bind = tmp_path / "scans"
    bind.mkdir()
    first = bind / "hand-01.png"
    first.write_bytes(b"HAND-ONE")
    draft = write_handwritten_scan_draft(
        output=tmp_path / "draft.json",
        packet_id="SECTION15-HANDWRITTEN",
        bind_dir=bind,
    )
    assert draft["schema_id"] == "dbx.handwritten_scan_draft"
    assert draft["status"] == "UNAPPROVED_DRAFT"
    assert draft["expected_page_count"] == 1
    assert draft["pages"][0]["path"] == "hand-01.png"
    assert draft["pages"][0]["source_sha256"] == sha256_file(first)
    assert "crops" not in draft
    queue = handwritten_scan_queue_from_draft(draft)
    assert queue["schema_id"] == "dbx.handwritten_scan_queue"
    assert queue["items"][0]["action"] == "transcribe_to_penterra"
    assert "legal" not in queue["items"][0]
    assert "grantor" not in queue["items"][0]


def test_handwritten_scan_draft_hashes_authorized_subset(
    tmp_path: Path,
) -> None:
    bind = tmp_path / "snapshot"
    nested = bind / "pc" / "Section 15"
    nested.mkdir(parents=True)
    scan = nested / "Handwritten Index.png"
    scan.write_bytes(b"SNAP-HAND")
    (bind / "ignore.txt").write_text("not a scan", encoding="utf-8")
    draft = write_handwritten_scan_draft(
        output=tmp_path / "draft.json",
        packet_id="SECTION15-HANDWRITTEN",
        bind_dir=bind,
        paths=[scan],
    )
    assert draft["expected_page_count"] == 1
    assert draft["pages"][0]["path"] == "pc/Section 15/Handwritten Index.png"
    assert draft["pages"][0]["source_sha256"] == sha256_file(scan)


def test_handwritten_scan_draft_rejects_escaped_paths(tmp_path: Path) -> None:
    bind = tmp_path / "scans"
    bind.mkdir()
    outside = tmp_path / "outside.png"
    outside.write_bytes(b"NOPE")
    with pytest.raises(HandwrittenScanError, match="escapes"):
        write_handwritten_scan_draft(
            output=tmp_path / "draft.json",
            packet_id="SECTION15-HANDWRITTEN",
            bind_dir=bind,
            paths=[outside],
        )


def test_operator_writes_handwritten_scan_queue_from_examiner_dir(
    tmp_path: Path,
) -> None:
    root = tmp_path / "pc-root"
    (root / "Section 15").mkdir(parents=True)
    receipts = tmp_path / "private-receipts"
    scans = receipts / "section15-handwritten-scans"
    scans.mkdir(parents=True)
    page = scans / "hand-01.png"
    page.write_bytes(b"HAND-SCAN")
    receipt = build_work_order(
        roots=[f"pc={root}"],
        sections=[15],
        receipt_dir=receipts,
        execute=True,
    )
    assert receipt.packages_complete is False
    draft = json.loads(
        (receipts / "section15-handwritten-scan-draft.json").read_text(
            encoding="utf-8"
        )
    )
    assert draft["pages"][0]["source_sha256"] == sha256_file(page)
    queue = json.loads(
        (receipts / "section15-handwritten-scan-queue.json").read_text(
            encoding="utf-8"
        )
    )
    assert queue["items"][0]["action"] == "transcribe_to_penterra"
    assert any(
        "Penterra xlsx" in hold for hold in receipt.sections[0].holds
    )
    joined = "\n".join(receipt.sections[0].next_commands)
    assert "handwritten-scan-queue.json" in joined


def test_operator_does_not_hash_phase1_live_handwritten_scans(
    tmp_path: Path,
) -> None:
    root = tmp_path / "pc-root"
    section = root / "Section 15"
    section.mkdir(parents=True)
    (section / "Handwritten Index.png").write_bytes(b"LIVE-HAND")
    receipts = tmp_path / "private-receipts"
    receipt = build_work_order(
        roots=[f"pc={root}"],
        sections=[15],
        receipt_dir=receipts,
        execute=True,
    )
    assert receipt.packages_complete is False
    draft = json.loads(
        (receipts / "section15-handwritten-scan-draft.json").read_text(
            encoding="utf-8"
        )
    )
    assert draft["pages"] == []
    assert not (receipts / "section15-handwritten-scan-queue.json").is_file()
