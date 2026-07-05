"""Stage 3 -- chain ownership per tract from runsheet evidence.

This is the heart of the engine. For each tract it walks the instruments in
recording order and maintains a running ledger of fractional mineral ownership:

* A **root** (patent / earliest deed with no identifiable grantor in-section, or
  an explicit ROOT row) seeds 100% ownership.
* A **deed** transfers ``conveyed_interest`` of the grantor's holding to the
  grantee, and lets the grantor **reserve** ``reserved_interest`` (rule: retained
  interests are preserved -- the grantor keeps what they reserved).
* An **assignment (ASSN)** transfers **leasehold only** -- it moves the OGL beside
  an owner, it does NOT change mineral ownership (rule #9).
* A **lease (OGL)** marks the lessor's interest as leased and records the OGL
  number beside that owner (rule #10).

Guard rails: a grantor can never convey more than they own (rule #13); ownership
can never go negative (rule #12). A conveyance that violates either is rejected,
left unapplied, and flagged for examiner review -- never force-fitted.

All math is Decimal. Interests are fractions of the whole tract (0..1); acres are
``interest * tract.gross_acres``.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Dict, List, Optional

from rapidfuzz import fuzz

from .audit import AuditLog
from .models import (ConveyanceType, EvidenceRow, OwnerInterest, ReviewFlag,
                     Tract)

# Two party strings are "the same owner" at/above this fuzzy ratio.
NAME_MATCH_THRESHOLD = 88


def _norm_name(name: str) -> str:
    return " ".join(str(name or "").upper().replace(".", "").replace(",", " ").split())


class Ledger:
    """Running fractional-ownership ledger for one tract during chaining."""

    def __init__(self):
        # canonical-name -> {"display": str, "interest": Decimal, "ogl": str|None,
        #                    "status": str, "sheet": str, "row": int}
        self._owners: Dict[str, dict] = {}

    def _match_key(self, name: str) -> Optional[str]:
        target = _norm_name(name)
        if not target:
            return None
        if target in self._owners:
            return target
        best_key, best_score = None, NAME_MATCH_THRESHOLD - 1
        for key in self._owners:
            score = fuzz.token_sort_ratio(target, key)
            if score > best_score:
                best_key, best_score = key, score
        return best_key

    def interest_of(self, name: str) -> Decimal:
        key = self._match_key(name)
        return self._owners[key]["interest"] if key else Decimal(0)

    def credit(self, name: str, amount: Decimal, *, sheet="", row=None,
               ogl=None, status=None) -> None:
        key = self._match_key(name) or _norm_name(name)
        rec = self._owners.setdefault(key, {
            "display": name.strip(), "interest": Decimal(0), "ogl": None,
            "status": "Unleased", "sheet": sheet, "row": row})
        rec["interest"] += amount
        if ogl is not None:
            rec["ogl"] = ogl
        if status is not None:
            rec["status"] = status
        if not rec["display"]:
            rec["display"] = name.strip()

    def debit(self, name: str, amount: Decimal) -> bool:
        key = self._match_key(name)
        if key is None:
            return False
        if self._owners[key]["interest"] + Decimal("1e-9") < amount:
            return False
        self._owners[key]["interest"] -= amount
        return True

    def set_lease(self, name: str, ogl: Optional[str], status: str) -> bool:
        key = self._match_key(name)
        if key is None:
            return False
        self._owners[key]["ogl"] = ogl
        self._owners[key]["status"] = status
        return True

    def final_owners(self, tract: Tract) -> List[OwnerInterest]:
        owners: List[OwnerInterest] = []
        gross = tract.gross_acres or Decimal(0)
        for rec in self._owners.values():
            interest = rec["interest"]
            if interest <= Decimal("1e-9"):
                continue  # dropped out of title -- rule #6, no intermediates
            nma = (interest * gross) if gross else None
            owners.append(OwnerInterest(
                owner=rec["display"],
                mineral_interest=interest,
                net_mineral_acres=nma,
                lease_number=rec["ogl"],
                lease_status=rec["status"],
                source_sheet=rec["sheet"],
                source_row=rec["row"],
            ))
        owners.sort(key=lambda o: o.mineral_interest, reverse=True)
        return owners


def _quantize(d: Decimal) -> Decimal:
    return d.quantize(Decimal("0.00000001"))


def chain_tract(tract: Tract, audit: AuditLog) -> Tract:
    """Chain one tract's evidence into final owners, recording every action."""
    ledger = Ledger()
    # Recording order; undated rows keep their discovery order (stable sort).
    evidence = sorted(tract.evidence, key=lambda e: (e.recording_date or e.instrument_date or "9999"))

    seeded = False
    for ev in evidence:
        ct = ev.conveyance_type
        sheet, row = ev.source_sheet, ev.source_row

        # --- ROOT: seed ownership -------------------------------------------
        grantor_known = ledger.interest_of(ev.grantor) > 0 if ev.grantor else False
        if ct == ConveyanceType.ROOT or (not seeded and not grantor_known and ev.grantee
                                         and ct in (ConveyanceType.DEED, ConveyanceType.MINERAL_DEED,
                                                    ConveyanceType.WARRANTY_DEED, ConveyanceType.QUITCLAIM)):
            share = ev.conveyed_interest if ev.conveyed_interest is not None else Decimal(1)
            ledger.credit(ev.grantee, _quantize(share), sheet=sheet, row=row)
            audit.record("SEED root ownership", tract=tract.name, source_sheet=sheet,
                         source_row=row, before="(none)",
                         after=f"{ev.grantee} = {share}", evidence=_ev_ref(ev))
            seeded = True
            continue

        # --- LEASE (OGL): mark lessor leased, carry OGL beside owner --------
        if ct == ConveyanceType.LEASE:
            ogl = ev.lease_number
            ok = ledger.set_lease(ev.grantor, ogl, "Leased")
            flag = "" if ok else "unmatched_ogl"
            audit.record("APPLY oil & gas lease", tract=tract.name, source_sheet=sheet,
                         source_row=row, before=f"{ev.grantor} unleased",
                         after=f"{ev.grantor} leased under {ogl or '?'}",
                         evidence=_ev_ref(ev), flag=flag)
            if not ok:
                tract.flags.append(ReviewFlag(
                    tract=tract.name, category="unmatched_ogl", severity="yellow",
                    message=f"OGL {ogl or '?'} lessor '{ev.grantor}' not found in tract ownership",
                    source_sheet=sheet, source_row=row))
            continue

        # --- ASSIGNMENT (ASSN): transfer leasehold only, not minerals -------
        if ct == ConveyanceType.ASSIGNMENT:
            ogl = ev.lease_number
            # An assignment moves the OGL reference; mineral ownership unchanged.
            audit.record("APPLY assignment (ASSN) -- leasehold only", tract=tract.name,
                         source_sheet=sheet, source_row=row,
                         before=f"OGL {ogl or '?'} held by {ev.grantor}",
                         after=f"OGL {ogl or '?'} assigned to {ev.grantee} (minerals unchanged)",
                         evidence=_ev_ref(ev))
            continue

        # --- DEED / MINERAL DEED / etc.: transfer minerals ------------------
        if ct in (ConveyanceType.DEED, ConveyanceType.MINERAL_DEED,
                  ConveyanceType.WARRANTY_DEED, ConveyanceType.QUITCLAIM):
            owned = ledger.interest_of(ev.grantor)
            conveyed = ev.conveyed_interest
            reserved = ev.reserved_interest or Decimal(0)
            if conveyed is None:
                # No fraction given: assume grantor conveys all they own less any
                # stated reservation. Recorded as an assumption for the audit.
                conveyed = _quantize(max(owned - reserved, Decimal(0)))
                assumed = True
            else:
                conveyed = _quantize(conveyed)
                assumed = False

            if owned <= Decimal("1e-9"):
                tract.flags.append(ReviewFlag(
                    tract=tract.name, category="impossible_conveyance", severity="yellow",
                    message=f"Grantor '{ev.grantor}' has no traced interest to convey",
                    source_sheet=sheet, source_row=row))
                audit.record("REJECT conveyance (grantor owns nothing traced)",
                             tract=tract.name, source_sheet=sheet, source_row=row,
                             before=f"{ev.grantor} owns 0", after="(unapplied)",
                             evidence=_ev_ref(ev), flag="impossible_conveyance")
                continue

            if conveyed > owned + Decimal("1e-9"):
                tract.flags.append(ReviewFlag(
                    tract=tract.name, category="impossible_conveyance", severity="yellow",
                    message=(f"Grantor '{ev.grantor}' conveys {conveyed} but owns only "
                             f"{owned} (rule #13)"),
                    source_sheet=sheet, source_row=row))
                audit.record("REJECT conveyance exceeds ownership", tract=tract.name,
                             source_sheet=sheet, source_row=row,
                             before=f"{ev.grantor} owns {owned}",
                             after=f"attempted convey {conveyed} (unapplied)",
                             evidence=_ev_ref(ev), flag="impossible_conveyance")
                continue

            ledger.debit(ev.grantor, conveyed)
            ledger.credit(ev.grantee, conveyed, sheet=sheet, row=row)
            note = " (assumed: all owned less reservation)" if assumed else ""
            audit.record("APPLY conveyance", tract=tract.name, source_sheet=sheet,
                         source_row=row,
                         before=f"{ev.grantor}={owned}",
                         after=f"{ev.grantor}={_quantize(owned - conveyed)}, "
                               f"{ev.grantee}+={conveyed}{note}",
                         evidence=_ev_ref(ev),
                         flag="assumption" if assumed else "")
            if assumed:
                tract.flags.append(ReviewFlag(
                    tract=tract.name, category="assumption", severity="yellow",
                    message=(f"No fraction stated for {ev.grantor}->{ev.grantee}; "
                             f"assumed grantor conveyed all owned ({conveyed}) less "
                             f"reservation {reserved}"),
                    source_sheet=sheet, source_row=row))
            continue

        # --- everything else: recorded but not a mineral mutation -----------
        audit.record(f"NOTE {ct.value} (no ownership change)", tract=tract.name,
                     source_sheet=sheet, source_row=row, evidence=_ev_ref(ev))

    tract.owners = ledger.final_owners(tract)
    return tract


def _ev_ref(ev: EvidenceRow) -> str:
    bits = []
    if ev.instrument_type:
        bits.append(ev.instrument_type)
    if ev.book_page:
        bits.append(f"Bk/Pg {ev.book_page}")
    if ev.instrument_date:
        bits.append(f"dated {ev.instrument_date}")
    bits.append(f"[{ev.source_sheet} r{ev.source_row}]")
    return "; ".join(bits)
