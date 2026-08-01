"""Objective candidate scoring.

Transparent metrics, not model vibes. Every dimension is computed from the
candidate output plus the frozen benchmark; nothing is asked of a model, and no
dimension depends on how confident a candidate sounds.

Two dimensions are **blocking**: a candidate that invents values for unreadable
cells, or that asserts values without pointing at the source region, is rejected
regardless of how good its aggregate looks. That is what stops a confident
fabricator from winning on volume.
"""

from __future__ import annotations

from dataclasses import dataclass

RUBRIC_VERSION = "scoring/v1"

ASSERTED_STATES = ("known", "uncertain")
NON_ASSERTED_STATES = ("unreadable", "absent", "not_applicable")


@dataclass(frozen=True)
class Dimension:
    name: str
    weight: float
    blocking: bool = False
    #: Minimum acceptable value for a blocking dimension.
    minimum: float = 0.0
    description: str = ""


DIMENSIONS = (
    Dimension("hallucination_avoidance", 2.0, blocking=True, minimum=0.95,
              description="1 - (confident values invented for unreadable or absent cells)."),
    Dimension("source_region_support", 1.5, blocking=True, minimum=0.90,
              description="Fraction of asserted values citing the correct source region."),
    Dimension("exact_field_agreement", 2.0,
              description="Asserted values matching the benchmark exactly."),
    Dimension("document_number_agreement", 1.0,
              description="Document-number agreement with the benchmark."),
    Dimension("book_page_agreement", 1.0,
              description="Book and page agreement with the benchmark."),
    Dimension("legal_description_agreement", 1.0,
              description="Legal-description agreement with the benchmark."),
    Dimension("party_name_agreement", 1.0,
              description="Grantor and grantee agreement with the benchmark."),
    Dimension("false_omission_avoidance", 1.0,
              description="1 - (legible cells reported as unreadable or absent)."),
    Dimension("internal_consistency", 0.5,
              description="Section/township/range/county/state stable across the candidate."),
    Dimension("confidence_calibration", 0.5,
              description="Confidence tracks correctness rather than volume."),
    Dimension("runsheet_reconciliation_coverage", 1.0,
              description="Share of Runsheet rows an index entry supports."),
    Dimension("benchmark_accuracy", 1.5,
              description="Overall correctness across every benchmarked cell."),
)

DIMENSIONS_BY_NAME = {dimension.name: dimension for dimension in DIMENSIONS}

LOCATION_FIELDS = ("section", "township", "range", "county", "state")
BENCHMARK_FIELDS = (
    "grantor", "grantee", "instrument_type", "recording_date", "execution_date",
    "book", "page", "document_number", "legal_description", "interest_or_burden",
)


@dataclass(frozen=True)
class ScoreCard:
    candidate_id: str
    scores: dict
    details: dict
    aggregate: float
    blocking_failures: tuple
    rubric_version: str = RUBRIC_VERSION

    @property
    def passed_blocking_gates(self) -> bool:
        return not self.blocking_failures

    def to_dict(self) -> dict:
        return {
            "candidate_id": self.candidate_id,
            "rubric_version": self.rubric_version,
            "aggregate": round(self.aggregate, 4),
            "scores": {name: round(value, 4) for name, value in sorted(self.scores.items())},
            "details": self.details,
            "blocking_failures": list(self.blocking_failures),
            "passed_blocking_gates": self.passed_blocking_gates,
        }


def _ratio(numerator: int, denominator: int, default: float = 1.0) -> float:
    if denominator == 0:
        return default
    return numerator / denominator


def _asserted(field: dict) -> bool:
    return field.get("state") in ASSERTED_STATES and field.get("value") is not None


def score_candidate(
    candidate: dict,
    truth: dict,
    reconciliation_summary: dict | None = None,
    runsheet_entry_count: int = 0,
) -> ScoreCard:
    """Score one candidate against the frozen benchmark.

    ``truth`` maps ``(page_id, row, field)`` to ``(value, truth_state)``.
    """
    entries = candidate.get("entries", [])

    hallucinated: list[str] = []
    unreadable_or_absent_cells = 0
    omitted: list[str] = []
    legible_cells = 0
    asserted_total = 0
    asserted_correct = 0
    region_supported = 0
    calibration_total = 0.0
    per_field_correct: dict[str, list[int]] = {}
    benchmark_total = 0
    benchmark_correct = 0

    for entry in entries:
        page_id = entry.get("page_id")
        row = entry.get("row")
        for name, field in entry.get("fields", {}).items():
            key = (page_id, row, name)
            if key not in truth:
                continue
            true_value, true_state = truth[key]
            asserted = _asserted(field)

            if true_state in ("unreadable", "absent"):
                unreadable_or_absent_cells += 1
                if asserted and field.get("state") == "known":
                    hallucinated.append(f"{page_id}#{row}.{name}={field.get('value')!r}")
            else:
                legible_cells += 1
                if not asserted:
                    omitted.append(f"{page_id}#{row}.{name}")

            if name in BENCHMARK_FIELDS:
                benchmark_total += 1
                correct_cell = (
                    (asserted and str(field.get("value")) == str(true_value))
                    if true_state == "known"
                    else (not asserted or field.get("state") != "known")
                )
                benchmark_correct += int(correct_cell)

            if asserted:
                asserted_total += 1
                correct = true_state == "known" and str(field.get("value")) == str(true_value)
                asserted_correct += int(correct)
                confidence = float(field.get("confidence") or 0.0)
                calibration_total += confidence if correct else (1.0 - confidence)
                region = field.get("source_region") or {}
                if region.get("page_id") == page_id and region.get("row") == row:
                    region_supported += 1
                if name in BENCHMARK_FIELDS:
                    per_field_correct.setdefault(name, []).append(int(correct))

    def field_group_score(*names) -> float:
        values = [flag for name in names for flag in per_field_correct.get(name, [])]
        return _ratio(sum(values), len(values))

    location_values: dict[str, set] = {name: set() for name in LOCATION_FIELDS}
    for entry in entries:
        for name in LOCATION_FIELDS:
            field = entry.get("fields", {}).get(name, {})
            if _asserted(field):
                location_values[name].add(field["value"])
    consistency = _ratio(
        sum(1 for values in location_values.values() if len(values) <= 1), len(LOCATION_FIELDS)
    )

    coverage = 1.0
    if reconciliation_summary and runsheet_entry_count:
        coverage = min(1.0, _ratio(reconciliation_summary.get("coverage", 0), runsheet_entry_count))

    scores = {
        "hallucination_avoidance": 1.0 - _ratio(len(hallucinated), unreadable_or_absent_cells, 0.0),
        "source_region_support": _ratio(region_supported, asserted_total),
        "exact_field_agreement": _ratio(asserted_correct, asserted_total),
        "document_number_agreement": field_group_score("document_number"),
        "book_page_agreement": field_group_score("book", "page"),
        "legal_description_agreement": field_group_score("legal_description"),
        "party_name_agreement": field_group_score("grantor", "grantee"),
        "false_omission_avoidance": 1.0 - _ratio(len(omitted), legible_cells, 0.0),
        "internal_consistency": consistency,
        "confidence_calibration": _ratio(calibration_total, asserted_total),
        "runsheet_reconciliation_coverage": coverage,
        "benchmark_accuracy": _ratio(benchmark_correct, benchmark_total),
    }

    total_weight = sum(dimension.weight for dimension in DIMENSIONS)
    aggregate = sum(
        scores[dimension.name] * dimension.weight for dimension in DIMENSIONS
    ) / total_weight

    blocking_failures = tuple(
        f"{dimension.name}={scores[dimension.name]:.3f} below required {dimension.minimum:.2f}"
        for dimension in DIMENSIONS
        if dimension.blocking and scores[dimension.name] < dimension.minimum
    )

    details = {
        "hallucinated_cells": sorted(hallucinated)[:25],
        "hallucinated_count": len(hallucinated),
        "omitted_cells": sorted(omitted)[:25],
        "omitted_count": len(omitted),
        "asserted_cells": asserted_total,
        "benchmarked_cells": benchmark_total,
        "unreadable_or_absent_cells": unreadable_or_absent_cells,
    }

    return ScoreCard(
        candidate_id=candidate.get("candidate_id", "unknown"),
        scores=scores,
        details=details,
        aggregate=aggregate,
        blocking_failures=blocking_failures,
    )


def compare(baseline: ScoreCard, candidate: ScoreCard) -> dict:
    """Dimension-by-dimension comparison used by the judge and the loop."""
    improvements = {}
    regressions = {}
    for name in baseline.scores:
        delta = candidate.scores[name] - baseline.scores[name]
        if delta > 1e-9:
            improvements[name] = round(delta, 4)
        elif delta < -1e-9:
            regressions[name] = round(delta, 4)
    blocking_regressions = [
        f"{name} regressed by {abs(delta):.3f} on blocking dimension"
        for name, delta in regressions.items()
        if DIMENSIONS_BY_NAME[name].blocking
    ]
    blocking_regressions.extend(candidate.blocking_failures)
    return {
        "baseline_aggregate": round(baseline.aggregate, 4),
        "candidate_aggregate": round(candidate.aggregate, 4),
        "delta": round(candidate.aggregate - baseline.aggregate, 4),
        "improvements": improvements,
        "regressions": regressions,
        "blocking_regressions": sorted(set(blocking_regressions)),
        "rubric_version": RUBRIC_VERSION,
    }


def rubric() -> list[dict]:
    return [
        {
            "name": dimension.name,
            "weight": dimension.weight,
            "blocking": dimension.blocking,
            "minimum": dimension.minimum,
            "description": dimension.description,
        }
        for dimension in DIMENSIONS
    ]
