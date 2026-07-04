"""Gates 7, 8, 9: OGL Register Audit, WI/Depth Consistency, Well/HBP Support.

OGL references in tract sheets must exist in the OGL register; assignments must
feed the working-interest sheet; depth clauses must align. HBP/production
claims require source-backed support. Orphans, clashes, and unsupported claims
escalate — never auto-repaired.
"""

from __future__ import annotations

from typing import Any, Dict, List, Set

from core.enums import FailureCategory, Severity
from .base_validator import ValidationResult, ValidatorBase
from .util import column_index, find_sheets_by_category, non_empty

_OGL_ALIASES = ("ogl", "ogl number", "ogl id", "lease id", "lease number", "lease")
_DEPTH_ALIASES = ("depth", "depth limitation", "depths", "formation", "interval")
_HBP_ALIASES = ("hbp", "held by production", "production status", "well status", "status")
_WELL_ALIASES = ("well", "well name", "api", "well number")


def _collect_values(context: Dict[str, Any], category: str, aliases) -> Set[str]:
    values: Set[str] = set()
    for sheet in find_sheets_by_category(context, category):
        col = column_index(sheet.headers, *aliases)
        if col is None:
            continue
        for row in sheet.rows:
            if col < len(row) and non_empty(row[col]):
                values.add(str(row[col]).strip().lower())
    return values


class OGLRegisterAuditGate(ValidatorBase):
    gate_name = "OGL Register Audit Gate"

    def validate(self, context: Dict[str, Any]) -> List[ValidationResult]:
        register = _collect_values(context, "ogl_register", _OGL_ALIASES)
        results: List[ValidationResult] = []
        checked = 0

        for sheet in find_sheets_by_category(context, "tracts"):
            col = column_index(sheet.headers, *_OGL_ALIASES)
            if col is None:
                continue
            header_offset = sheet.header_row_index or 0
            for r_idx, row in enumerate(sheet.rows):
                if col >= len(row) or not non_empty(row[col]):
                    continue
                checked += 1
                ref = str(row[col]).strip().lower()
                excel_row = header_offset + 1 + r_idx
                if register and ref not in register:
                    results.append(
                        self._escalate(
                            affected_sheet=sheet.name,
                            affected_cell_or_range=f"row {excel_row}",
                            affected_subject=str(row[col]),
                            reason="Tract OGL reference not found in OGL register.",
                            evidence=f"ref={ref!r}",
                            failure_category=FailureCategory.OGL_MISMATCH_WI_GAP,
                            recommended_action="Examiner must reconcile OGL orphan.",
                            confidence=0.9,
                        )
                    )
        if not register and checked > 0:
            results.append(
                self._escalate(
                    affected_subject="ogl_register",
                    reason="Tracts reference OGLs but no register entries were found.",
                    failure_category=FailureCategory.OGL_MISMATCH_WI_GAP,
                    recommended_action="Confirm OGL register is populated.",
                )
            )
        if not results:
            results.append(
                self._passed(
                    affected_subject="ogl_register",
                    reason=f"OGL references reconciled ({checked} checked).",
                    confidence=0.9,
                )
            )
        return results


class WIDepthConsistencyGate(ValidatorBase):
    gate_name = "WI/Depth Consistency Gate"

    def validate(self, context: Dict[str, Any]) -> List[ValidationResult]:
        wi_sheets = find_sheets_by_category(context, "working_interest")
        if not wi_sheets:
            return [
                self._escalate(
                    affected_subject="working_interest",
                    reason="No working-interest sheet for WI/depth consistency.",
                    failure_category=FailureCategory.OGL_MISMATCH_WI_GAP,
                    recommended_action="Confirm WI sheet exists.",
                )
            ]

        register_ogls = _collect_values(context, "ogl_register", _OGL_ALIASES)
        results: List[ValidationResult] = []
        checked = 0
        for sheet in wi_sheets:
            ogl_col = column_index(sheet.headers, *_OGL_ALIASES)
            depth_col = column_index(sheet.headers, *_DEPTH_ALIASES)
            header_offset = sheet.header_row_index or 0
            for r_idx, row in enumerate(sheet.rows):
                if not any(non_empty(c) for c in row):
                    continue
                checked += 1
                excel_row = header_offset + 1 + r_idx
                # WI assignment must trace to an OGL in the register.
                if ogl_col is not None and ogl_col < len(row) and non_empty(row[ogl_col]):
                    ref = str(row[ogl_col]).strip().lower()
                    if register_ogls and ref not in register_ogls:
                        results.append(
                            self._escalate(
                                affected_sheet=sheet.name,
                                affected_cell_or_range=f"row {excel_row}",
                                affected_subject=str(row[ogl_col]),
                                reason="WI assignment references an OGL not in register.",
                                evidence=f"ref={ref!r}",
                                failure_category=FailureCategory.OGL_MISMATCH_WI_GAP,
                                recommended_action="Examiner must resolve WI/OGL gap.",
                                confidence=0.88,
                            )
                        )
                # Depth clause present but unsupported cannot be inferred.
                if depth_col is not None and depth_col < len(row) and non_empty(row[depth_col]):
                    depth_text = str(row[depth_col]).strip().lower()
                    if "unknown" in depth_text or "tbd" in depth_text or "?" in depth_text:
                        results.append(
                            self._escalate(
                                affected_sheet=sheet.name,
                                affected_cell_or_range=f"row {excel_row}",
                                affected_subject="depth limitation",
                                reason="Depth limitation is ambiguous/unsupported.",
                                evidence=f"depth={depth_text!r}",
                                failure_category=FailureCategory.UNSAFE_LEGAL_INFERENCE,
                                recommended_action="Examiner must confirm depth clause.",
                                confidence=0.85,
                            )
                        )
        if not results:
            results.append(
                self._passed(
                    affected_subject="working_interest",
                    reason=f"WI/depth consistent ({checked} row(s)).",
                    confidence=0.88,
                )
            )
        return results


class WellHBPSupportGate(ValidatorBase):
    gate_name = "Well/HBP Support Gate"

    def validate(self, context: Dict[str, Any]) -> List[ValidationResult]:
        well_sheets = find_sheets_by_category(context, "wells")
        source_index = context.get("source_index") or {}
        found_refs = {str(k).lower() for k in source_index.get("found_keys", [])}
        results: List[ValidationResult] = []
        checked = 0

        for sheet in well_sheets:
            hbp_col = column_index(sheet.headers, *_HBP_ALIASES)
            well_col = column_index(sheet.headers, *_WELL_ALIASES)
            header_offset = sheet.header_row_index or 0
            for r_idx, row in enumerate(sheet.rows):
                if hbp_col is None or hbp_col >= len(row) or not non_empty(row[hbp_col]):
                    continue
                status = str(row[hbp_col]).strip().lower()
                excel_row = header_offset + 1 + r_idx
                claims_production = any(
                    m in status for m in ("hbp", "held by production", "producing", "active")
                )
                if not claims_production:
                    continue
                checked += 1
                well_ref = (
                    str(row[well_col]).strip().lower()
                    if well_col is not None and well_col < len(row) and non_empty(row[well_col])
                    else ""
                )
                supported = well_ref and well_ref in found_refs
                if not supported:
                    results.append(
                        self._escalate(
                            affected_sheet=sheet.name,
                            affected_cell_or_range=f"row {excel_row}",
                            affected_subject=well_ref or f"{sheet.name} row {excel_row}",
                            reason="HBP/production claim lacks source-backed support.",
                            evidence=f"status={status!r} well={well_ref!r}",
                            failure_category=FailureCategory.HBP_UNSUPPORTED,
                            recommended_action=(
                                "Provide production/well-status source; examiner must "
                                "confirm HBP support."
                            ),
                            confidence=0.9,
                        )
                    )
        if checked == 0 and not well_sheets:
            return [
                self._skip("No wells sheet present; HBP support not applicable.")
            ]
        if not results:
            results.append(
                self._passed(
                    affected_subject="wells",
                    reason=f"HBP/production claims supported ({checked} checked).",
                    confidence=0.85,
                )
            )
        return results
