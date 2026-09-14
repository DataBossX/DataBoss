"""Page-render crop compiler and hash-bound PDF page census."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from horizon.package_finish import run_finish
from horizon.page_render_export import (
    PageRenderExportError,
    compile_page_renders,
    write_crop_packet,
)
from horizon.pdf_census import PdfCensusError, census_packet, main as census_main, write_inventory_packet
from horizon.reextraction_gate import assess_ledger, parse_ledger_export


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _packet(**overrides: object) -> dict[str, object]:
    page_hash = _sha("render-1")
    packet = {
        "schema_id": "dbx.page_render_crop_packet",
        "schema_version": "1.0",
        "packet_id": "SYNTH-P11-RENDERS",
        "expected_page_count": 1,
        "pages": [{"page": 1, "source_sha256": page_hash}],
        "crops": [
            {
                "row_id": "p01r01",
                "page": 1,
                "crop_id": "p01r01",
                "source_sha256": page_hash,
                "docno": "2026-09901",
                "bookpage": "",
                "rec_date": "1/2/2026",
                "doc_date": "",
                "grantor": "SYNTH SURVEYOR",
                "grantee": "The Public",
            }
        ],
    }
    packet.update(overrides)
    return packet


def test_compile_emits_checkable_tract_export() -> None:
    receipt = compile_page_renders(_packet())
    assert receipt.technical_pass is True
    assert receipt.reextraction_technical_pass is True
    assert receipt.crop_count == 1
    packet_id, rows = parse_ledger_export(receipt.tract_export)
    assert packet_id == "SYNTH-P11-RENDERS"
    assert assess_ledger(packet_id, rows).technical_pass is True


def test_bare_docno_is_preserved_not_guessed() -> None:
    page_hash = _sha("render-1")
    receipt = compile_page_renders(
        _packet(
            crops=[
                {
                    "row_id": "p01r01",
                    "page": 1,
                    "crop_id": "p01r01",
                    "source_sha256": page_hash,
                    "docno": "900001",
                    "bookpage": "",
                    "rec_date": "",
                    "doc_date": "",
                    "grantor": "",
                    "grantee": "",
                }
            ]
        )
    )
    assert receipt.technical_pass is True
    assert receipt.reextraction_technical_pass is False
    assert receipt.next_action == "reextract_bare_docno_from_page_renders"
    assert receipt.tract_export["rows"][0]["docno"] == "900001"


def test_hash_mismatch_and_missing_identity_fail() -> None:
    with pytest.raises(PageRenderExportError, match="does not match page"):
        compile_page_renders(
            _packet(
                crops=[
                    {
                        "row_id": "p01r01",
                        "page": 1,
                        "crop_id": "p01r01",
                        "source_sha256": _sha("other"),
                        "docno": "2026-09901",
                        "bookpage": "",
                        "rec_date": "1/2/2026",
                        "doc_date": "",
                        "grantor": "SYNTH",
                        "grantee": "",
                    }
                ]
            )
        )
    with pytest.raises(PageRenderExportError, match="neither docno nor bookpage"):
        compile_page_renders(
            _packet(
                crops=[
                    {
                        "row_id": "p01r01",
                        "page": 1,
                        "crop_id": "p01r01",
                        "source_sha256": _sha("render-1"),
                        "docno": "",
                        "bookpage": "",
                        "rec_date": "1/2/2026",
                        "doc_date": "",
                        "grantor": "SYNTH",
                        "grantee": "",
                    }
                ]
            )
        )


def _minimal_pdf() -> bytes:
    return (
        b"%PDF-1.1\n"
        b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n"
        b"2 0 obj<< /Type /Pages /Count 1 /Kids [3 0 R] >>endobj\n"
        b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>endobj\n"
        b"trailer<< /Root 1 0 R >>\n"
    )


def test_pdf_census_binds_hash_and_flags_empty_text(tmp_path: Path) -> None:
    pdf = tmp_path / "part4.pdf"
    pdf.write_bytes(_minimal_pdf())
    digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
    receipt = census_packet(
        {
            "schema_id": "dbx.pdf_page_census_packet",
            "schema_version": "1.0",
            "packet_id": "SYNTH-P13-CENSUS",
            "files": [
                {
                    "path": "part4.pdf",
                    "source_sha256": digest,
                    "expected_pages": 1,
                }
            ],
        },
        bind_dir=tmp_path,
    )
    assert receipt.technical_pass is True
    assert receipt.empty_text_files == 1
    assert receipt.files[0].counted_pages == 1
    assert receipt.files[0].empty_text is True

    wrong = census_packet(
        {
            "schema_id": "dbx.pdf_page_census_packet",
            "schema_version": "1.0",
            "packet_id": "SYNTH-P13-CENSUS",
            "files": [
                {
                    "path": "part4.pdf",
                    "source_sha256": digest,
                    "expected_pages": 462,
                }
            ],
        },
        bind_dir=tmp_path,
    )
    assert wrong.technical_pass is False
    assert any("expected 462" in issue for issue in wrong.files[0].issues)


def test_inventory_writes_counted_pages_not_row_count(tmp_path: Path) -> None:
    bind = tmp_path / "federal-pdfs"
    bind.mkdir()
    (bind / "part4.pdf").write_bytes(_minimal_pdf())
    output = tmp_path / "census-packet.json"
    packet = write_inventory_packet(
        bind_dir=bind,
        output=output,
        packet_id="SECTION13-CENSUS",
    )
    assert packet["schema_id"] == "dbx.pdf_page_census_packet"
    assert packet["files"][0]["path"] == "part4.pdf"
    assert packet["files"][0]["expected_pages"] == 1
    assert packet["files"][0]["expected_pages"] != 462
    receipt = census_packet(packet, bind_dir=bind)
    assert receipt.technical_pass is True
    assert receipt.empty_text_files == 1
    assert census_main(
        [
            "--inventory",
            "--bind-dir",
            str(bind),
            "--output",
            str(tmp_path / "second.json"),
            "--packet-id",
            "SECTION13-CENSUS-2",
        ]
    ) == 0


def test_inventory_refuses_empty_dir_and_repo_output(tmp_path: Path) -> None:
    empty = tmp_path / "empty-pdfs"
    empty.mkdir()
    with pytest.raises(PdfCensusError, match="no PDF files"):
        write_inventory_packet(
            bind_dir=empty,
            output=tmp_path / "census.json",
            packet_id="SECTION13-CENSUS",
        )
    bind = tmp_path / "federal-pdfs"
    bind.mkdir()
    (bind / "part4.pdf").write_bytes(_minimal_pdf())
    repo_out = Path(__file__).resolve().parents[1] / "horizon" / "synth-census.json"
    with pytest.raises(PdfCensusError, match="outside this repository"):
        write_inventory_packet(
            bind_dir=bind,
            output=repo_out,
            packet_id="SECTION13-CENSUS",
        )
    existing = tmp_path / "exists.json"
    existing.write_text("{}", encoding="utf-8")
    with pytest.raises(PdfCensusError, match="already exists"):
        write_inventory_packet(
            bind_dir=bind,
            output=existing,
            packet_id="SECTION13-CENSUS",
        )
    assert census_main(
        [
            "--inventory",
            "--packet",
            str(existing),
            "--bind-dir",
            str(bind),
            "--output",
            str(tmp_path / "nope.json"),
            "--packet-id",
            "SECTION13-CENSUS",
        ]
    ) == 1


def test_finish_runner_compiles_page_renders_without_completing(
    tmp_path: Path,
) -> None:
    packet = tmp_path / "renders.json"
    packet.write_text(json.dumps(_packet()), encoding="utf-8")
    receipt = run_finish(sections=[11], page_render_packet=packet)
    assert receipt.packages_complete is False
    assert receipt.technical_pass is True
    assert {gate.name for gate in receipt.gates} == {
        "page_render_export",
        "reextraction",
        "occurrence_ledger",
    }


def test_write_crop_packet_preserves_bare_docno(tmp_path: Path) -> None:
    render = tmp_path / "p01.bin"
    render.write_bytes(b"SYNTH-RENDER")
    output = tmp_path / "crops.json"
    packet = write_crop_packet(
        draft={
            "packet_id": "SYNTH-P11-RENDERS",
            "expected_page_count": 1,
            "pages": [{"page": 1, "path": "p01.bin"}],
            "crops": [
                {
                    "row_id": "p01r01",
                    "page": 1,
                    "crop_id": "p01r01",
                    "docno": "2026-09901",
                    "bookpage": "",
                    "rec_date": "1/2/2026",
                    "doc_date": "",
                    "grantor": "SYNTH SURVEYOR",
                    "grantee": "The Public",
                }
            ],
        },
        bind_dir=tmp_path,
        output=output,
    )
    assert packet["crops"][0]["bookpage"] == ""
    assert packet["pages"][0]["source_sha256"] == hashlib.sha256(
        b"SYNTH-RENDER"
    ).hexdigest()
    compiled = compile_page_renders(packet, bind_dir=tmp_path)
    assert compiled.technical_pass is True
    with pytest.raises(PageRenderExportError, match="neither docno nor bookpage"):
        write_crop_packet(
            draft={
                "packet_id": "SYNTH-EMPTY",
                "expected_page_count": 1,
                "pages": [{"page": 1, "path": "p01.bin"}],
                "crops": [
                    {
                        "row_id": "p01r02",
                        "page": 1,
                        "crop_id": "p01r02",
                        "docno": "",
                        "bookpage": "",
                        "rec_date": "",
                        "doc_date": "",
                        "grantor": "",
                        "grantee": "",
                    }
                ],
            },
            bind_dir=tmp_path,
            output=tmp_path / "empty.json",
        )
