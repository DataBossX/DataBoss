from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Iterable


@dataclass(frozen=True)
class Defect:
    code: str
    severity: str
    detail: str
    sequence_no: int | None = None
    recording_reference: str | None = None


@dataclass(frozen=True)
class LedgerEntry:
    sequence_no: int
    recording_reference: str
    grantor_name: str
    grantee_name: str
    conveyed: Fraction
    grantor_before: Fraction
    grantor_after: Fraction
    grantee_after: Fraction
    estate_total: Fraction


@dataclass(frozen=True)
class LedgerResult:
    ownership: dict[str, Fraction]
    entries: tuple[LedgerEntry, ...]
    defects: tuple[Defect, ...]

    @property
    def blocking_defects(self) -> tuple[Defect, ...]:
        return tuple(defect for defect in self.defects if defect.severity == "BLOCKING")


def fraction_text(value: Fraction) -> str:
    return (
        str(value.numerator)
        if value.denominator == 1
        else f"{value.numerator}/{value.denominator}"
    )


def calculate_ownership(
    opening: Iterable[dict], instruments: Iterable[dict]
) -> LedgerResult:
    ownership: dict[str, Fraction] = {}
    defects: list[Defect] = []
    entries: list[LedgerEntry] = []

    for item in opening:
        owner = str(item["owner_name"]).strip()
        interest = Fraction(int(item["interest_num"]), int(item["interest_den"]))
        if not owner or interest < 0:
            defects.append(
                Defect("INVALID_OPENING_OWNERSHIP", "BLOCKING", "Invalid opening owner")
            )
            continue
        ownership[owner] = ownership.get(owner, Fraction()) + interest

    opening_total = sum(ownership.values(), Fraction())
    if opening_total != Fraction(1):
        defects.append(
            Defect(
                "OPENING_ESTATE_NOT_BALANCED",
                "BLOCKING",
                f"Opening ownership totals {fraction_text(opening_total)}, not 1",
            )
        )

    seen_recordings: set[str] = set()
    for instrument in sorted(instruments, key=lambda item: int(item["sequence_no"])):
        sequence = int(instrument["sequence_no"])
        recording = str(instrument["recording_reference"]).strip()
        grantor = str(instrument["grantor_name"]).strip()
        grantee = str(instrument["grantee_name"]).strip()
        context = {"sequence_no": sequence, "recording_reference": recording}

        if recording in seen_recordings:
            defects.append(
                Defect(
                    "DUPLICATE_INSTRUMENT",
                    "BLOCKING",
                    f"Recording reference {recording} appears more than once",
                    **context,
                )
            )
            continue
        seen_recordings.add(recording)
        if instrument["review_status"] != "REVIEWED":
            defects.append(
                Defect(
                    "INSTRUMENT_NEEDS_REVIEW",
                    "BLOCKING",
                    f"Instrument {recording} has not been examiner-reviewed",
                    **context,
                )
            )
            continue
        if not instrument.get("evidence_asset_version_id"):
            defects.append(
                Defect(
                    "MISSING_EVIDENCE",
                    "BLOCKING",
                    f"Instrument {recording} has no evidence citation",
                    **context,
                )
            )
            continue
        grantor_before = ownership.get(grantor)
        if grantor_before is None:
            defects.append(
                Defect(
                    "CHAIN_GAP",
                    "BLOCKING",
                    f"Grantor {grantor} has no established opening or prior interest",
                    **context,
                )
            )
            continue
        stated = Fraction(
            int(instrument["conveyed_num"]), int(instrument["conveyed_den"])
        )
        if stated < 0:
            defects.append(
                Defect(
                    "INVALID_CONVEYANCE",
                    "BLOCKING",
                    f"Instrument {recording} has a negative conveyance",
                    **context,
                )
            )
            continue
        conveyed = (
            stated * grantor_before
            if instrument["interest_basis"] == "OF_GRANTOR"
            else stated
        )
        if conveyed > grantor_before:
            defects.append(
                Defect(
                    "OVER_CONVEYANCE",
                    "BLOCKING",
                    f"{grantor} conveyed {fraction_text(conveyed)} but held "
                    f"{fraction_text(grantor_before)}",
                    **context,
                )
            )
            continue

        if grantor != grantee:
            ownership[grantor] = grantor_before - conveyed
            ownership[grantee] = ownership.get(grantee, Fraction()) + conveyed
        estate_total = sum(ownership.values(), Fraction())
        if estate_total != opening_total:
            raise AssertionError("Exact ownership conservation invariant failed")
        entries.append(
            LedgerEntry(
                sequence_no=sequence,
                recording_reference=recording,
                grantor_name=grantor,
                grantee_name=grantee,
                conveyed=conveyed,
                grantor_before=grantor_before,
                grantor_after=ownership[grantor],
                grantee_after=ownership[grantee],
                estate_total=estate_total,
            )
        )

    return LedgerResult(
        ownership={owner: value for owner, value in ownership.items() if value},
        entries=tuple(entries),
        defects=tuple(defects),
    )
