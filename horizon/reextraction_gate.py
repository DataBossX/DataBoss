"""Fail closed when a tract ledger cannot check its own document numbers.

A row is checkable only when it carries an independent locator (book/page) or
face-captured recorded date plus at least one party. Bare document-number rows
cannot be corrected from the ledger; they must be re-extracted from page
renders. This module never guesses a document number and never mutates a
workbook.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .crosskey import OracleRow, Suspect, audit
from .stable_key import StableKeyError, normalize_bookpage, normalize_docno, stable_key

EXPORT_SCHEMA_ID = "dbx.tract_ledger_export"
EXPORT_SCHEMA_VERSION = "1.0"
RECEIPT_SCHEMA_ID = "dbx.reextraction_receipt"
RECEIPT_SCHEMA_VERSION = "1.0"
REQUIRED_EXPORT_KEYS = {
    "schema_id",
    "schema_version",
    "packet_id",
    "rows",
}
REQUIRED_ROW_KEYS = {
    "row_id",
    "docno",
    "bookpage",
    "rec_date",
    "doc_date",
    "grantor",
    "grantee",
    "page",
    "crop_id",
}
REQUIRED_ORACLE_KEYS = {
    "schema_id",
    "schema_version",
    "rows",
}
ORACLE_SCHEMA_ID = "dbx.crosskey_oracle"
ORACLE_ROW_KEYS = {
    "docno",
    "bookpage",
    "rec_date",
    "doc_date",
    "doc_type",
    "grantor",
    "grantee",
}


class ReextractionError(ValueError):
    """Raised when a tract-ledger export is malformed."""


@dataclass(frozen=True)
class LedgerRow:
    row_id: str
    docno: str
    bookpage: str
    rec_date: str
    doc_date: str
    grantor: str
    grantee: str
    page: int
    crop_id: str

    @property
    def has_bookpage(self) -> bool:
        return bool(self.bookpage)

    @property
    def has_face_corroboration(self) -> bool:
        return bool(self.rec_date) and bool(self.grantor or self.grantee)

    @property
    def checkable(self) -> bool:
        return self.has_bookpage or self.has_face_corroboration


@dataclass
class ReextractionReceipt:
    generated_utc: str
    packet_id: str
    row_count: int
    checkable_count: int
    bare_docno_count: int
    unparseable_count: int
    bookpage_count: int
    overlap_keys: List[str]
    bare_docno_row_ids: List[str]
    unparseable_row_ids: List[str]
    next_action: str
    self_correction_permitted: bool
    technical_pass: bool
    crosskey: Dict[str, object] = field(default_factory=dict)
    schema_id: str = RECEIPT_SCHEMA_ID
    schema_version: str = RECEIPT_SCHEMA_VERSION
    notes: List[str] = field(default_factory=lambda: [
        "technical_pass means every row is checkable; it is not package release",
        "bare document-number rows must be re-extracted from page renders",
    ])

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def _require_text(value: object, label: str, *, allow_blank: bool = False) -> str:
    if not isinstance(value, str) or "\n" in value:
        raise ReextractionError(f"{label} must be a single-line string")
    text = value.strip()
    if not allow_blank and not text:
        raise ReextractionError(f"{label} must be a single-line string")
    return text


def _load_json(path: Path) -> Dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReextractionError(f"Cannot read {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ReextractionError(f"{path} must contain a JSON object")
    return payload


def parse_ledger_export(payload: Dict[str, object]) -> tuple[str, List[LedgerRow]]:
    if set(payload) != REQUIRED_EXPORT_KEYS:
        raise ReextractionError("Tract ledger export has invalid top-level fields")
    if (
        payload["schema_id"] != EXPORT_SCHEMA_ID
        or payload["schema_version"] != EXPORT_SCHEMA_VERSION
    ):
        raise ReextractionError("Tract ledger export schema is invalid")
    packet_id = _require_text(payload["packet_id"], "packet_id")
    raw_rows = payload["rows"]
    if not isinstance(raw_rows, list) or not raw_rows:
        raise ReextractionError("rows must be a non-empty list")
    rows: List[LedgerRow] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_rows):
        if not isinstance(raw, dict) or set(raw) != REQUIRED_ROW_KEYS:
            raise ReextractionError(f"rows[{index}] has invalid fields")
        row_id = _require_text(raw["row_id"], "row_id")
        if row_id in seen:
            raise ReextractionError(f"row_id is duplicated: {row_id}")
        seen.add(row_id)
        page = raw["page"]
        if type(page) is not int or page < 1:
            raise ReextractionError(f"{row_id} page must be an integer >= 1")
        try:
            docno = normalize_docno(str(raw["docno"]))
            bookpage = normalize_bookpage(str(raw["bookpage"]))
        except StableKeyError as exc:
            raise ReextractionError(f"{row_id}: {exc}") from exc
        rows.append(
            LedgerRow(
                row_id=row_id,
                docno=docno,
                bookpage=bookpage,
                rec_date=_require_text(raw["rec_date"], "rec_date", allow_blank=True),
                doc_date=_require_text(raw["doc_date"], "doc_date", allow_blank=True),
                grantor=_require_text(raw["grantor"], "grantor", allow_blank=True),
                grantee=_require_text(raw["grantee"], "grantee", allow_blank=True),
                page=page,
                crop_id=_require_text(raw["crop_id"], "crop_id"),
            )
        )
    return packet_id, rows


def parse_oracle(payload: Dict[str, object]) -> List[OracleRow]:
    if set(payload) != REQUIRED_ORACLE_KEYS:
        raise ReextractionError("Oracle export has invalid top-level fields")
    if (
        payload["schema_id"] != ORACLE_SCHEMA_ID
        or payload["schema_version"] != EXPORT_SCHEMA_VERSION
    ):
        raise ReextractionError("Oracle export schema is invalid")
    raw_rows = payload["rows"]
    if not isinstance(raw_rows, list) or not raw_rows:
        raise ReextractionError("oracle rows must be a non-empty list")
    rows: List[OracleRow] = []
    for index, raw in enumerate(raw_rows):
        if not isinstance(raw, dict) or set(raw) != ORACLE_ROW_KEYS:
            raise ReextractionError(f"oracle rows[{index}] has invalid fields")
        rows.append(
            OracleRow(
                docno=_require_text(raw["docno"], "docno", allow_blank=True),
                bookpage=_require_text(raw["bookpage"], "bookpage", allow_blank=True),
                rec_date=_require_text(raw["rec_date"], "rec_date", allow_blank=True),
                doc_date=_require_text(raw["doc_date"], "doc_date", allow_blank=True),
                doc_type=_require_text(raw["doc_type"], "doc_type", allow_blank=True),
                grantor=_require_text(raw["grantor"], "grantor", allow_blank=True),
                grantee=_require_text(raw["grantee"], "grantee", allow_blank=True),
            )
        )
    return rows


def assess_ledger(
    packet_id: str,
    rows: Sequence[LedgerRow],
    *,
    oracle: Optional[Sequence[OracleRow]] = None,
) -> ReextractionReceipt:
    checkable: List[LedgerRow] = []
    bare: List[LedgerRow] = []
    unparseable: List[str] = []
    keys: Dict[str, List[str]] = {}
    for row in rows:
        if not row.docno and not row.bookpage:
            unparseable.append(row.row_id)
            continue
        try:
            key = stable_key(row.docno or None, row.bookpage or None)
        except StableKeyError:
            unparseable.append(row.row_id)
            continue
        keys.setdefault(key, []).append(row.row_id)
        if row.checkable:
            checkable.append(row)
        else:
            bare.append(row)

    overlaps = sorted(key for key, group in keys.items() if len(group) > 1)
    crosskey_payload: Dict[str, object] = {}
    if oracle is not None:
        if bare:
            raise ReextractionError(
                "Refuse cross-key proposals while bare document-number rows remain"
            )
        suspects = [
            Suspect(
                docno=row.docno,
                locator=row.row_id,
                bookpage=row.bookpage,
                rec_date=row.rec_date,
                doc_date=row.doc_date,
                grantor=row.grantor,
                grantee=row.grantee,
            )
            for row in checkable
        ]
        crosskey_payload = audit(suspects, list(oracle))

    self_correction = not bare and not unparseable
    if unparseable:
        next_action = "repair_unparseable_identities"
    elif bare:
        next_action = "reextract_bare_docno_from_page_renders"
    else:
        next_action = "run_corroborated_crosskey_then_occurrence_ledger"
    return ReextractionReceipt(
        generated_utc=datetime.now(timezone.utc).isoformat(),
        packet_id=packet_id,
        row_count=len(rows),
        checkable_count=len(checkable),
        bare_docno_count=len(bare),
        unparseable_count=len(unparseable),
        bookpage_count=sum(1 for row in rows if row.has_bookpage),
        overlap_keys=overlaps,
        bare_docno_row_ids=[row.row_id for row in bare],
        unparseable_row_ids=unparseable,
        next_action=next_action,
        self_correction_permitted=self_correction,
        technical_pass=self_correction,
        crosskey=crosskey_payload,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Measure whether a tract-ledger export can check its own "
            "document numbers, without mutating production."
        )
    )
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--oracle", type=Path)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        packet_id, rows = parse_ledger_export(_load_json(args.packet))
        oracle = parse_oracle(_load_json(args.oracle)) if args.oracle else None
        receipt = assess_ledger(packet_id, rows, oracle=oracle)
        args.output.write_text(
            json.dumps(receipt.to_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )
    except (OSError, ReextractionError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "output": str(args.output),
                "technical_pass": receipt.technical_pass,
                "row_count": receipt.row_count,
                "checkable_count": receipt.checkable_count,
                "bare_docno_count": receipt.bare_docno_count,
                "next_action": receipt.next_action,
            },
            indent=2,
        )
    )
    return 0 if receipt.technical_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
