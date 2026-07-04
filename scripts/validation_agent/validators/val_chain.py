"""Gate 5: Chain Continuity.

Every grantor must have prior vesting (appear as a prior grantee, or be a root
patent/source-of-title). Missing probate / affidavit of heirship escalates.
Chain gaps are NEVER auto-repaired — a gap that can only be closed by assuming
a fact is escalated to a human examiner.
"""

from __future__ import annotations

from typing import Any, Dict, List, Set

from core.enums import FailureCategory, Severity
from .base_validator import ValidationResult, ValidatorBase
from .util import column_index, find_sheets_by_category, non_empty

_GRANTOR_ALIASES = ("grantor", "grantor name", "from", "seller")
_GRANTEE_ALIASES = ("grantee", "grantee name", "to", "buyer")
_TYPE_ALIASES = ("instrument type", "type", "conveyance type", "document type")
_ROOT_MARKERS = ("patent", "source of title", "sovereignty", "root", "state of")
_PROBATE_MARKERS = ("probate", "heirship", "affidavit of heirship", "estate", "decedent",
                    "administrator", "executor", "will")


def _norm(name: Any) -> str:
    return " ".join(str(name).strip().lower().split())


class ChainContinuityGate(ValidatorBase):
    gate_name = "Chain Continuity Gate"

    def validate(self, context: Dict[str, Any]) -> List[ValidationResult]:
        sheets = find_sheets_by_category(context, "runsheet")
        if not sheets:
            return [
                self._escalate(
                    affected_subject="chain",
                    reason="No runsheet available for chain continuity.",
                    failure_category=FailureCategory.MISSING_SOURCE,
                    recommended_action="Confirm a runsheet/chain sheet exists.",
                )
            ]

        results: List[ValidationResult] = []
        prior_grantees: Set[str] = set()
        checked = 0

        for sheet in sheets:
            g_col = column_index(sheet.headers, *_GRANTOR_ALIASES)
            e_col = column_index(sheet.headers, *_GRANTEE_ALIASES)
            t_col = column_index(sheet.headers, *_TYPE_ALIASES)
            if g_col is None or e_col is None:
                continue
            header_offset = sheet.header_row_index or 0
            for r_idx, row in enumerate(sheet.rows):
                grantor = row[g_col] if g_col < len(row) else None
                grantee = row[e_col] if e_col < len(row) else None
                if not non_empty(grantor) and not non_empty(grantee):
                    continue
                excel_row = header_offset + 1 + r_idx
                itype = (
                    _norm(row[t_col]) if (t_col is not None and t_col < len(row)) else ""
                )
                row_blob = _norm(" ".join(str(c) for c in row if c is not None))
                checked += 1

                if non_empty(grantor):
                    gnorm = _norm(grantor)
                    is_root = any(m in gnorm or m in itype or m in row_blob for m in _ROOT_MARKERS)
                    has_prior = gnorm in prior_grantees
                    if not has_prior and not is_root:
                        has_probate = any(m in row_blob for m in _PROBATE_MARKERS)
                        if has_probate:
                            results.append(
                                self._escalate(
                                    affected_sheet=sheet.name,
                                    affected_cell_or_range=f"row {excel_row}",
                                    affected_subject=str(grantor),
                                    reason=(
                                        "Grantor not previously vested; conveyance "
                                        "relies on probate/heirship that must be verified."
                                    ),
                                    evidence=f"grantor={grantor!r}",
                                    failure_category=FailureCategory.TITLE_CHAIN_GAP,
                                    recommended_action=(
                                        "Examiner must confirm probate/affidavit of "
                                        "heirship supports vesting. No auto-repair."
                                    ),
                                    confidence=0.9,
                                )
                            )
                        else:
                            results.append(
                                self._escalate(
                                    affected_sheet=sheet.name,
                                    affected_cell_or_range=f"row {excel_row}",
                                    affected_subject=str(grantor),
                                    reason=(
                                        "Chain gap: grantor has no prior vesting and no "
                                        "root/source-of-title marker."
                                    ),
                                    evidence=f"grantor={grantor!r}",
                                    failure_category=FailureCategory.TITLE_CHAIN_GAP,
                                    recommended_action=(
                                        "Examiner must locate the vesting conveyance or "
                                        "curative. Chain gaps are never auto-repaired."
                                    ),
                                    confidence=0.9,
                                )
                            )
                if non_empty(grantee):
                    prior_grantees.add(_norm(grantee))

        if checked == 0:
            return [
                self._escalate(
                    affected_subject="chain",
                    reason="No grantor/grantee rows found for chain continuity.",
                    failure_category=FailureCategory.MISSING_SOURCE,
                    recommended_action="Confirm runsheet has grantor/grantee columns.",
                )
            ]
        if not results:
            results.append(
                self._passed(
                    affected_subject="chain",
                    reason=f"Chain continuity intact across {checked} conveyance(s).",
                    confidence=0.95,
                )
            )
        return results
