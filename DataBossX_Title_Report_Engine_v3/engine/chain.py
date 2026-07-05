"""Task 10 -- build the ownership chain per tract from parsed runsheet evidence.

All ownership/acreage math uses :class:`fractions.Fraction` (exact) and
:class:`decimal.Decimal` -- never Python float. The rules enforced:

  * a grantor conveys no more than they own (over-conveyance is flagged, not
    silently clamped away);
  * a grantee receives only the conveyed interest; the grantor retains the rest;
  * a lease/OGL creates leasehold, not a transfer of mineral fee;
  * an assignment (ASSN) transfers leasehold only;
  * reservations remain with the reserver;
  * a tract is never balanced by fabricating ownership -- an untieable chain is
    tagged Needs Examiner Review.
"""

from __future__ import annotations

from decimal import Decimal
from fractions import Fraction
from typing import Dict, List, Optional

from .models import (Assumption, ChainEvent, EvidenceRow, FinalOwner, ReviewFlag,
                     TractResult)
from .utils import (FULL, InterestError, fmt_acres, format_fraction, get_logger,
                    parse_acres, quantize_acres, try_parse_interest)

log = get_logger()

# Instrument types that move mineral fee ownership.
FEE_CONVEYANCES = {"WD", "QCD", "MD"}
# Leasehold-only instruments.
LEASEHOLD = {"OGL", "ASSN"}
# Non-transferring / informational.
INFORMATIONAL = {"AFF", "PROBATE", "ORDER", "TRUST", "REL", "MTG", "ESMT",
                 "POOLING", "RD", "REVIEW"}


def group_by_tract(rows: List[EvidenceRow]) -> Dict[str, List[EvidenceRow]]:
    groups: Dict[str, List[EvidenceRow]] = {}
    for r in rows:
        key = (r.tract or "1").strip() or "1"
        groups.setdefault(key, []).append(r)
    return groups


def _acres_to_fraction(acres: Optional[Decimal], control: Optional[Decimal]) -> Optional[Fraction]:
    if acres is None or control in (None, Decimal(0)):
        return None
    return Fraction(acres) / Fraction(control)


def determine_control_acres(rows: List[EvidenceRow],
                            template_acres: Optional[Decimal],
                            tract: str) -> tuple[Optional[Decimal], str, Optional[Assumption]]:
    """Pick the tract's control acreage from the best available source.

    Priority: template tract total > explicit runsheet acres > None (flagged).
    Section 31 is NOT assumed to be 640 acres.
    """
    if template_acres is not None:
        return quantize_acres(template_acres), "template tract total", None
    # Look for a control-acreage signal in the runsheet rows (largest gross acres
    # among the earliest fee instruments is a reasonable control basis).
    candidates = [parse_acres(r.acres) for r in rows if parse_acres(r.acres)]
    if candidates:
        control = max(candidates)
        assn = Assumption(
            tract=tract, kind="control_acreage",
            statement=f"ASSUMPTION: Control acreage for Tract {tract} taken as "
                      f"{fmt_acres(control)} ac from the largest gross acreage in the "
                      "runsheet; no template tract total was available.",
            basis="runsheet gross acreage", confidence_penalty=8.0,
        )
        return quantize_acres(control), "runsheet gross acreage (assumed)", assn
    return None, "unknown", Assumption(
        tract=tract, kind="control_acreage",
        statement=f"ASSUMPTION: Control acreage for Tract {tract} could not be "
                  "determined from any source; tract cannot be balanced until the "
                  "legal description / acreage is supplied.",
        basis="none", confidence_penalty=20.0,
    )


def build_tract_chain(tract: str, rows: List[EvidenceRow],
                      template_acres: Optional[Decimal] = None) -> TractResult:
    result = TractResult(tract=tract)
    control, source, control_assn = determine_control_acres(rows, template_acres, tract)
    result.control_acres = fmt_acres(control) if control is not None else None
    result.control_source = source
    if control_assn:
        result.assumptions.append(control_assn)
        result.flags.append(ReviewFlag(
            tract=tract, severity="yellow", category="acreage",
            message=control_assn.statement,
            recommended_action="Confirm tract control acreage from the recorded legal description."))

    # Order events chronologically where a date exists; stable otherwise.
    def _key(r: EvidenceRow):
        d = r.recording_date or r.effective_date or r.instrument_date or ""
        return (d or "9999", r.source_row or 0)
    ordered = sorted(rows, key=_key)

    # Ownership ledger: owner -> Fraction of the mineral fee (of the control tract).
    ledger: Dict[str, Fraction] = {}
    opening_set = False

    for seq, row in enumerate(ordered, start=1):
        ev = ChainEvent(
            tract=tract, seq=seq,
            instrument_number=row.instrument_number,
            instrument_type=row.instrument_type,
            instrument_date=row.instrument_date or row.recording_date or row.effective_date,
            grantor=row.grantor or row.assignor or row.lessor,
            grantee=row.grantee or row.assignee or row.lessee,
            evidence=f"{row.source_file}#{row.source_sheet}!row{row.source_row}",
            confidence=row.confidence,
            ogl_reference=row.ogl_number,
        )
        itype = row.instrument_type

        if itype in FEE_CONVEYANCES:
            _apply_fee_conveyance(result, ledger, ev, row, control, opening_set)
            opening_set = True
        elif itype in LEASEHOLD:
            _apply_leasehold(result, ev, row, itype)
        else:  # informational / burden / review
            _apply_informational(result, ev, row, itype)

        result.events.append(ev)

    _finalize_owners(result, ledger, control, ordered)
    _score_tract(result, control)
    return result


def _apply_fee_conveyance(result, ledger, ev, row, control, opening_set):
    tract = result.tract
    grantor = ev.grantor
    grantee = ev.grantee
    conv_frac = try_parse_interest(row.conveyed_interest)
    conv_acres = parse_acres(row.acres)
    reserved = try_parse_interest(row.reserved_interest)

    # Establish opening ownership if this is the first fee event and grantor unknown.
    grantor_held = ledger.get(grantor)
    if grantor_held is None and not opening_set:
        # Opening assumption: grantor is treated as the opening owner of the
        # full mineral estate of the tract (best-supported earliest chain).
        grantor_held = FULL
        ledger[grantor] = FULL
        result.assumptions.append(Assumption(
            tract=tract, kind="opening_ownership",
            statement=f"ASSUMPTION: Opening ownership vested in {grantor or '(unnamed grantor)'} "
                      f"as the earliest grantor in the runsheet for Tract {tract}; prior vesting "
                      "is not present in the source file.",
            basis="earliest runsheet fee instrument", confidence_penalty=10.0))
        result.flags.append(ReviewFlag(
            tract=tract, severity="yellow", category="opening_vesting",
            message=f"Opening ownership assumed for {grantor}; verify patent/prior chain.",
            instrument_number=row.instrument_number,
            recommended_action="Confirm sovereignty-to-first-grantor chain."))
    elif grantor_held is None:
        grantor_held = Fraction(0)
        result.flags.append(ReviewFlag(
            tract=tract, severity="red", category="chain_gap",
            message=f"Grantor {grantor} not a current owner in the chain "
                    f"(instrument {row.instrument_number}); possible missing prior conveyance.",
            instrument_number=row.instrument_number,
            recommended_action="Locate the deed that vested this grantor."))

    # Determine conveyed fraction: explicit interest wins; else derive from acres.
    if conv_frac is None and conv_acres is not None and control:
        conv_frac = _acres_to_fraction(conv_acres, control)
    if conv_frac is None:
        # "all right title and interest" -> convey everything grantor owns.
        conv_frac = grantor_held
        ev.notes = _join(ev.notes,
                         "Conveyed interest not stated; treated as all of grantor's calculated interest.")

    # Over-conveyance guard: never convey more than owned.
    if conv_frac > grantor_held:
        result.flags.append(ReviewFlag(
            tract=tract, severity="red", category="over_conveyance",
            message=f"Over-conveyance avoided: {grantor} conveyed {format_fraction(conv_frac)} "
                    f"but held {format_fraction(grantor_held)} (instr {row.instrument_number}).",
            instrument_number=row.instrument_number,
            recommended_action="Reconcile the over-conveyance before relying on the balance."))
        ev.flag = "OVER-CONVEYANCE"
        ev.notes = _join(ev.notes,
                         f"Over-conveyance avoided: deed described {format_fraction(conv_frac)} "
                         f"but grantor held {format_fraction(grantor_held)}.")
        conv_frac = grantor_held  # limit to owned; flagged above (not silent)

    # Reservation stays with grantor (reduce conveyed accordingly if expressed).
    if reserved is not None and reserved > 0:
        conv_frac = max(Fraction(0), conv_frac - reserved)
        ev.notes = _join(ev.notes,
                         f"Grantor reserved {format_fraction(reserved)}; reservation preserved with grantor.")

    before = grantor_held
    after_grantor = before - conv_frac
    ledger[grantor] = after_grantor
    ledger[grantee] = ledger.get(grantee, Fraction(0)) + conv_frac

    ev.action = f"{ev.instrument_type}: convey {format_fraction(conv_frac)}"
    ev.before_acres = _frac_acres(before, control)
    ev.conveyed_acres = _frac_acres(conv_frac, control)
    ev.after_acres = _frac_acres(after_grantor, control)
    ev.retained_acres = _frac_acres(after_grantor, control)
    if not ev.notes:
        ev.notes = f"{ev.instrument_type} conveyed {format_fraction(conv_frac)} of the tract."


def _apply_leasehold(result, ev, row, itype):
    tract = result.tract
    if itype == "OGL":
        ev.action = "OGL: leasehold created (mineral fee unchanged)"
        ev.ogl_reference = row.ogl_number or row.lease_number
        ev.notes = _join(ev.notes,
                         "OGL creates leasehold only; mineral ownership unchanged. "
                         "OGL carried beside the leased owner per Tract 1 pattern.")
    else:  # ASSN
        ev.action = "ASSN: leasehold interest transferred (mineral fee unchanged)"
        ev.assn_reference = row.book_page or row.instrument_number
        ev.notes = _join(ev.notes,
                         "ASSN transfers leasehold only; mineral ownership unchanged. "
                         "Assignment recording reference kept out of the OGL column.")


def _apply_informational(result, ev, row, itype):
    tract = result.tract
    label = {
        "AFF": "Affidavit", "PROBATE": "Probate", "ORDER": "Order",
        "TRUST": "Trust", "REL": "Release", "MTG": "Mortgage",
        "ESMT": "Easement", "POOLING": "Pooling", "RD": "Royalty Deed",
        "REVIEW": "Unclassified instrument",
    }.get(itype, itype)
    ev.action = f"{itype}: {label} (no mineral fee transfer)"
    if itype in {"PROBATE", "AFF", "ORDER", "TRUST"}:
        ev.notes = _join(ev.notes, f"{label} noted; succession/curative effect carried into chain.")
        result.flags.append(ReviewFlag(
            tract=tract, severity="yellow", category="succession",
            message=f"{label} present (instr {row.instrument_number}); "
                    "verify heirship/succession is fully supported.",
            instrument_number=row.instrument_number,
            recommended_action="Confirm complete probate/heirship documentation."))
    elif itype == "RD":
        ev.notes = _join(ev.notes, "Royalty deed conveys royalty/NPRI burden; carried, mineral fee unchanged.")
    elif itype == "REVIEW":
        ev.flag = "REVIEW"
        ev.notes = _join(ev.notes, "Instrument type could not be normalized; needs examiner review.")
        result.flags.append(ReviewFlag(
            tract=tract, severity="yellow", category="unclassified_instrument",
            message=f"Instrument {row.instrument_number} type unresolved ('{row.raw_instrument_type}').",
            instrument_number=row.instrument_number,
            recommended_action="Classify the instrument type."))


def _finalize_owners(result, ledger, control, ordered):
    tract = result.tract
    # Build an OGL lookup: leased owner -> OGL number (carry-down per Tract 1).
    ogl_by_owner: Dict[str, str] = {}
    for r in ordered:
        if r.instrument_type == "OGL" and (r.ogl_number or r.lease_number):
            owner = r.lessor or r.grantor
            if owner:
                ogl_by_owner[owner] = r.ogl_number or r.lease_number

    total = Fraction(0)
    for owner, frac in ledger.items():
        if not owner or frac == 0:
            continue  # intermediate who conveyed everything -> off the title sheet
        if frac < 0:
            result.flags.append(ReviewFlag(
                tract=tract, severity="red", category="negative_interest",
                message=f"Negative interest computed for {owner} ({format_fraction(frac)}); "
                        "chain inconsistency.",
                recommended_action="Re-examine conveyances into/out of this owner."))
            continue
        total += frac
        result.final_owners.append(FinalOwner(
            tract=tract, owner=owner,
            conveyance_type="retained/current",
            net_acres=_frac_acres(frac, control),
            mineral_interest=format_fraction(frac),
            ogl_number=ogl_by_owner.get(owner, ""),
            status="ok",
            notes="OGL carried beside leased owner per Tract 1 pattern." if owner in ogl_by_owner else "",
        ))

    # Balance check against control (in interest terms, total should be 1).
    if control is not None:
        if total == FULL:
            result.balanced = True
            result.balance_note = f"Ownership sums to 8/8 across {fmt_acres(control)} ac."
        else:
            result.balanced = False
            result.balance_note = (f"Ownership sums to {format_fraction(total)} of the tract "
                                   f"(expected 8/8); tract does not balance.")
            result.flags.append(ReviewFlag(
                tract=tract, severity="red", category="balance",
                message=result.balance_note,
                recommended_action="Locate the missing conveyance(s) to tie the chain to 8/8."))
    else:
        result.balance_note = "No control acreage; balance cannot be verified."
    # Sort owners by descending interest for a clean title sheet.
    result.final_owners.sort(key=lambda o: try_parse_interest(o.mineral_interest) or Fraction(0),
                             reverse=True)


def _score_tract(result, control):
    """Task 16 -- evidence score 0..100 from concrete chain conditions."""
    score = 100
    reasons = []
    if control is None:
        score -= 25; reasons.append("no control acreage")
    if not result.balanced:
        score -= 20; reasons.append("does not balance to 8/8")
    for f in result.flags:
        if f.severity == "red":
            score -= 10
        elif f.severity == "yellow":
            score -= 4
    for a in result.assumptions:
        score -= int(a.confidence_penalty)
    if not result.events:
        score = min(score, 30); reasons.append("no chain events")
    result.evidence_score = max(0, min(100, score))
    if reasons:
        result.balance_note = _join(result.balance_note, "Score drivers: " + ", ".join(reasons))


# ------------------------------------------------------------------ helpers
def _frac_acres(frac: Optional[Fraction], control: Optional[Decimal]) -> str:
    if frac is None or control is None:
        return ""
    return fmt_acres(Decimal(frac.numerator) * control / Decimal(frac.denominator))


def _join(a: str, b: str) -> str:
    return (a + " " + b).strip() if a else b


def build_all(rows: List[EvidenceRow],
              template_acres_by_tract: Optional[Dict[str, Decimal]] = None) -> List[TractResult]:
    template_acres_by_tract = template_acres_by_tract or {}
    results = []
    for tract, tract_rows in sorted(group_by_tract(rows).items(), key=lambda kv: kv[0]):
        results.append(build_tract_chain(tract, tract_rows,
                                         template_acres_by_tract.get(tract)))
    return results
