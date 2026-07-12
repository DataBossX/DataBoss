"""Evidence-bound exact WI, NRI, and net leasehold acreage calculations."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, localcontext
from enum import Enum
from fractions import Fraction
from typing import Any, Iterable

from horizon.interest import InterestError, format_fraction, net_acres, parse_acres, parse_interest

from .security import EvidenceStatus


class BurdenBasis(str, Enum):
    GROSS_PRODUCTION = "GROSS_PRODUCTION"
    WORKING_INTEREST = "WORKING_INTEREST"


_BLOCKING_EVIDENCE = {
    EvidenceStatus.INFERRED,
    EvidenceStatus.ASSUMED,
    EvidenceStatus.ESTIMATED,
    EvidenceStatus.CONFLICTED,
    EvidenceStatus.MISSING,
    EvidenceStatus.REJECTED,
    EvidenceStatus.NOT_APPLICABLE,
}


@dataclass(frozen=True)
class EvidenceValue:
    value: Any
    evidence_refs: tuple[str, ...]
    status: EvidenceStatus = EvidenceStatus.EXTRACTED_UNVERIFIED
    source_expression: str = ""

    def __post_init__(self) -> None:
        refs = (
            (self.evidence_refs,)
            if isinstance(self.evidence_refs, str)
            else tuple(self.evidence_refs)
        )
        object.__setattr__(self, "evidence_refs", refs)


@dataclass(frozen=True)
class ExactValue:
    numerator: int
    denominator: int
    decimal_display: str
    source_expression: str
    evidence_refs: tuple[str, ...]

    @property
    def fraction(self) -> Fraction:
        return Fraction(self.numerator, self.denominator)

    @property
    def fraction_display(self) -> str:
        return format_fraction(self.fraction)


@dataclass(frozen=True)
class TitleInterestResult:
    status: str
    working_interest: ExactValue | None = None
    net_revenue_interest: ExactValue | None = None
    net_leasehold_acres: ExactValue | None = None
    burden_basis: BurdenBasis | None = None
    source_expression: str = ""
    trace: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()

    @property
    def blocked(self) -> bool:
        return self.status == "BLOCKED"

    @property
    def numerator(self) -> int | None:
        return self.net_revenue_interest.numerator if self.net_revenue_interest else None

    @property
    def denominator(self) -> int | None:
        return self.net_revenue_interest.denominator if self.net_revenue_interest else None

    @property
    def decimal_display(self) -> str | None:
        return self.net_revenue_interest.decimal_display if self.net_revenue_interest else None


def _decimal_display(value: Fraction, places: int = 12) -> str:
    with localcontext() as context:
        context.prec = max(28, places + 10)
        decimal = Decimal(value.numerator) / Decimal(value.denominator)
        rendered = f"{decimal:.{places}f}".rstrip("0").rstrip(".")
    return rendered or "0"


def _exact(
    value: Fraction,
    expression: str,
    evidence_refs: Iterable[str],
) -> ExactValue:
    return ExactValue(
        numerator=value.numerator,
        denominator=value.denominator,
        decimal_display=_decimal_display(value),
        source_expression=expression,
        evidence_refs=tuple(dict.fromkeys(evidence_refs)),
    )


def _validate_input(name: str, item: EvidenceValue, blockers: list[str]) -> None:
    if not item.evidence_refs or any(not str(ref).strip() for ref in item.evidence_refs):
        blockers.append(f"{name}: evidence reference required")
    if item.status in _BLOCKING_EVIDENCE:
        blockers.append(f"{name}: evidence status {item.status.value} is not calculable")
    if item.value is None or not str(item.value).strip():
        blockers.append(f"{name}: value is missing")


def calculate_title_interest(
    working_interest: EvidenceValue,
    royalty_burden: EvidenceValue,
    gross_acres: EvidenceValue,
    burden_basis: BurdenBasis | str,
) -> TitleInterestResult:
    """Calculate exact values, blocking missing, conflicting, or ambiguous input.

    A gross-production burden is subtracted from WI. A working-interest burden
    is multiplied by WI. This distinction is material and is never inferred.
    """

    blockers: list[str] = []
    for name, item in (
        ("working_interest", working_interest),
        ("royalty_burden", royalty_burden),
        ("gross_acres", gross_acres),
    ):
        _validate_input(name, item, blockers)
    try:
        if isinstance(burden_basis, BurdenBasis):
            basis = burden_basis
        else:
            basis = BurdenBasis(burden_basis)
    except (TypeError, ValueError):
        basis = None
        blockers.append("burden_basis: must be GROSS_PRODUCTION or WORKING_INTEREST")
    if blockers:
        return TitleInterestResult("BLOCKED", burden_basis=basis, blockers=tuple(blockers))

    try:
        wi = parse_interest(working_interest.value)
        burden = parse_interest(royalty_burden.value)
        acres = parse_acres(gross_acres.value)
    except InterestError as exc:
        return TitleInterestResult(
            "BLOCKED",
            burden_basis=basis,
            blockers=(f"ambiguous or invalid exact input: {exc}",),
        )
    range_errors = []
    if not 0 <= wi <= 1:
        range_errors.append("working_interest must be between 0 and 1")
    if not 0 <= burden <= 1:
        range_errors.append("royalty_burden must be between 0 and 1")
    if acres < 0:
        range_errors.append("gross_acres cannot be negative")
    if range_errors:
        return TitleInterestResult("BLOCKED", burden_basis=basis, blockers=tuple(range_errors))

    wi_expression = working_interest.source_expression or str(working_interest.value)
    burden_expression = royalty_burden.source_expression or str(royalty_burden.value)
    acres_expression = gross_acres.source_expression or str(gross_acres.value)
    if basis is BurdenBasis.GROSS_PRODUCTION:
        nri = wi - burden
        nri_expression = f"({wi_expression}) - ({burden_expression})"
        trace_line = (
            f"NRI = WI - gross-production burden = "
            f"{format_fraction(wi)} - {format_fraction(burden)} = {format_fraction(nri)}"
        )
    else:
        nri = wi * (Fraction(1) - burden)
        nri_expression = f"({wi_expression}) * (1 - ({burden_expression}))"
        trace_line = (
            f"NRI = WI × (1 - WI-basis burden) = {format_fraction(wi)} × "
            f"(1 - {format_fraction(burden)}) = {format_fraction(nri)}"
        )
    if nri < 0:
        return TitleInterestResult(
            "BLOCKED",
            burden_basis=basis,
            blockers=("royalty burden produces negative NRI",),
            trace=(trace_line,),
        )

    nla = net_acres(wi, acres)
    acreage_expression = f"({wi_expression}) * ({acres_expression})"
    trace = (
        f"WI = {format_fraction(wi)}",
        trace_line,
        f"Net leasehold acres = WI × gross acres = {format_fraction(wi)} × "
        f"{format_fraction(acres)} = {format_fraction(nla)}",
    )
    return TitleInterestResult(
        status="CALCULATED",
        working_interest=_exact(wi, wi_expression, working_interest.evidence_refs),
        net_revenue_interest=_exact(
            nri,
            nri_expression,
            (*working_interest.evidence_refs, *royalty_burden.evidence_refs),
        ),
        net_leasehold_acres=_exact(
            nla,
            acreage_expression,
            (*working_interest.evidence_refs, *gross_acres.evidence_refs),
        ),
        burden_basis=basis,
        source_expression=nri_expression,
        trace=trace,
        blockers=(),
    )
