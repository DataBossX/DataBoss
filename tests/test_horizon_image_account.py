"""Every raster and PDF page must be counted and accounted for."""

from __future__ import annotations

import json
from pathlib import Path

from horizon.image_account import (
    WORK_DATE,
    account_images,
    every_image_accounted,
    main,
    verify_packet,
    vision_queue_from_receipt,
    write_inventory_packet,
)
from horizon.package_finish import run_finish
from horizon.remaining_plan import remaining_plan
from horizon.vision_ocr import review_queue


MINIMAL_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de"
    "0000000c49444154789c636000020000050001d5c8c94e0000000049454e44ae426082"
)
TWO_PAGE_PDF = (
    b"%PDF-1.1\n"
    b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n"
    b"2 0 obj<< /Type /Pages /Count 2 /Kids [3 0 R 4 0 R] >>endobj\n"
    b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>endobj\n"
    b"4 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>endobj\n"
    b"trailer<< /Root 1 0 R >>\n"
)


def _bind(tmp_path: Path) -> Path:
    bind = tmp_path / "faces"
    bind.mkdir()
    (bind / "handwritten.tif").write_bytes(MINIMAL_PNG)
    (bind / "scan.png").write_bytes(MINIMAL_PNG)
    (bind / "casefile.pdf").write_bytes(TWO_PAGE_PDF)
    (bind / "notes.txt").write_text("not an image\n", encoding="utf-8")
    return bind


def test_account_images_counts_every_raster_and_pdf_page(tmp_path: Path) -> None:
    receipt = account_images(_bind(tmp_path), packet_id="SYNTH-IMG-001")
    images = [item for item in receipt.images if item.kind in {"raster", "pdf_page"}]
    assert receipt.work_date == WORK_DATE.isoformat()
    assert receipt.raster_count == 2
    assert receipt.pdf_page_count == 2
    assert receipt.image_count == 4
    assert receipt.other_file_count == 1
    assert receipt.accounted_images == 4
    assert receipt.unaccounted_images == 0
    assert every_image_accounted(receipt)
    assert {item.path for item in images} == {
        "handwritten.tif",
        "scan.png",
        "casefile.pdf#page=1",
        "casefile.pdf#page=2",
    }
    assert receipt.packages_complete is False


def test_verify_packet_fails_when_an_image_is_omitted(tmp_path: Path) -> None:
    bind = _bind(tmp_path)
    packet_path = tmp_path / "packet.json"
    packet = write_inventory_packet(
        bind_dir=bind,
        output=packet_path,
        packet_id="SYNTH-IMG-002",
    )
    packet["files"] = [
        item for item in packet["files"] if item.get("path") != "scan.png"
    ]
    receipt = verify_packet(packet, bind)
    assert receipt.technical_pass is False
    assert any("missing from the packet" in note for note in receipt.notes)


def test_vision_queue_covers_empty_text_images(tmp_path: Path) -> None:
    receipt = account_images(_bind(tmp_path), packet_id="SYNTH-IMG-003")
    queue = vision_queue_from_receipt(receipt)
    assert queue["schema_id"] == "dbx.image_account_queue"
    assert queue["work_date"] == WORK_DATE.isoformat()
    paths = {item["path"] for item in queue["items"]}
    assert paths == {
        "handwritten.tif",
        "scan.png",
        "casefile.pdf#page=1",
        "casefile.pdf#page=2",
    }
    reviewed = review_queue(queue, bind_dir=_bind(tmp_path))
    assert reviewed.queued == 4
    assert reviewed.vision_unavailable == 4
    assert reviewed.packages_complete is False
    assert all(
        "do not write it into legal cells" not in " ".join(item.notes)
        or item.ocr_status == "ran"
        for item in reviewed.attempts
    )


def test_image_account_cli_inventory(tmp_path: Path) -> None:
    result = main(
        [
            "--bind-dir",
            str(_bind(tmp_path)),
            "--packet-id",
            "SYNTH-IMG-CLI",
            "--inventory",
            "--output",
            str(tmp_path / "packet.json"),
            "--vision-queue",
            str(tmp_path / "queue.json"),
        ]
    )
    assert result == 0
    queue = json.loads((tmp_path / "queue.json").read_text(encoding="utf-8"))
    assert len(queue["items"]) == 4


def test_finish_image_account_gate_holds_empty_text(tmp_path: Path) -> None:
    receipt = run_finish(
        sections=[15],
        image_bind_dir=_bind(tmp_path),
    )
    gate = next(item for item in receipt.gates if item.name == "image_account")
    assert gate.ran is True
    assert gate.detail["image_count"] == 4
    assert gate.detail["work_date"] == WORK_DATE.isoformat()
    assert any("empty-text image" in action for action in receipt.next_actions)
    assert receipt.packages_complete is False


def test_remaining_plan_holds_unaccounted_images(tmp_path: Path) -> None:
    finish = {
        "schema_id": "dbx.package_finish_receipt",
        "gates": [
            {
                "name": "image_account",
                "ran": True,
                "technical_pass": False,
                "detail": {"unaccounted_images": 2, "empty_text_images": 3},
            }
        ],
    }
    plan = remaining_plan(section=15, finish=finish, receipt_dir=tmp_path)
    assert any("unaccounted" in item for item in plan["missing"])
    assert any("vision before OCR" in item for item in plan["missing"])
    assert plan["packages_complete"] is False


def test_remaining_plan_scores_image_account_queue(tmp_path: Path) -> None:
    (tmp_path / "section15-image-account-queue.json").write_text(
        json.dumps(
            {
                "schema_id": "dbx.image_account_queue",
                "schema_version": "1.0",
                "packet_id": "SEC15-IMAGES",
                "items": [
                    {"path": "scan.png", "kind": "raster", "source_sha256": "a" * 64}
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    plan = remaining_plan(section=15, finish=None, receipt_dir=tmp_path)
    assert plan["open_queues"]["image_account_queue"] == (
        "section15-image-account-queue.json"
    )
    assert any("vision before OCR" in item for item in plan["missing"])
