"""Controlled multi-agent tournament and bounded improvement loop.

The tournament exists to improve *uncertain analysis* without ever replacing
accepted work by accident. The accepted baseline is frozen and hashed before any
candidate runs, candidates run independently, scoring is deterministic, and an
independent judge — not the producing agent — decides. A candidate that fails a
blocking gate is quarantined; a candidate that merely fails to improve is
rejected. In both cases the baseline survives untouched, and the receipt records
which happened and why.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .consensus import build_consensus, describe_disagreements
from .errors import BudgetExceeded, CommandBrainError
from .judge import judge_candidate
from .reconcile import reconcile, summarize
from .schemas import CANDIDATE_OUTPUT_SCHEMA, validate
from .scoring import DIMENSIONS_BY_NAME, ScoreCard, compare, rubric, score_candidate
from .util import canonical_hash, canonical_json


@dataclass(frozen=True)
class CandidateSpec:
    label: str
    role_id: str
    model_id: str
    profile_id: str

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "role_id": self.role_id,
            "model_id": self.model_id,
            "profile_id": self.profile_id,
        }


@dataclass(frozen=True)
class TournamentPlan:
    question: str
    baseline: CandidateSpec
    candidates: tuple
    judge_model_id: str
    judge_role_id: str = "JUDGE"
    project_id: str | None = None
    page_ids: tuple = ()
    runsheet_id: str | None = None
    max_candidates: int = 5
    scoring_criteria: tuple = field(default_factory=lambda: tuple(rubric()))

    def to_dict(self) -> dict:
        return {
            "question": self.question,
            "baseline": self.baseline.to_dict(),
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "judge_model_id": self.judge_model_id,
            "judge_role_id": self.judge_role_id,
            "project_id": self.project_id,
            "page_ids": list(self.page_ids),
            "runsheet_id": self.runsheet_id,
            "max_candidates": self.max_candidates,
            "scoring_criteria": [dict(criterion) for criterion in self.scoring_criteria],
        }


@dataclass
class CandidateRecord:
    candidate_id: str
    spec: CandidateSpec
    output: dict
    scorecard: ScoreCard
    reconciliation: dict
    summary: dict
    simulated: bool
    assignment_id: str | None
    status: str = "SCORED"
    decision: dict | None = None
    iteration: int = 0

    def to_dict(self) -> dict:
        return {
            "candidate_id": self.candidate_id,
            "spec": self.spec.to_dict(),
            "status": self.status,
            "simulated": self.simulated,
            "assignment_id": self.assignment_id,
            "iteration": self.iteration,
            "scorecard": self.scorecard.to_dict(),
            "reconciliation_summary": self.summary,
            "decision": self.decision,
            "output_hash": canonical_hash(self.output),
        }


@dataclass
class TournamentResult:
    tournament_id: str
    plan: TournamentPlan
    baseline: CandidateRecord
    candidates: list
    accepted_candidate_id: str | None
    consensus: dict
    receipt_id: str | None = None
    stopped_reason: str | None = None

    @property
    def baseline_preserved(self) -> bool:
        return self.accepted_candidate_id in (None, self.baseline.candidate_id)

    def to_dict(self) -> dict:
        return {
            "tournament_id": self.tournament_id,
            "question": self.plan.question,
            "baseline": self.baseline.to_dict(),
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "accepted_candidate_id": self.accepted_candidate_id,
            "baseline_preserved": self.baseline_preserved,
            "consensus": {
                "agreed_count": self.consensus["agreed_count"],
                "disagreed_count": self.consensus["disagreed_count"],
                "contested_unreadable_count": self.consensus["contested_unreadable_count"],
                "vote_overruled_by_source": self.consensus["vote_overruled_by_source"],
                "disagreement_lines": describe_disagreements(self.consensus),
            },
            "receipt_id": self.receipt_id,
            "stopped_reason": self.stopped_reason,
        }


class TournamentEngine:
    """Runs a tournament using an injected candidate ``producer``.

    ``producer(spec, iteration) -> (output: dict, meta: dict)`` is supplied by the
    runtime and is normally backed by :class:`~.dispatcher.AgentDispatcher`, so
    every candidate still goes through policy, model verification, and schema
    validation before it reaches the scorer.
    """

    def __init__(self, store, producer, truth_provider, runsheet_provider):
        self.store = store
        self.producer = producer
        self.truth_provider = truth_provider
        self.runsheet_provider = runsheet_provider

    # -- helpers ----------------------------------------------------------
    def _evaluate(self, output: dict, runsheet: dict, truth: dict) -> tuple:
        validate(output, CANDIDATE_OUTPUT_SCHEMA, "$candidate")
        reconciliation = reconcile(output.get("entries", []), runsheet)
        summary = summarize(reconciliation)
        scorecard = score_candidate(
            output, truth, summary, len(runsheet.get("entries", []))
        )
        return reconciliation, summary, scorecard

    def _persist_candidate(self, tournament_id: str, record: CandidateRecord, is_baseline: bool) -> None:
        self.store.execute(
            """
            INSERT INTO cb_tournament_candidates (
                candidate_id, tournament_id, role_id, model_id, iteration, is_baseline,
                simulated, output_hash, output_json, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.candidate_id,
                tournament_id,
                record.spec.role_id,
                record.spec.model_id,
                record.iteration,
                int(is_baseline),
                int(record.simulated),
                canonical_hash(record.output),
                canonical_json(record.output),
                record.status,
                self.store.now(),
            ),
        )
        for name, value in record.scorecard.scores.items():
            dimension = DIMENSIONS_BY_NAME[name]
            self.store.execute(
                """
                INSERT INTO cb_candidate_scores (id, candidate_id, dimension, value, weight, blocking, detail_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.store.new_id("score"),
                    record.candidate_id,
                    name,
                    float(value),
                    dimension.weight,
                    int(dimension.blocking),
                    canonical_json({"minimum": dimension.minimum}),
                ),
            )

    def _set_status(self, candidate_id: str, status: str) -> None:
        self.store.execute(
            "UPDATE cb_tournament_candidates SET status = ? WHERE candidate_id = ?",
            (status, candidate_id),
        )

    # -- run --------------------------------------------------------------
    def run(
        self,
        plan: TournamentPlan,
        *,
        iteration: int = 0,
        tournament_id: str | None = None,
        stop_check=None,
    ) -> TournamentResult:
        if len(plan.candidates) > plan.max_candidates:
            raise BudgetExceeded(
                f"{len(plan.candidates)} candidates requested; the cap is {plan.max_candidates}.",
                detail={"requested": len(plan.candidates), "cap": plan.max_candidates},
            )

        truth = self.truth_provider(plan)
        runsheet = self.runsheet_provider(plan)

        # 1-2. Freeze and hash the baseline before anything else runs.
        baseline_output, baseline_meta = self.producer(plan.baseline, iteration)
        baseline_reconciliation, baseline_summary, baseline_scorecard = self._evaluate(
            baseline_output, runsheet, truth
        )
        baseline_hash = canonical_hash(baseline_output)
        baseline_record = CandidateRecord(
            candidate_id=baseline_output["candidate_id"],
            spec=plan.baseline,
            output=baseline_output,
            scorecard=baseline_scorecard,
            reconciliation=baseline_reconciliation,
            summary=baseline_summary,
            simulated=bool(baseline_meta.get("simulated")),
            assignment_id=baseline_meta.get("assignment_id"),
            status="ACCEPTED",
            iteration=iteration,
        )

        tournament_id = tournament_id or self.store.new_id("trn")
        self.store.execute(
            """
            INSERT INTO cb_tournaments (
                tournament_id, project_id, question, baseline_candidate_id, baseline_hash,
                status, created_at
            ) VALUES (?, ?, ?, ?, ?, 'RUNNING', ?)
            """,
            (
                tournament_id,
                plan.project_id,
                plan.question,
                baseline_record.candidate_id,
                baseline_hash,
                self.store.now(),
            ),
        )
        self._persist_candidate(tournament_id, baseline_record, is_baseline=True)
        self.store.audit(
            "tournament.baseline_frozen",
            "tournament",
            tournament_id,
            {
                "baseline_candidate_id": baseline_record.candidate_id,
                "baseline_hash": baseline_hash,
                "baseline_aggregate": round(baseline_scorecard.aggregate, 4),
            },
            project_id=plan.project_id,
        )

        # 6-11. Candidates run independently, are normalized, scored, judged.
        records: list[CandidateRecord] = []
        stopped_reason = None
        for spec in plan.candidates:
            if stop_check is not None and stop_check():
                stopped_reason = "Operator stop requested; remaining candidates were not run."
                break
            try:
                output, meta = self.producer(spec, iteration)
                reconciliation, summary, scorecard = self._evaluate(output, runsheet, truth)
            except CommandBrainError as exc:
                self.store.audit(
                    "tournament.candidate_failed",
                    "tournament",
                    tournament_id,
                    {"spec": spec.to_dict(), "error": exc.code, "message": exc.message},
                    project_id=plan.project_id,
                )
                continue

            record = CandidateRecord(
                candidate_id=output["candidate_id"],
                spec=spec,
                output=output,
                scorecard=scorecard,
                reconciliation=reconciliation,
                summary=summary,
                simulated=bool(meta.get("simulated")),
                assignment_id=meta.get("assignment_id"),
                iteration=iteration,
            )
            self._persist_candidate(tournament_id, record, is_baseline=False)

            decision = judge_candidate(
                baseline_scorecard,
                scorecard,
                candidate_model_id=spec.model_id,
                judge_model_id=plan.judge_model_id,
                validators=tuple(other.model_id for other in plan.candidates if other is not spec),
                reconciliation_summary=summary,
            )
            record.decision = decision.full_record()
            record.status = {
                "ACCEPT": "SCORED",
                "REJECT": "REJECTED",
                "QUARANTINE": "QUARANTINED",
                "HUMAN_REVIEW": "SCORED",
            }[decision.decision]
            self._set_status(record.candidate_id, record.status)

            self.store.execute(
                """
                INSERT INTO cb_judge_decisions (
                    id, tournament_id, candidate_id, judge_role_id, judge_model_id,
                    decision, rationale, evidence_json, independent, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
                """,
                (
                    self.store.new_id("judge"),
                    tournament_id,
                    record.candidate_id,
                    plan.judge_role_id,
                    plan.judge_model_id,
                    decision.decision,
                    decision.rationale,
                    canonical_json(list(decision.evidence_refs)),
                    self.store.now(),
                ),
            )

            if decision.decision == "QUARANTINE":
                self.store.quarantine(
                    "tournament_candidate", record.candidate_id, decision.rationale
                )
            if decision.decision == "HUMAN_REVIEW":
                self.store.queue_human_review(
                    "tournament_candidate",
                    record.candidate_id,
                    "Candidate improves on the baseline but most rows still need a human decision. Accept?",
                    {"decision": record.decision},
                    project_id=plan.project_id,
                )
            records.append(record)

        # 12-14. Accept only a candidate the judge accepted and that actually wins.
        accepted_id = None
        accepted_record = None
        for record in records:
            if record.decision and record.decision["decision"] == "ACCEPT":
                if accepted_record is None or record.scorecard.aggregate > accepted_record.scorecard.aggregate:
                    accepted_record = record
        if accepted_record is not None:
            accepted_id = accepted_record.candidate_id
            accepted_record.status = "ACCEPTED"
            self._set_status(accepted_id, "ACCEPTED")
            self._set_status(baseline_record.candidate_id, "SCORED")

        consensus = build_consensus(
            [baseline_record.output] + [record.output for record in records], truth
        )
        for line in consensus["vote_overruled_by_source"]:
            self.store.audit(
                "tournament.vote_overruled_by_source", "tournament", tournament_id, {"detail": line}
            )
        for cell in consensus["human_review_cells"]:
            if cell["status"] == "contested_unreadable":
                self.store.queue_human_review(
                    "index_cell",
                    f"{cell['page_id']}_r{cell['row']}_{cell['field']}",
                    "Readers disagree about whether this cell is legible. Human reading required.",
                    cell,
                    project_id=plan.project_id,
                )

        self.store.execute(
            """
            UPDATE cb_tournaments SET status = 'COMPLETE', accepted_candidate_id = ?, completed_at = ?
             WHERE tournament_id = ?
            """,
            (accepted_id, self.store.now(), tournament_id),
        )

        result = TournamentResult(
            tournament_id=tournament_id,
            plan=plan,
            baseline=baseline_record,
            candidates=records,
            accepted_candidate_id=accepted_id,
            consensus=consensus,
            stopped_reason=stopped_reason,
        )

        receipt = self.store.write_receipt(
            "tournament",
            tournament_id,
            {
                "question": plan.question,
                "plan": plan.to_dict(),
                "baseline_hash": baseline_hash,
                "baseline_scores": baseline_scorecard.to_dict(),
                "candidates": [record.to_dict() for record in records],
                "accepted_candidate_id": accepted_id,
                "baseline_preserved": result.baseline_preserved,
                "consensus": result.to_dict()["consensus"],
                "rubric": rubric(),
                "stopped_reason": stopped_reason,
            },
            project_id=plan.project_id,
        )
        result.receipt_id = receipt["receipt_id"]
        return result


@dataclass
class IterationOutcome:
    iteration: int
    baseline_aggregate: float
    best_candidate_aggregate: float | None
    accepted: bool
    reason: str
    comparison: dict | None = None

    def to_dict(self) -> dict:
        return {
            "iteration": self.iteration,
            "baseline_aggregate": round(self.baseline_aggregate, 4),
            "best_candidate_aggregate": (
                round(self.best_candidate_aggregate, 4)
                if self.best_candidate_aggregate is not None
                else None
            ),
            "accepted": self.accepted,
            "reason": self.reason,
            "comparison": self.comparison,
        }


class ImprovementLoop:
    """Bounded loop that never mutates the accepted baseline while experimenting."""

    def __init__(self, engine: TournamentEngine, store):
        self.engine = engine
        self.store = store

    def run(
        self,
        plan: TournamentPlan,
        *,
        max_iterations: int = 3,
        minimum_delta: float = 0.01,
        stop_check=None,
    ) -> dict:
        if max_iterations < 1:
            raise BudgetExceeded(
                "Improvement loop requires at least one iteration.",
                detail={"max_iterations": max_iterations},
            )
        outcomes: list[IterationOutcome] = []
        accepted_baseline: ScoreCard | None = None
        accepted_output_hash: str | None = None
        results = []
        stop_reason = "iteration cap reached"

        for iteration in range(max_iterations):
            if stop_check is not None and stop_check():
                stop_reason = "operator stop"
                break
            result = self.engine.run(plan, iteration=iteration)
            results.append(result)
            baseline_score = result.baseline.scorecard
            if accepted_baseline is None:
                accepted_baseline = baseline_score
                accepted_output_hash = canonical_hash(result.baseline.output)

            best = None
            for record in result.candidates:
                if record.decision and record.decision["decision"] == "ACCEPT":
                    if best is None or record.scorecard.aggregate > best.scorecard.aggregate:
                        best = record

            if best is None:
                outcomes.append(
                    IterationOutcome(
                        iteration,
                        accepted_baseline.aggregate,
                        None,
                        False,
                        "No candidate was accepted by the independent judge; baseline preserved.",
                    )
                )
                stop_reason = "no accepted candidate"
                break

            comparison = compare(accepted_baseline, best.scorecard)
            if comparison["delta"] < minimum_delta:
                outcomes.append(
                    IterationOutcome(
                        iteration,
                        accepted_baseline.aggregate,
                        best.scorecard.aggregate,
                        False,
                        f"Improvement {comparison['delta']} below threshold {minimum_delta}; stopping.",
                        comparison,
                    )
                )
                stop_reason = "improvement below threshold"
                break

            accepted_baseline = best.scorecard
            accepted_output_hash = canonical_hash(best.output)
            outcomes.append(
                IterationOutcome(
                    iteration,
                    accepted_baseline.aggregate,
                    best.scorecard.aggregate,
                    True,
                    "Candidate accepted; it becomes the baseline for the next iteration.",
                    comparison,
                )
            )

        summary = {
            "iterations_run": len(outcomes),
            "max_iterations": max_iterations,
            "stop_reason": stop_reason,
            "outcomes": [outcome.to_dict() for outcome in outcomes],
            "final_baseline_aggregate": (
                round(accepted_baseline.aggregate, 4) if accepted_baseline else None
            ),
            "final_baseline_hash": accepted_output_hash,
            "tournament_ids": [result.tournament_id for result in results],
        }
        receipt = self.store.write_receipt(
            "improvement_loop", results[0].tournament_id if results else "none", summary,
            project_id=plan.project_id,
        )
        summary["receipt_id"] = receipt["receipt_id"]
        return summary
