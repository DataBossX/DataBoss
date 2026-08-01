"""Tournament, scoring, judge, and improvement-loop behaviour."""

from __future__ import annotations

import json

import pytest

from databossx.command_brain.autonomy import AutonomyLevel
from databossx.command_brain.consensus import build_consensus
from databossx.command_brain.errors import BudgetExceeded
from databossx.command_brain.judge import judge_candidate
from databossx.command_brain.readers import read_corpus
from databossx.command_brain.scoring import DIMENSIONS_BY_NAME, ScoreCard, compare, score_candidate
from databossx.command_brain.util import canonical_hash


@pytest.fixture
def tournament(runtime):
    plan = runtime.build_tournament_plan(
        "Read the synthetic index and reconcile it against the Runsheet.", 3, "sec32_synthetic"
    )
    with runtime.policy.elevated(AutonomyLevel.READ_ONLY_EXECUTE):
        return runtime.tournaments.run(plan)


def _by_profile(result, profile_id):
    for record in result.candidates:
        if record.spec.profile_id == profile_id:
            return record
    raise AssertionError(f"no candidate with profile {profile_id}")


def test_baseline_is_frozen_and_hashed_before_candidates_run(runtime, tournament):
    row = runtime.store.fetchone(
        "SELECT baseline_candidate_id, baseline_hash FROM cb_tournaments WHERE tournament_id = ?",
        (tournament.tournament_id,),
    )
    assert row["baseline_candidate_id"] == tournament.baseline.candidate_id
    assert row["baseline_hash"] == canonical_hash(tournament.baseline.output)


def test_baseline_bytes_are_unchanged_by_the_tournament(runtime, tournament):
    stored = runtime.store.fetchone(
        "SELECT output_json FROM cb_tournament_candidates WHERE candidate_id = ?",
        (tournament.baseline.candidate_id,),
    )
    assert canonical_hash(json.loads(stored["output_json"])) == canonical_hash(
        tournament.baseline.output
    )


def test_candidates_execute_independently(runtime, tournament):
    assignments = runtime.store.fetchall(
        "SELECT id, model_id FROM cb_agent_assignments WHERE role_id = 'INDEX_READER'"
    )
    models = [row["model_id"] for row in assignments]
    # One dispatch per candidate plus the baseline; each on its own model lane.
    assert len(assignments) == len(tournament.candidates) + 1
    assert len(set(models)) == len(models)


def test_candidate_with_a_lower_score_is_rejected(tournament):
    transposing = _by_profile(tournament, "transposing")
    assert transposing.scorecard.aggregate < tournament.baseline.scorecard.aggregate
    assert transposing.decision["decision"] == "REJECT"
    assert transposing.status == "REJECTED"


def test_hallucinated_values_are_penalised_and_quarantined(runtime, tournament):
    fabricating = _by_profile(tournament, "fabricating")
    assert fabricating.scorecard.scores["hallucination_avoidance"] < 0.95
    assert fabricating.scorecard.blocking_failures
    assert fabricating.decision["decision"] == "QUARANTINE"
    assert fabricating.status == "QUARANTINED"
    assert runtime.store.is_quarantined(fabricating.candidate_id)


def test_a_quarantined_candidate_is_never_the_accepted_one(tournament):
    fabricating = _by_profile(tournament, "fabricating")
    assert tournament.accepted_candidate_id != fabricating.candidate_id


def test_unreadable_fields_stay_unreadable_rather_than_guessed(runtime):
    entries = read_corpus("careful", runtime.corpus.pages)
    truth = runtime.corpus.truth
    for entry in entries:
        for name, field in entry["fields"].items():
            _, truth_state = truth[(entry["page_id"], entry["row"], name)]
            if truth_state == "unreadable":
                assert field["state"] == "unreadable"
                assert field["value"] is None


def test_absent_and_unreadable_are_distinct_states(runtime):
    entries = read_corpus("careful", runtime.corpus.pages)
    states = {
        field["state"]
        for entry in entries
        for field in entry["fields"].values()
    }
    assert {"unreadable", "absent"} <= states


def test_a_majority_vote_cannot_override_clear_source_evidence(runtime, tournament):
    """Three confident readers do not turn a smudge into a value."""
    consensus = tournament.consensus
    assert consensus["contested_unreadable_count"] > 0
    assert consensus["vote_overruled_by_source"]
    for cell in consensus["cells"]:
        if cell["status"] == "contested_unreadable":
            assert cell["value"] is None
            assert cell["requires_human_review"] is True


def test_contested_cells_are_queued_for_a_human(runtime, tournament):
    queue = runtime.store.open_human_reviews("sec32_synthetic")
    assert queue
    assert any(item["subject_type"] == "index_cell" for item in queue)


def test_judge_decisions_cite_evidence(runtime, tournament):
    rows = runtime.store.fetchall(
        "SELECT decision, rationale, evidence_json FROM cb_judge_decisions WHERE tournament_id = ?",
        (tournament.tournament_id,),
    )
    assert rows
    for row in rows:
        evidence = json.loads(row["evidence_json"])
        assert evidence, "a judge decision with no evidence is not a decision"
        assert any(item.startswith("rubric=") for item in evidence)
        assert row["rationale"]


def test_a_better_aggregate_with_a_blocking_regression_is_still_rejected():
    """Volume does not buy its way past a blocking gate."""
    scores = {name: 1.0 for name in DIMENSIONS_BY_NAME}
    baseline = ScoreCard("cand_base", dict(scores), {}, 0.90, ())

    better_but_broken = dict(scores)
    better_but_broken["source_region_support"] = 0.10  # blocking dimension collapses
    candidate = ScoreCard(
        "cand_new",
        better_but_broken,
        {"hallucinated_cells": []},
        0.99,  # higher aggregate than the baseline
        ("source_region_support=0.100 below required 0.90",),
    )

    comparison = compare(baseline, candidate)
    assert comparison["delta"] > 0
    assert comparison["blocking_regressions"]

    decision = judge_candidate(
        baseline,
        candidate,
        candidate_model_id="simulated.reader.careful",
        judge_model_id="deterministic.judge",
    )
    assert decision.decision == "QUARANTINE"
    assert decision.blocking_regressions


def test_insignificant_improvement_is_treated_as_noise():
    scores = {name: 0.9 for name in DIMENSIONS_BY_NAME}
    baseline = ScoreCard("cand_base", dict(scores), {}, 0.900, ())
    candidate = ScoreCard("cand_new", dict(scores), {}, 0.9005, ())
    decision = judge_candidate(
        baseline,
        candidate,
        candidate_model_id="simulated.reader.careful",
        judge_model_id="deterministic.judge",
    )
    assert decision.decision == "REJECT"
    assert "below the meaningful threshold" in decision.rationale


def test_candidate_cap_is_enforced(runtime):
    plan = runtime.build_tournament_plan("q", 3, "sec32_synthetic")
    over_cap = plan.__class__(
        question=plan.question,
        baseline=plan.baseline,
        candidates=plan.candidates + plan.candidates,
        judge_model_id=plan.judge_model_id,
        max_candidates=2,
    )
    with pytest.raises(BudgetExceeded):
        runtime.tournaments.run(over_cap)


def test_iteration_cap_is_enforced(runtime):
    plan = runtime.build_tournament_plan("q", 3, "sec32_synthetic")
    with runtime.policy.elevated(AutonomyLevel.READ_ONLY_EXECUTE):
        summary = runtime.improvement.run(plan, max_iterations=1)
    assert summary["iterations_run"] <= 1
    assert summary["max_iterations"] == 1

    with pytest.raises(BudgetExceeded):
        runtime.improvement.run(plan, max_iterations=0)


def test_improvement_loop_stops_when_improvement_is_insignificant(runtime):
    plan = runtime.build_tournament_plan("q", 3, "sec32_synthetic")
    with runtime.policy.elevated(AutonomyLevel.READ_ONLY_EXECUTE):
        summary = runtime.improvement.run(plan, max_iterations=5)
    assert summary["stop_reason"] in ("improvement below threshold", "no accepted candidate")
    assert summary["iterations_run"] < 5
    assert summary["receipt_id"]


def test_improvement_loop_never_lowers_the_accepted_baseline(runtime):
    plan = runtime.build_tournament_plan("q", 3, "sec32_synthetic")
    with runtime.policy.elevated(AutonomyLevel.READ_ONLY_EXECUTE):
        summary = runtime.improvement.run(plan, max_iterations=3)
    aggregates = [
        outcome["baseline_aggregate"] for outcome in summary["outcomes"]
    ]
    assert aggregates == sorted(aggregates)


def test_every_tournament_writes_a_receipt(runtime, tournament):
    receipt = runtime.store.get_receipt(tournament.receipt_id)
    payload = receipt["payload"]
    assert payload["baseline_hash"]
    assert payload["rubric"]
    assert payload["plan"]["judge_model_id"] == "deterministic.judge"
    for candidate in payload["candidates"]:
        assert candidate["output_hash"]
        assert candidate["scorecard"]["scores"]
        assert candidate["decision"]["decision"]


def test_scoring_is_reproducible(runtime):
    truth = runtime.corpus.truth
    first = score_candidate(
        {"candidate_id": "c1", "entries": read_corpus("careful", runtime.corpus.pages)}, truth
    )
    second = score_candidate(
        {"candidate_id": "c1", "entries": read_corpus("careful", runtime.corpus.pages)}, truth
    )
    assert first.to_dict() == second.to_dict()


def test_reconciliation_reports_the_planted_conflicts(runtime):
    from databossx.command_brain.reconcile import reconcile, summarize

    entries = read_corpus("careful", runtime.corpus.pages)
    summary = summarize(reconcile(entries, runtime.corpus.runsheet))
    counts = summary["counts"]
    assert counts.get("conflicting_legal_description", 0) >= 1
    assert counts.get("runsheet_only", 0) >= 1
    assert counts.get("unreadable_source_field", 0) >= 1
    assert summary["human_review_rows"] > 0


def test_consensus_marks_agreement_without_asserting_unsupported_values(runtime):
    candidates = [
        {"candidate_id": f"cand_{profile}", "entries": read_corpus(profile, runtime.corpus.pages)}
        for profile in ("careful", "conservative", "fabricating")
    ]
    consensus = build_consensus(candidates, runtime.corpus.truth)
    assert consensus["agreed_count"] > 0
    for cell in consensus["cells"]:
        if cell["status"] == "contested_unreadable":
            assert cell["value"] is None


def test_stop_request_halts_remaining_candidates(runtime):
    plan = runtime.build_tournament_plan("q", 3, "sec32_synthetic")
    with runtime.policy.elevated(AutonomyLevel.READ_ONLY_EXECUTE):
        result = runtime.tournaments.run(plan, stop_check=lambda: True)
    assert result.candidates == []
    assert "stop requested" in (result.stopped_reason or "").lower()
    assert result.baseline_preserved is True
