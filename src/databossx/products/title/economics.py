from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .ledger import Defect, fraction_text, recording_reference_key


@dataclass(frozen=True)
class EconomicLedgerEntry:
    sequence_no: int
    event_kind: str
    recording_reference: str
    from_party: str
    to_party: str
    conveyed: Fraction
    from_before: Fraction
    from_after: Fraction
    to_after: Fraction


@dataclass(frozen=True)
class EconomicResult:
    unit_id: str
    unit_label: str
    gross_acres: Fraction
    leased_mineral_fraction: Fraction
    base_royalty: Fraction
    leasehold: dict[str, Fraction]
    working_interest: dict[str, Fraction]
    nri: dict[str, Fraction]
    burdens_received: dict[str, Fraction]
    net_leasehold_acres: dict[str, Fraction]
    tract_weighted_wi: dict[str, Fraction]
    tract_weighted_nri: dict[str, Fraction]
    royalty_share: Fraction
    entries: tuple[EconomicLedgerEntry, ...]
    defects: tuple[Defect, ...]

    @property
    def blocking_defects(self) -> tuple[Defect, ...]:
        return tuple(defect for defect in self.defects if defect.severity == "BLOCKING")


def _fraction(row: dict, prefix: str = "interest") -> Fraction:
    return Fraction(int(row[f"{prefix}_num"]), int(row[f"{prefix}_den"]))


def _defect(
    code: str,
    detail: str,
    event: dict | None = None,
) -> Defect:
    return Defect(
        code=code,
        severity="BLOCKING",
        detail=detail,
        sequence_no=int(event["sequence_no"]) if event else None,
        recording_reference=str(event["recording_reference"]) if event else None,
    )


def calculate_economics(unit: dict, events: list[dict]) -> EconomicResult:
    unit_id = str(unit["id"])
    label = str(unit["unit_label"])
    gross = _fraction(unit, "gross_acres")
    mineral = _fraction(unit, "leased_mineral")
    royalty = _fraction(unit, "base_royalty")
    defects: list[Defect] = []
    entries: list[EconomicLedgerEntry] = []

    if unit["review_status"] != "REVIEWED" or not unit.get("evidence_span_sha256"):
        defects.append(_defect("ECONOMIC_UNIT_NEEDS_REVIEW", f"{label} is not reviewed"))
    if gross <= 0:
        defects.append(_defect("INVALID_GROSS_ACRES", f"{label} gross acres must be positive"))
    if not 0 < mineral <= 1:
        defects.append(
            _defect(
                "INVALID_LEASED_MINERAL_FRACTION",
                f"{label} leased mineral fraction is {fraction_text(mineral)}",
            )
        )
    if not 0 <= royalty < 1:
        defects.append(
            _defect(
                "INVALID_BASE_ROYALTY",
                f"{label} base royalty is {fraction_text(royalty)}",
            )
        )
    if str(unit.get("unsupported_terms", "")).strip():
        defects.append(
            _defect(
                "UNSUPPORTED_ECONOMIC_TERM",
                f"{label}: {unit['unsupported_terms']}",
            )
        )

    usable_events: list[dict] = []
    seen: set[str] = set()
    for event in sorted(events, key=lambda row: int(row["sequence_no"])):
        key = event.get("recording_reference_key") or recording_reference_key(
            str(event["recording_reference"])
        )
        if key in seen:
            defects.append(
                _defect(
                    "DUPLICATE_ECONOMIC_EVENT",
                    f"{label} repeats recording reference {event['recording_reference']}",
                    event,
                )
            )
            continue
        seen.add(key)
        if event["review_status"] != "REVIEWED" or not event.get(
            "evidence_span_sha256"
        ):
            defects.append(
                _defect(
                    "ECONOMIC_EVENT_NEEDS_REVIEW",
                    f"{label} event {event['recording_reference']} is not reviewed",
                    event,
                )
            )
            continue
        usable_events.append(event)

    leasehold: dict[str, Fraction] = {}
    for event in usable_events:
        if event["event_kind"] != "OPENING_LEASEHOLD":
            continue
        amount = _fraction(event)
        if event["interest_basis"] != "ABSOLUTE_UNIT" or amount < 0:
            defects.append(
                _defect(
                    "INVALID_OPENING_LEASEHOLD",
                    "Opening leasehold requires a nonnegative absolute unit share",
                    event,
                )
            )
            continue
        owner = str(event["to_party"])
        leasehold[owner] = leasehold.get(owner, Fraction()) + amount
    opening_total = sum(leasehold.values(), Fraction())
    if opening_total != 1:
        defects.append(
            _defect(
                "OPENING_LEASEHOLD_NOT_BALANCED",
                f"{label} opening leasehold totals {fraction_text(opening_total)}, not 1",
            )
        )

    for event in usable_events:
        if event["event_kind"] != "ASSIGNMENT":
            continue
        assignor = str(event.get("from_party") or "")
        assignee = str(event["to_party"])
        before = leasehold.get(assignor)
        if before is None:
            defects.append(
                _defect(
                    "LEASEHOLD_CHAIN_GAP",
                    f"{assignor or 'Missing assignor'} has no established leasehold",
                    event,
                )
            )
            continue
        stated = _fraction(event)
        conveyed = (
            stated * before
            if event["interest_basis"] == "OF_ASSIGNOR"
            else stated
        )
        if event["interest_basis"] not in {"OF_ASSIGNOR", "ABSOLUTE_UNIT"}:
            defects.append(
                _defect(
                    "INVALID_ASSIGNMENT_BASIS",
                    "Assignment basis must be absolute unit or of assignor",
                    event,
                )
            )
            continue
        if conveyed < 0 or conveyed > before:
            defects.append(
                _defect(
                    "LEASEHOLD_OVER_ASSIGNMENT",
                    f"{assignor} attempted {fraction_text(conveyed)} from "
                    f"{fraction_text(before)}",
                    event,
                )
            )
            continue
        leasehold[assignor] = before - conveyed
        leasehold[assignee] = leasehold.get(assignee, Fraction()) + conveyed
        entries.append(
            EconomicLedgerEntry(
                sequence_no=int(event["sequence_no"]),
                event_kind="ASSIGNMENT",
                recording_reference=str(event["recording_reference"]),
                from_party=assignor,
                to_party=assignee,
                conveyed=conveyed,
                from_before=before,
                from_after=leasehold[assignor],
                to_after=leasehold[assignee],
            )
        )
    leasehold = {party: value for party, value in leasehold.items() if value}
    if sum(leasehold.values(), Fraction()) != opening_total:
        raise AssertionError("Leasehold conservation invariant failed")

    if unit["wi_basis"] == "WI_EQUALS_LEASEHOLD":
        working_interest = dict(leasehold)
    else:
        working_interest: dict[str, Fraction] = {}
        for event in usable_events:
            if event["event_kind"] != "WORKING_INTEREST":
                continue
            if event["interest_basis"] != "ABSOLUTE_UNIT":
                defects.append(
                    _defect(
                        "INVALID_WI_ALLOCATION",
                        "Explicit working interest must use an absolute unit share",
                        event,
                    )
                )
                continue
            party = str(event["to_party"])
            working_interest[party] = working_interest.get(party, Fraction()) + _fraction(
                event
            )
    wi_total = sum(working_interest.values(), Fraction())
    if wi_total != 1:
        defects.append(
            _defect(
                "WI_TOTAL_NOT_BALANCED",
                f"{label} working interest totals {fraction_text(wi_total)}, not 1",
            )
        )

    burdens_paid: dict[str, Fraction] = {}
    burdens_received: dict[str, Fraction] = {}
    for event in usable_events:
        if event["event_kind"] != "REVENUE_BURDEN":
            continue
        payer = str(event.get("from_party") or "")
        recipient = str(event["to_party"])
        amount = _fraction(event)
        if event["interest_basis"] != "LEASE_8_8" or not event.get("burden_kind"):
            defects.append(
                _defect(
                    "UNALLOCATED_REVENUE_BURDEN",
                    "Revenue burdens require a payer, kind, and lease-8/8 amount",
                    event,
                )
            )
            continue
        if payer not in working_interest:
            defects.append(
                _defect(
                    "UNALLOCATED_REVENUE_BURDEN",
                    f"Burden payer {payer or 'missing'} has no working interest",
                    event,
                )
            )
            continue
        burdens_paid[payer] = burdens_paid.get(payer, Fraction()) + amount
        burdens_received[recipient] = burdens_received.get(recipient, Fraction()) + amount

    nri: dict[str, Fraction] = {}
    for party, wi in working_interest.items():
        available = wi * (1 - royalty)
        burden = burdens_paid.get(party, Fraction())
        if burden > available:
            defects.append(
                _defect(
                    "BURDEN_EXCEEDS_OWNER_REVENUE",
                    f"{party} burden {fraction_text(burden)} exceeds "
                    f"{fraction_text(available)}",
                )
            )
        nri[party] = available - burden
    for party, burden in burdens_received.items():
        nri[party] = nri.get(party, Fraction()) + burden

    revenue_total = sum(nri.values(), Fraction()) + royalty
    if revenue_total != 1:
        defects.append(
            _defect(
                "REVENUE_CONSERVATION_FAILURE",
                f"{label} NRI plus royalty totals {fraction_text(revenue_total)}, not 1",
            )
        )
    net_leasehold_acres = {
        party: gross * mineral * share for party, share in leasehold.items()
    }
    tract_weighted_wi = {
        party: mineral * share for party, share in working_interest.items()
    }
    tract_weighted_nri = {party: mineral * share for party, share in nri.items()}
    return EconomicResult(
        unit_id=unit_id,
        unit_label=label,
        gross_acres=gross,
        leased_mineral_fraction=mineral,
        base_royalty=royalty,
        leasehold=leasehold,
        working_interest=working_interest,
        nri=nri,
        burdens_received=burdens_received,
        net_leasehold_acres=net_leasehold_acres,
        tract_weighted_wi=tract_weighted_wi,
        tract_weighted_nri=tract_weighted_nri,
        royalty_share=mineral * royalty,
        entries=tuple(entries),
        defects=tuple(defects),
    )
