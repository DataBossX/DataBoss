"""Gate 6: Instrument Source Audit.

Every material conveyance row must cite a Book/Page or an Instrument Number.
A material row missing both escalates as a missing source.
"""

from __future__ import annotations

from typing import Any, Dict, List

from core.enums import FailureCategory, Severity
from .base_validator import ValidationResult, ValidatorBase
from .util import column_index, find_sheets_by_category, non_empty

_BOOK_ALIASES = ("book", "book number", "vol", "volume")
_PAGE_ALIASES = ("page", "page number", "pg")
_INSTRUMENT_ALIASES = ("instrument", "instrument number", "instrument no",
                       "recording number", "reception number", "doc number",
                       "document number", "recording")
_GRANTOR_ALIASES = ("grantor", "grantor name", "from")


class InstrumentSourceAuditGate(ValidatorBase):
    gate_name = "Instrument Source Audit Gate"

    def validate(self, context: Dict[str, Any]) -> List[ValidationResult]:
        sheets = find_sheets_by_category(context, "runsheet")
        sheets += find_sheets_by_category(context, "ogl_register")
        if not sheets:
            return [
                self._escalate(
                    affected_subject="instrument sources",
                    reason="No runsheet/OGL sheets available for instrument audit.",
                    failure_category=FailureCategory.MISSING_SOURCE,
                    recommended_action="Confirm source-bearing sheets exist.",
                )
            ]

        results: List[ValidationResult] = []
        checked = 0
        for sheet in sheets:
            book = column_index(sheet.headers, *_BOOK_ALIASES)
            page = column_index(sheet.headers, *_PAGE_ALIASES)
            instrument = column_index(sheet.headers, *_INSTRUMENT_ALIASES)
            grantor = column_index(sheet.headers, *_GRANTOR_ALIASES)
            if book is None and page is None and instrument is None:
                continue
            header_offset = sheet.header_row_index or 0
            for r_idx, row in enumerate(sheet.rows):
                # material row = has a grantor or any populated content
                material = (
                    grantor is not None
                    and grantor < len(row)
                    and non_empty(row[grantor])
                )
                if grantor is None:
                    material = any(non_empty(c) for c in row)
                if not material:
                    continue
                checked += 1
                excel_row = header_offset + 1 + r_idx
                has_bp = (
                    book is not None and page is not None
                    and book < len(row) and page < len(row)
                    and non_empty(row[book]) and non_empty(row[page])
                )
                has_instr = (
                    instrument is not None and instrument < len(row)
                    and non_empty(row[instrument])
                )
                if not has_bp and not has_instr:
                    subject = (
                        str(row[grantor]).strip()
                        if grantor is not None and grantor < len(row) and non_empty(row[grantor])
                        else f"{sheet.name} row {excel_row}"
                    )
                    results.append(
                        self._escalate(
                            affected_sheet=sheet.name,
                            affected_cell_or_range=f"row {excel_row}",
                            affected_subject=subject,
                            reason="Material row cites no Book/Page or Instrument Number.",
                            evidence=f"row={[str(c) for c in row][:8]}",
                            failure_category=FailureCategory.MISSING_SOURCE,
                            recommended_action=(
                                "Locate and cite the recording reference; examiner "
                                "review if source cannot be found."
                            ),
                            confidence=0.9,
                        )
                    )

        if checked == 0:
            return [
                self._escalate(
                    affected_subject="instrument sources",
                    reason="No material rows found for instrument source audit.",
                    failure_category=FailureCategory.MISSING_SOURCE,
                    recommended_action="Confirm source-bearing columns exist.",
                )
            ]
        if not results:
            results.append(
                self._passed(
                    affected_subject="instrument sources",
                    reason=f"All {checked} material row(s) cite a recording reference.",
                    confidence=0.95,
                )
            )
        return results
