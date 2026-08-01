"""Runtime assembly.

Wires the store, policy engine, model gateway, tool registry, dispatcher, lease
manager, approval service, memory, and tournament engine into one object, and
provides the concrete handler bodies the tools call.

Model registration here is honest about what this environment can actually do:
deterministic in-process workers are VERIFIED, the labelled simulators are
LIMITED, and every endpoint that would need a network transport or an external
agent stays NOT_VERIFIED until something proves otherwise.
"""

from __future__ import annotations

from dataclasses import dataclass

from .approvals import ApprovalService
from .autonomy import AutonomyLevel
from .dispatcher import AgentDispatcher, build_code_handoff
from .envelope import EnvelopeDrafter
from .errors import ToolInputRejected
from .leases import LeaseManager
from .memory import MemoryService
from .model_gateway import (
    DeterministicAdapter,
    HandoffAdapter,
    HttpModelAdapter,
    Modality,
    ModelDescriptor,
    ModelGateway,
    SimulatedAdapter,
)
from .policy import DataSensitivity, PolicyEngine, PolicyProfile
from .readers import PROFILES, read_corpus
from .reconcile import reconcile, summarize
from .scoring import rubric
from .state import StateRetriever
from .store import CommandBrainStore
from .synthetic import SYNTHETIC_BANNER, build_corpus
from .toolset import build_registry
from .tools import ToolContext
from .tournament import CandidateSpec, ImprovementLoop, TournamentEngine, TournamentPlan
from .util import Clock, IdFactory, canonical_hash

READER_MODEL_PREFIX = "simulated.reader."

#: Which reader profile backs each simulated candidate model.
READER_MODELS = {
    f"{READER_MODEL_PREFIX}{profile_id}": profile_id for profile_id in PROFILES
}

DEFAULT_BASELINE_PROFILE = "conservative"
DEFAULT_CANDIDATE_ORDER = ("careful", "transposing", "fabricating", "conservative")


@dataclass(frozen=True)
class RuntimeIdentity:
    requesting_user: str = "operator"
    project_id: str | None = None


class CommandBrainRuntime:
    """Everything the Command Brain needs, assembled once."""

    def __init__(
        self,
        db_path,
        *,
        profile: PolicyProfile | None = None,
        clock: Clock | None = None,
        id_seed: str | None = None,
        requesting_user: str = "operator",
        project_id: str | None = None,
        corpus=None,
    ):
        self.clock = clock or Clock()
        self.store = CommandBrainStore(db_path, clock=self.clock, ids=IdFactory(id_seed))
        self.store.initialize()
        self.policy = PolicyEngine(profile or PolicyProfile())
        self.identity = RuntimeIdentity(requesting_user, project_id)
        self.corpus = corpus or build_corpus()

        self.state = StateRetriever(self.store, self.clock)
        self.gateway = ModelGateway(clock=self.clock, store=self.store)
        self.leases = LeaseManager(self.store, self.clock)
        self.approvals = ApprovalService(self.store, self.clock)
        self.drafter = EnvelopeDrafter(self.store, self.clock)
        self.memory = MemoryService(self.store, self.clock)

        self._register_models()
        self.gateway.probe_all()

        self.dispatcher = AgentDispatcher(
            self.store, self.gateway, self.policy, self.leases, self.approvals
        )
        self.tools = build_registry(self, store=self.store, policy=self.policy)
        self.tournaments = TournamentEngine(
            self.store,
            producer=self._produce_candidate,
            truth_provider=lambda plan: self.corpus.truth,
            runsheet_provider=lambda plan: self.corpus.runsheet,
        )
        self.improvement = ImprovementLoop(self.tournaments, self.store)

        self._test_suites = {
            "command_brain_selftest": self._selftest,
            "command_brain_policy_gates": self._policy_gate_test,
        }
        for suite_id in self._test_suites:
            self.store.execute(
                "INSERT OR REPLACE INTO cb_test_suites (suite_id, description, registered_at) VALUES (?, ?, ?)",
                (suite_id, f"Registered deterministic suite {suite_id}", self.store.now()),
            )

        self._register_synthetic_artifacts()

        from .roles import sync_roles

        sync_roles(self.store)

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------
    def _register_models(self) -> None:
        def descriptor(model_id, provider, name, **kwargs) -> ModelDescriptor:
            defaults = dict(
                modalities={Modality.TEXT},
                context_limit=32_000,
                tool_use=False,
                structured_output=True,
                is_local=True,
                cost_category="FREE",
                latency_category="FAST",
                data_sensitivity_policy=DataSensitivity.SYNTHETIC,
                permitted_project_classes=("synthetic", "internal"),
                simulated=False,
            )
            defaults.update(kwargs)
            return ModelDescriptor(model_id=model_id, provider=provider, display_name=name, **defaults)

        # Deterministic in-process workers. These are genuinely verified: they
        # have no network dependency and their behaviour is reproducible.
        self.gateway.register(
            DeterministicAdapter(
                descriptor(
                    "deterministic.reconciler",
                    "databossx",
                    "Deterministic index/Runsheet reconciler",
                    modalities={Modality.DETERMINISTIC, Modality.TEXT},
                ),
                self._deterministic_reconcile,
            )
        )
        self.gateway.register(
            DeterministicAdapter(
                descriptor(
                    "deterministic.judge",
                    "databossx",
                    "Deterministic scoring judge",
                    modalities={Modality.DETERMINISTIC, Modality.TEXT},
                ),
                lambda request: request.payload.get("decision", {}),
            )
        )
        self.gateway.register(
            DeterministicAdapter(
                descriptor(
                    "deterministic.commander",
                    "databossx",
                    "Deterministic state summariser",
                    modalities={Modality.DETERMINISTIC, Modality.TEXT},
                ),
                self._deterministic_commander,
            )
        )
        self.gateway.register(
            DeterministicAdapter(
                descriptor(
                    "deterministic.validator",
                    "databossx",
                    "Deterministic workbook and formula validator",
                    modalities={Modality.DETERMINISTIC, Modality.TEXT},
                ),
                self._deterministic_validator,
            )
        )
        self.gateway.register(
            DeterministicAdapter(
                descriptor(
                    "human.review_queue",
                    "databossx",
                    "Human review lane",
                    modalities={Modality.DETERMINISTIC, Modality.TEXT},
                ),
                self._human_review_lane,
            )
        )

        # Labelled simulators, one per reader failure mode.
        for model_id, profile_id in READER_MODELS.items():
            self.gateway.register(
                SimulatedAdapter(
                    descriptor(
                        model_id,
                        "databossx.simulated",
                        f"SIMULATED index reader ({profile_id})",
                        modalities={Modality.TEXT, Modality.VISION},
                        simulated=True,
                        permitted_project_classes=("synthetic",),
                    ),
                    self._make_reader(profile_id),
                )
            )

        # Endpoints that need a transport or an external agent. They stay
        # NOT_VERIFIED and are therefore ineligible for routing until proven.
        self.gateway.register(
            HttpModelAdapter(
                descriptor(
                    "local.openai_compatible",
                    "local",
                    "Local OpenAI-compatible endpoint (Ollama / llama.cpp / vLLM)",
                    tool_use=True,
                    cost_category="LOCAL",
                    latency_category="VARIABLE",
                ),
                base_url="http://127.0.0.1:11434",
            )
        )
        self.gateway.register(
            HandoffAdapter(
                descriptor(
                    "handoff.claude_code",
                    "anthropic",
                    "Claude Code task handoff lane",
                    is_local=False,
                    cost_category="MEDIUM",
                    latency_category="SLOW",
                    permitted_project_classes=("synthetic", "internal", "repository"),
                ),
                lambda request: build_code_handoff(**request.payload),
            )
        )
        self.gateway.register(
            HandoffAdapter(
                descriptor(
                    "handoff.codex",
                    "openai",
                    "Codex task handoff lane",
                    is_local=False,
                    cost_category="MEDIUM",
                    latency_category="SLOW",
                    permitted_project_classes=("synthetic", "internal", "repository"),
                ),
                lambda request: build_code_handoff(**request.payload),
            )
        )

    def _register_synthetic_artifacts(self) -> None:
        project_id = self.identity.project_id
        for page in self.corpus.pages:
            self.state.register_artifact(
                page.page_id,
                "index_page",
                f"{page.label} — {SYNTHETIC_BANNER}",
                self.corpus.page_hash(page.page_id),
                project_id=project_id,
                synthetic=True,
            )
        self.state.register_artifact(
            self.corpus.runsheet["runsheet_id"],
            "runsheet",
            f"Runsheet — {SYNTHETIC_BANNER}",
            self.corpus.runsheet_hash(),
            project_id=project_id,
            synthetic=True,
        )

    # ------------------------------------------------------------------
    # Model bodies
    # ------------------------------------------------------------------
    def _make_reader(self, profile_id: str):
        def _read(request):
            page_ids = request.payload.get("page_ids") or [p.page_id for p in self.corpus.pages]
            pages = [self.corpus.page(page_id) for page_id in page_ids]
            entries = read_corpus(profile_id, pages)
            candidate_id = request.payload.get("candidate_id") or (
                "cand_" + canonical_hash({"profile": profile_id, "pages": page_ids})[:16]
            )
            return {
                "candidate_id": candidate_id,
                "agent_role": request.payload.get("role_id", "INDEX_READER"),
                "model_id": f"{READER_MODEL_PREFIX}{profile_id}",
                "simulated": True,
                "reasoning_summary": (
                    f"SIMULATED reader profile {profile_id!r}: {PROFILES[profile_id].description}"
                ),
                "entries": entries,
            }

        return _read

    def _deterministic_reconcile(self, request) -> dict:
        entries = request.payload.get("entries", [])
        return reconcile(entries, self.corpus.runsheet)

    def _deterministic_commander(self, request) -> dict:
        facts = request.payload.get("facts", [])
        return {"summary": request.payload.get("summary", ""), "facts": facts}

    def _deterministic_validator(self, request) -> dict:
        return request.payload.get("result", {"verdict": "NOT_VERIFIED", "findings": []})

    def _human_review_lane(self, request) -> dict:
        return {
            "queued": True,
            "question": request.payload.get("question", "Operator decision required."),
            "context_refs": request.payload.get("context_refs", []),
        }

    # ------------------------------------------------------------------
    # Tool handler bodies
    # ------------------------------------------------------------------
    def read_receipt(self, receipt_id: str) -> dict:
        receipt = self.store.get_receipt(receipt_id)
        if receipt is None:
            raise ToolInputRejected(
                f"{receipt_id!r} is not a known receipt.", detail={"receipt_id": receipt_id}
            )
        return {
            "receipt_id": receipt["receipt_id"],
            "subject_type": receipt["subject_type"],
            "subject_id": receipt["subject_id"],
            "payload_hash": receipt["payload_hash"],
            "created_at": receipt["created_at"],
            "payload": receipt["payload"],
        }

    def inspect_index_page(self, artifact_id: str) -> dict:
        """Structure and legibility only — never transcribed values."""
        metadata = self.state.artifact_metadata(artifact_id)
        if metadata["artifact_class"] != "index_page":
            raise ToolInputRejected(
                f"{artifact_id!r} is not a registered index page.", detail={"artifact_id": artifact_id}
            )
        page = self.corpus.page(artifact_id)
        rows = [
            {
                "row": row.row,
                "region": dict(row.region),
                "cells": {
                    name: {"legibility": synthetic_field.legibility}
                    for name, synthetic_field in row.fields.items()
                },
            }
            for row in page.rows
        ]
        return {
            "artifact_id": artifact_id,
            "label": metadata["label"],
            "sha256": metadata["sha256"],
            "synthetic": True,
            "rows": rows,
            "note": "Structure only. Transcription is an agent output, not a tool output.",
        }

    def inspect_workbook(self, artifact_id: str) -> dict:
        metadata = self.state.artifact_metadata(artifact_id)
        try:  # pragma: no cover - exercised only where openpyxl is installed
            import openpyxl  # noqa: F401
        except ImportError:
            return {
                "artifact_id": artifact_id,
                "state": "NOT_VERIFIED",
                "detail": (
                    "No workbook backend (openpyxl) is available in this runtime, so no structural "
                    "claim is made about the workbook."
                ),
                "metadata": metadata,
            }
        return {
            "artifact_id": artifact_id,
            "state": "VERIFIED",
            "detail": "Workbook backend available; structural inspection performed read-only.",
            "metadata": metadata,
        }

    def run_test_suite(self, suite_id: str) -> dict:
        suite = self._test_suites.get(suite_id)
        if suite is None:
            raise ToolInputRejected(
                f"{suite_id!r} is not a registered test suite. Arbitrary commands are not accepted.",
                detail={"suite_id": suite_id, "registered": sorted(self._test_suites)},
            )
        checks = suite()
        failed = [check for check in checks if not check["passed"]]
        return {
            "suite_id": suite_id,
            "state": "FAIL" if failed else "PASS",
            "checks": checks,
            "failed": len(failed),
        }

    def _selftest(self) -> list[dict]:
        ledger = self.store.verify_ledger()
        return [
            {"name": "audit_ledger_intact", "passed": ledger["valid"], "detail": str(ledger)},
            {"name": "tool_registry_frozen", "passed": self.tools.frozen, "detail": "registry frozen"},
            {
                "name": "level_4_disabled",
                "passed": self.policy.profile.autonomy_ceiling <= AutonomyLevel.BOUNDED_WRITER,
                "detail": f"ceiling={self.policy.profile.autonomy_ceiling.name}",
            },
        ]

    def _policy_gate_test(self) -> list[dict]:
        from .policy import ActionRequest, RiskLevel

        external = self.policy.evaluate(
            ActionRequest(
                action_type="selftest:external",
                required_level=AutonomyLevel.BOUNDED_WRITER,
                risk=RiskLevel.CRITICAL,
                external_effect=True,
            )
        )
        spoken = self.policy.evaluate(
            ActionRequest(
                action_type="selftest:spoken_writer",
                required_level=AutonomyLevel.BOUNDED_WRITER,
                risk=RiskLevel.HIGH,
                mutates_state=True,
            )
        )
        return [
            {"name": "external_effect_denied", "passed": not external.allowed, "detail": "; ".join(external.reasons)},
            {"name": "speech_is_not_authority", "passed": not spoken.allowed, "detail": "; ".join(spoken.reasons)},
        ]

    def draft_envelope_tool(self, ctx, params: dict) -> dict:
        envelope = self.drafter.draft(
            requesting_user=self.identity.requesting_user,
            transcript=getattr(ctx, "metadata", {}).get("transcript", ""),
            normalized_intent=getattr(ctx, "metadata", {}).get("intent", "tool_request"),
            goal=params["goal"],
            project_id=params.get("project_id") or self.identity.project_id,
            autonomy_level=AutonomyLevel.parse(params.get("autonomy_level", 1)),
            plan_id=getattr(ctx, "plan_id", None),
            assigned_roles=tuple(params.get("roles", ())),
            tools=tuple(params.get("tools", ())),
            model_restrictions={
                "local_only": self.policy.profile.local_only,
                "cloud_allowed": self.policy.profile.cloud_models_allowed,
            },
            data_sensitivity=self.policy.profile.data_sensitivity,
            validation_gates=("schema", "policy", "receipt"),
            acceptance_criteria=("All declared gates pass.", "A receipt is written."),
            rollback_plan="Nothing is mutated by a draft; discarding the draft is the rollback.",
            stop_conditions=("Operator stop.", "Budget exhausted.", "Uncertainty requires a human."),
        )
        payload = envelope.phone_safe()
        payload["envelope_hash"] = envelope.envelope_hash
        payload["plain_language"] = envelope.plain_language()
        return payload

    def assign_read_only_agent(self, ctx, params: dict) -> dict:
        result = self.dispatcher.dispatch(
            params["role_id"],
            params["model_id"],
            {
                "page_ids": [params["artifact_id"]],
                "role_id": params["role_id"],
                "candidate_id": "cand_" + canonical_hash(params)[:16],
            },
            capability="read_only_inspection",
            approval_id=getattr(ctx, "metadata", {}).get("approval_id"),
        )
        return {
            "role_id": result.role_id,
            "model_id": result.model_id,
            "assignment_id": result.assignment_id,
            "simulated": result.simulated,
            "verification_state": result.verification_state,
            "output_hash": result.output_hash,
            "receipt_id": result.receipt_id,
        }

    # -- tournaments ------------------------------------------------------
    def _produce_candidate(self, spec: CandidateSpec, iteration: int):
        candidate_id = "cand_" + canonical_hash(
            {"label": spec.label, "profile": spec.profile_id, "iteration": iteration}
        )[:16]
        result = self.dispatcher.dispatch(
            spec.role_id,
            spec.model_id,
            {
                "page_ids": [page.page_id for page in self.corpus.pages],
                "role_id": spec.role_id,
                "candidate_id": candidate_id,
            },
            capability="index_reading",
            modality=Modality.VISION,
        )
        return result.output, {
            "simulated": result.simulated,
            "assignment_id": result.assignment_id,
            "verification_state": result.verification_state,
        }

    def build_tournament_plan(
        self,
        question: str,
        candidate_count: int = 3,
        project_id: str | None = None,
        page_ids=None,
    ) -> TournamentPlan:
        available = [
            profile_id
            for profile_id in DEFAULT_CANDIDATE_ORDER
            if profile_id != DEFAULT_BASELINE_PROFILE
        ]
        chosen = available[: max(1, min(candidate_count, self.policy.profile.max_candidates))]
        return TournamentPlan(
            question=question,
            baseline=CandidateSpec(
                "baseline",
                "INDEX_READER",
                f"{READER_MODEL_PREFIX}{DEFAULT_BASELINE_PROFILE}",
                DEFAULT_BASELINE_PROFILE,
            ),
            candidates=tuple(
                CandidateSpec(
                    f"candidate_{profile_id}",
                    "INDEX_READER",
                    f"{READER_MODEL_PREFIX}{profile_id}",
                    profile_id,
                )
                for profile_id in chosen
            ),
            judge_model_id="deterministic.judge",
            project_id=project_id or self.identity.project_id,
            page_ids=tuple(page_ids or [page.page_id for page in self.corpus.pages]),
            runsheet_id=self.corpus.runsheet["runsheet_id"],
            max_candidates=self.policy.profile.max_candidates,
        )

    def create_tournament_plan(self, ctx, params: dict) -> TournamentPlan:
        return self.build_tournament_plan(
            params["question"],
            int(params.get("candidate_count", 3)),
            params.get("project_id"),
            params.get("page_ids"),
        )

    def run_tournament_tool(self, ctx, params: dict) -> dict:
        plan = self.build_tournament_plan(
            params["question"], int(params.get("candidate_count", 3)), params.get("project_id")
        )
        job_id = self.open_job("tournament", plan.project_id)
        try:
            result = self.tournaments.run(plan, stop_check=lambda: self.job_stopped(job_id))
        finally:
            self.close_job(job_id)
        payload = result.to_dict()
        payload["job_id"] = job_id
        payload["rubric"] = rubric()
        return payload

    def compare_candidate_scores(self, tournament_id: str) -> dict:
        rows = self.store.fetchall(
            """
            SELECT c.candidate_id, c.role_id, c.model_id, c.status, c.is_baseline, c.simulated,
                   c.iteration, c.output_hash
              FROM cb_tournament_candidates c
             WHERE c.tournament_id = ?
             ORDER BY c.is_baseline DESC, c.candidate_id
            """,
            (tournament_id,),
        )
        candidates = []
        for row in rows:
            scores = {
                score["dimension"]: {
                    "value": round(score["value"], 4),
                    "weight": score["weight"],
                    "blocking": bool(score["blocking"]),
                }
                for score in self.store.fetchall(
                    "SELECT * FROM cb_candidate_scores WHERE candidate_id = ? ORDER BY dimension",
                    (row["candidate_id"],),
                )
            }
            decision = self.store.fetchone(
                "SELECT decision, rationale, evidence_json FROM cb_judge_decisions WHERE candidate_id = ?",
                (row["candidate_id"],),
            )
            candidates.append(
                {
                    "candidate_id": row["candidate_id"],
                    "role_id": row["role_id"],
                    "model_id": row["model_id"],
                    "status": row["status"],
                    "is_baseline": bool(row["is_baseline"]),
                    "simulated": bool(row["simulated"]),
                    "iteration": row["iteration"],
                    "output_hash": row["output_hash"],
                    "scores": scores,
                    "decision": dict(decision) if decision else None,
                }
            )
        return {"tournament_id": tournament_id, "candidates": candidates, "rubric": rubric()}

    # -- jobs -------------------------------------------------------------
    def open_job(self, kind: str, project_id: str | None = None, envelope_id: str | None = None) -> str:
        job_id = self.store.new_id("job")
        now = self.store.now()
        self.store.execute(
            """
            INSERT INTO cb_jobs (job_id, project_id, kind, state, envelope_id, created_at, updated_at)
            VALUES (?, ?, ?, 'RUNNING', ?, ?, ?)
            """,
            (job_id, project_id, kind, envelope_id, now, now),
        )
        self.store.audit("job.started", "job", job_id, {"kind": kind}, project_id=project_id)
        return job_id

    def close_job(self, job_id: str, state: str = "SUCCEEDED") -> None:
        self.store.execute(
            "UPDATE cb_jobs SET state = ?, updated_at = ? WHERE job_id = ?",
            (state, self.store.now(), job_id),
        )
        self.store.audit("job.finished", "job", job_id, {"state": state})

    def job_stopped(self, job_id: str) -> bool:
        row = self.store.fetchone("SELECT stop_requested FROM cb_jobs WHERE job_id = ?", (job_id,))
        return bool(row and row["stop_requested"])

    def stop_job(self, job_id: str) -> dict:
        row = self.store.fetchone("SELECT * FROM cb_jobs WHERE job_id = ?", (job_id,))
        if row is None:
            raise ToolInputRejected(
                f"{job_id!r} is not a known job.", detail={"job_id": job_id}
            )
        if row["state"] not in ("QUEUED", "RUNNING"):
            return {"job_id": job_id, "state": row["state"], "detail": "Job was not stoppable."}
        self.store.execute(
            "UPDATE cb_jobs SET stop_requested = 1, state = 'STOPPED', updated_at = ? WHERE job_id = ?",
            (self.store.now(), job_id),
        )
        self.store.audit("job.stopped", "job", job_id, {"requested_by": self.identity.requesting_user})
        return {"job_id": job_id, "state": "STOPPED", "detail": "Stop requested and recorded."}

    def stop_all_jobs(self) -> list[dict]:
        results = []
        for job in self.state.active_jobs():
            results.append(self.stop_job(job["job_id"]))
        return results

    # -- explanation ------------------------------------------------------
    def explain(self, subject_id: str, output_format: str = "standard", verbosity: str = "standard") -> dict:
        receipts = self.store.receipts_for(subject_id)
        if not receipts:
            receipt = self.store.get_receipt(subject_id)
            receipts = [receipt] if receipt else []
        if not receipts:
            return {
                "subject_id": subject_id,
                "explanation": (
                    f"No receipt exists for {subject_id}. Nothing has been accepted or rejected "
                    "for that subject, so there is nothing to explain yet."
                ),
                "format": output_format,
                "evidence": [],
            }
        latest = receipts[-1]
        payload = latest["payload"]
        lines = []
        if payload.get("question"):
            lines.append(f"Question: {payload['question']}")
        if "baseline_preserved" in payload:
            lines.append(
                "The accepted baseline was preserved."
                if payload["baseline_preserved"]
                else f"A candidate replaced the baseline: {payload.get('accepted_candidate_id')}."
            )
        for candidate in payload.get("candidates", [])[:5]:
            decision = (candidate.get("decision") or {}).get("decision", "SCORED")
            aggregate = candidate.get("scorecard", {}).get("aggregate")
            lines.append(
                f"{candidate['candidate_id']} ({candidate['spec']['profile_id']}): {decision}, score {aggregate}."
            )
        consensus = payload.get("consensus", {})
        if consensus:
            lines.append(
                f"{consensus.get('agreed_count', 0)} cells agreed, "
                f"{consensus.get('disagreed_count', 0)} disagreed, "
                f"{consensus.get('contested_unreadable_count', 0)} contested as unreadable."
            )
        if verbosity == "concise" or output_format == "phone":
            lines = lines[:4]
        return {
            "subject_id": subject_id,
            "explanation": " ".join(lines) if lines else "Receipt recorded with no narrative fields.",
            "format": output_format,
            "receipt_id": latest["receipt_id"],
            "evidence": [latest["payload_hash"]],
        }

    # -- convenience ------------------------------------------------------
    def tool_context(self, **metadata) -> ToolContext:
        return ToolContext(
            runtime=self,
            project_id=metadata.pop("project_id", self.identity.project_id),
            plan_id=metadata.pop("plan_id", None),
            envelope_id=metadata.pop("envelope_id", None),
            metadata=metadata,
        )

    def reconcile_candidate(self, candidate: dict) -> dict:
        reconciliation = reconcile(candidate.get("entries", []), self.corpus.runsheet)
        return {"reconciliation": reconciliation, "summary": summarize(reconciliation)}

    def model_catalog(self) -> list[dict]:
        return self.gateway.catalog()
