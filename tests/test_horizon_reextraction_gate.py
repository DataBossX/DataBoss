"""Bare document-number ledgers cannot self-correct."""

import json
from pathlib import Path

import pytest

from horizon.crosskey import OracleRow
from horizon.reextraction_gate import (
    ReextractionError,
    assess_ledger,
    main,
    parse_ledger_export,
    parse_oracle,
)


def _row(
    row_id: str,
    docno: str,
    *,
    bookpage: str = "",
    rec_date: str = "",
    grantor: str = "",
    grantee: str = "",
    page: int = 1,
) -> dict[str, object]:
    return {
        "row_id": row_id,
        "docno": docno,
        "bookpage": bookpage,
        "rec_date": rec_date,
        "doc_date": "",
        "grantor": grantor,
        "grantee": grantee,
        "page": page,
        "crop_id": row_id,
    }


def _export(rows: list[dict[str, object]], packet_id: str = "SYNTH-REEX-001") -> dict:
    return {
        "schema_id": "dbx.tract_ledger_export",
        "schema_version": "1.0",
        "packet_id": packet_id,
        "rows": rows,
    }


def test_p11_shaped_bare_docno_ledger_is_blocked() -> None:
    rows = [_row(f"p01r{index:02d}", f"{900000 + index}") for index in range(1, 20)]
    rows.append(
        _row(
            "p01r20",
            "900020",
            bookpage="0654-0561",
            rec_date="1/2/2024",
            grantor="SYNTH PARTY",
        )
    )
    packet_id, parsed = parse_ledger_export(_export(rows, "SYNTH-P11-SHAPE"))
    receipt = assess_ledger(packet_id, parsed)

    assert receipt.row_count == 20
    assert receipt.checkable_count == 1
    assert receipt.bare_docno_count == 19
    assert receipt.bookpage_count == 1
    assert receipt.self_correction_permitted is False
    assert receipt.technical_pass is False
    assert receipt.next_action == "reextract_bare_docno_from_page_renders"


def test_modern_docno_with_face_date_and_party_is_checkable() -> None:
    payload = _export(
        [
            _row(
                "p02r01",
                "2026-09901",
                rec_date="1/2/2026",
                grantor="SYNTH SURVEYOR",
                grantee="The Public",
            )
        ]
    )
    packet_id, parsed = parse_ledger_export(payload)
    receipt = assess_ledger(packet_id, parsed)
    assert receipt.technical_pass
    assert receipt.bare_docno_count == 0
    assert parsed[0].checkable


def test_refuse_crosskey_while_bare_rows_remain() -> None:
    packet_id, parsed = parse_ledger_export(
        _export([_row("p01r01", "900111")])
    )
    with pytest.raises(ReextractionError, match="bare document-number"):
        assess_ledger(
            packet_id,
            parsed,
            oracle=[OracleRow(docno="900112")],
        )


def test_oracle_proposes_only_after_reextraction() -> None:
    packet_id, parsed = parse_ledger_export(
        _export(
            [
                _row(
                    "p04r06",
                    "900112",
                    bookpage="0654-0561",
                    rec_date="3/4/2024",
                    grantor="SYNTH ALPHA LLC",
                )
            ]
        )
    )
    receipt = assess_ledger(
        packet_id,
        parsed,
        oracle=[
            OracleRow(
                docno="900113",
                bookpage="654-561",
                rec_date="03/04/2024",
                grantor="Synth Alpha, LLC",
            )
        ],
    )
    assert receipt.technical_pass
    assert receipt.crosskey["corrections_proposed"] == 1
    assert receipt.crosskey["results"][0]["status"] == "CORRECTION_PROPOSED"


def test_cli_writes_blocked_receipt(tmp_path: Path) -> None:
    packet = tmp_path / "export.json"
    packet.write_text(
        json.dumps(_export([_row("p01r01", "900111")])),
        encoding="utf-8",
    )
    output = tmp_path / "receipt.json"
    result = main(["--packet", str(packet), "--output", str(output)])
    assert result == 2
    receipt = json.loads(output.read_text(encoding="utf-8"))
    assert receipt["bare_docno_count"] == 1
    assert receipt["self_correction_permitted"] is False


def test_unknown_export_fields_fail_closed() -> None:
    payload = _export([_row("p01r01", "900111")])
    payload["comment"] = "ignore"
    with pytest.raises(ReextractionError, match="top-level"):
        parse_ledger_export(payload)


def test_oracle_schema_is_strict() -> None:
    with pytest.raises(ReextractionError):
        parse_oracle({"schema_id": "nope", "schema_version": "1.0", "rows": []})
