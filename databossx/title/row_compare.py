"""Compare an OCR suggestion against a workbook runsheet row.

Never marks a fact "verified" unless the OCR value matches the workbook value
(case/space-insensitive). Mismatches and OCR-only values are surfaced, never
auto-applied to the source.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Map workbook header -> OCR scalar field.
FIELD_MAP = {
    "Instrument_Type": "instrument_type",
    "Document_Date": "document_date",
    "Recorded_Date": "recorded_date",
    "Book": "book",
    "Page": "page",
}


def _norm(v) -> str:
    return " ".join(str(v).strip().lower().split()) if v is not None else ""


@dataclass
class FieldComparison:
    field: str
    workbook_value: str
    ocr_value: str
    match: bool


@dataclass
class RowComparison:
    fields: list[FieldComparison] = field(default_factory=list)

    @property
    def mismatches(self) -> list[FieldComparison]:
        # Only count as mismatch when both sides have a value and they differ.
        return [f for f in self.fields if f.workbook_value and f.ocr_value and not f.match]

    @property
    def has_mismatch(self) -> bool:
        return len(self.mismatches) > 0


def compare_row(workbook_row: dict, ocr: dict) -> RowComparison:
    result = RowComparison()
    for header, ocr_field in FIELD_MAP.items():
        wb_val = _norm(workbook_row.get(header))
        ocr_val = _norm(ocr.get(ocr_field))
        result.fields.append(
            FieldComparison(header, wb_val, ocr_val, match=(wb_val == ocr_val and wb_val != ""))
        )
    return result
