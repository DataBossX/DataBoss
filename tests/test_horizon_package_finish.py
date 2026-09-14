"""Package finish runner never promotes and chains existing gates."""

import hashlib
import json
from pathlib import Path

from horizon.package_finish import main, run_finish


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _checkable_export() -> dict:
    return {
        "schema_id": "dbx.tract_ledger_export",
        "schema_version": "1.0",
        "packet_id": "SYNTH-FINISH-001",
        "rows": [
            {
                "row_id": "p01r01",
                "docno": "2026-09901",
                "bookpage": "",
                "rec_date": "1/2/2026",
                "doc_date": "",
                "grantor": "SYNTH SURVEYOR",
                "grantee": "The Public",
                "page": 1,
                "crop_id": "p01r01",
            }
        ],
    }


def _occurrence_packet() -> dict:
    key = "2026-09901|"
    digest = _sha("face-a")
    fields = {
        "party": "SYNTH SURVEYOR",
        "date_role": "recorded",
        "legal": "SYNTH TRACT",
    }
    return {
        "schema_id": "dbx.occurrence_packet",
        "schema_version": "1.0",
        "packet_id": "SYNTH-FINISH-OCC",
        "occurrences": [
            {
                "occurrence_id": "occ-001",
                "stable_key": key,
                "source_sha256": digest,
                "page": 1,
                "crop_id": "p01r01",
                "fields": fields,
                "risk": "novel",
            }
        ],
        "unique_key_ledger": [{"stable_key": key, "source_sha256": digest}],
        "candidate_rows": [
            {
                "row_id": "R6-001",
                "stable_key": key,
                "source_sha256": digest,
                "fields": fields,
            }
        ],
        "allowlist": [],
    }


def test_empty_run_is_blocked_and_never_complete() -> None:
    receipt = run_finish(sections=[15, 13, 11])
    assert receipt.packages_complete is False
    assert receipt.technical_pass is False
    assert receipt.gates == []
    assert any("Mount PC/Drive" in action for action in receipt.next_actions)


def test_chained_checkable_packets_pass_gates_but_not_packages(
    tmp_path: Path,
) -> None:
    export = tmp_path / "export.json"
    packet = tmp_path / "packet.json"
    plat = tmp_path / "plat.pdf"
    export.write_text(json.dumps(_checkable_export()), encoding="utf-8")
    packet.write_text(json.dumps(_occurrence_packet()), encoding="utf-8")
    plat.write_bytes(b"%PDF-1.1\n1 0 obj<<>>endobj\ntrailer<<>>\n")

    receipt = run_finish(
        sections=[15, 13, 11],
        tract_export=export,
        occurrence_packet=packet,
        public_plats=[f"campbell,45n,76w,{plat}"],
    )
    assert receipt.technical_pass is True
    assert receipt.packages_complete is False
    assert {gate.name for gate in receipt.gates} == {
        "reextraction",
        "occurrence_ledger",
        "public_cadastral",
    }
    assert all(gate.technical_pass for gate in receipt.gates)


def test_cli_empty_run_writes_blocked_receipt(tmp_path: Path) -> None:
    output = tmp_path / "finish.json"
    result = main(["--output", str(output), "--section", "15"])
    assert result == 2
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["packages_complete"] is False
    assert payload["technical_pass"] is False
