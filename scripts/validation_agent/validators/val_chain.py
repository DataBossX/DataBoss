"""Chain-of-title continuity and vesting (Gate 5).

Walks the runsheet in recorded order and proves an unbroken grantor->grantee
trace: the grantor on every conveyance must already be vested (a grantee in a
prior link, or the origin of the chain).  A break -- a grantor who never
received title, or an heirship/estate transfer with no probate instrument -- is
a Critical, MANDATORY escalation.

This gate NEVER proposes an automated repair.  Bridging a vesting gap requires
a legal fact (a deed, a probate, an affidavit of heirship) that the system is
forbidden from inventing (Golden Law #3/#4).
"""

from __future__ import annotations

import re

from ..models import CellRef, FailureCategory, Finding, GateResult, GateStatus, Severity
from ..ingestion.sheet_classifier import SheetCategory
from ._helpers import data_cells_in_column, find_header_column, is_total_row
from .base_validator import ValidatorBase

_PROBATE_TOKENS = ("probate", "heirship", "estate", "affidavit of death",
                   "will", "intestate", "decedent", "deceased")


def _normalize_party(name: str) -> str:
    n = name.upper().strip()
    n = re.sub(r"\b(ET\s+UX|ET\s+AL|ET\s+VIR)\b\.?", "", n)
    n = re.sub(r"\b(A\s+SINGLE\s+PERSON|HUSBAND\s+AND\s+WIFE|TRUSTEE|"
               r"AS\s+JOINT\s+TENANTS)\b", "", n)
    n = re.sub(r"[.,;]", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    return n


class ChainValidator(ValidatorBase):
    gate_name = "Chain Continuity"
    gate_ids = (5,)

    def _run(self, manifest) -> list[GateResult]:
        runsheets = manifest.by_category(SheetCategory.RUNSHEET)
        if not runsheets:
            return [GateResult(5, "Chain Continuity", GateStatus.ERROR,
                               detail="No runsheet classified; cannot trace chain.")]

        findings: list[Finding] = []
        links_checked = 0

        for sheet in runsheets:
            grantor_col = find_header_column(sheet, "grantor")
            grantee_col = find_header_column(sheet, "grantee")
            type_col = find_header_column(sheet, "instrument type", "type",
                                          "conveyance type")
            src_col = find_header_column(sheet, "book", "page", "instrument number",
                                         "inst #", "instrument #", "source")
            if not (grantor_col and grantee_col):
                findings.append(Finding(
                    gate_id=5, gate_name="Chain Continuity",
                    category=FailureCategory.MISSING_SOURCE, severity=Severity.CRITICAL,
                    message=(f"Runsheet '{sheet.name}' lacks grantor/grantee "
                             f"columns; chain cannot be traced."),
                    location=CellRef(sheet=sheet.name), subject=sheet.name,
                    repairable=False, escalate=True))
                continue

            vested: set[str] = set()
            first = True
            for g_cell in data_cells_in_column(sheet, grantor_col):
                row = g_cell.row
                if is_total_row(sheet, row) or g_cell.value is None:
                    continue
                grantor = _normalize_party(str(g_cell.value))
                grantee_cell = sheet.cell(f"{grantee_col}{row}")
                grantee = _normalize_party(str(grantee_cell.value)) \
                    if grantee_cell and grantee_cell.value is not None else ""
                itype = self._text(sheet, type_col, row).lower()
                source = self._text(sheet, src_col, row).strip()
                links_checked += 1

                is_probate = any(tok in itype for tok in _PROBATE_TOKENS)

                # Probate/heirship transfer with no recorded instrument.
                if is_probate and not source:
                    findings.append(Finding(
                        gate_id=5, gate_name="Chain Continuity",
                        category=FailureCategory.TITLE_CHAIN_GAP,
                        severity=Severity.CRITICAL,
                        message=(f"Row {row}: '{itype}' transfer from {grantor} "
                                 f"has no probate/affidavit instrument recorded."),
                        location=CellRef(sheet=sheet.name,
                                         cell=f"{grantor_col}{row}"),
                        subject=f"{grantor} (row {row})",
                        repairable=False, escalate=True,
                        evidence={"instrument_type": itype}))

                # Vesting gap: grantor never received title.
                if not first and grantor not in vested:
                    findings.append(Finding(
                        gate_id=5, gate_name="Chain Continuity",
                        category=FailureCategory.TITLE_CHAIN_GAP,
                        severity=Severity.CRITICAL,
                        message=(f"Row {row}: grantor {grantor} is not previously "
                                 f"vested (unexplained vesting gap)."),
                        location=CellRef(sheet=sheet.name,
                                         cell=f"{grantor_col}{row}"),
                        subject=f"{grantor} (row {row})",
                        repairable=False, escalate=True,
                        evidence={"vested_parties": sorted(vested)[:20]}))

                if grantee:
                    vested.add(grantee)
                first = False

        status = GateStatus.PASS if not findings else GateStatus.FAIL
        detail = (f"Unbroken chain across {links_checked} link(s)."
                  if not findings else
                  f"{len(findings)} vesting/probate gap(s) -- mandatory escalation.")
        return [GateResult(5, "Chain Continuity", status, findings, detail,
                           {"links_checked": links_checked})]

    @staticmethod
    def _text(sheet, col, row) -> str:
        if not col:
            return ""
        cell = sheet.cell(f"{col}{row}")
        return str(cell.value) if cell and cell.value is not None else ""
