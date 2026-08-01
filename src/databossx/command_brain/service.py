"""The Command Brain itself.

Implements the operating loop:

    LISTEN → UNDERSTAND → RETRIEVE CURRENT STATE → IDENTIFY INTENT →
    IDENTIFY RISK → BUILD PLAN → SELECT AGENTS → REQUEST APPROVAL WHEN REQUIRED
    → EXECUTE ALLOWLISTED WORK → VERIFY RESULTS → COMPARE AGAINST BASELINE →
    ACCEPT, REJECT, OR QUARANTINE → RECORD RECEIPT → EXPLAIN THE RESULT

The loop always stops at "request approval" for anything consequential.
:meth:`CommandBrain.handle` can produce a plan and a drafted envelope; it cannot
execute one. Execution requires :meth:`approve` (an authenticated act) followed by
:meth:`execute`, and the approval is bound to the exact envelope hash the
operator saw.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .autonomy import AutonomyLevel
from .envelope import TaskEnvelope
from .errors import ApprovalError, AutonomyViolation, ClarificationRequired, CommandBrainError
from .intent import CONSEQUENTIAL, IntentEngine, IntentKind, NormalizedIntent
from .memory import MemoryKind
from .planner import Plan, Planner
from .policy import AuthoritySource, PolicyProfile
from .redaction import redact
from .roles import get_role
from .tools import ToolResult
from .util import canonical_hash


@dataclass
class CommandResponse:
    """What the operator sees before anything happens."""

    conversation_id: str
    transcript: str
    channel: str
    intent: dict
    interpreted_request: str
    plan: dict
    autonomy_level: int
    autonomy_level_name: str
    requires_approval: bool
    envelope: dict | None = None
    envelope_hash: str | None = None
    approval_prompt: str | None = None
    results: dict = field(default_factory=dict)
    facts: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    simulated_components: list = field(default_factory=list)
    spoken_summary: str = ""
    receipt_id: str | None = None
    error: dict | None = None

    def to_dict(self) -> dict:
        return redact(
            {
                "conversation_id": self.conversation_id,
                "transcript": self.transcript,
                "channel": self.channel,
                "intent": self.intent,
                "interpreted_request": self.interpreted_request,
                "plan": self.plan,
                "autonomy_level": self.autonomy_level,
                "autonomy_level_name": self.autonomy_level_name,
                "requires_approval": self.requires_approval,
                "envelope": self.envelope,
                "envelope_hash": self.envelope_hash,
                "approval_prompt": self.approval_prompt,
                "results": self.results,
                "facts": self.facts,
                "warnings": self.warnings,
                "simulated_components": self.simulated_components,
                "spoken_summary": self.spoken_summary,
                "receipt_id": self.receipt_id,
                "error": self.error,
            }
        )


#: Intents whose plans run entirely at OBSERVE and touch nothing.
IMMEDIATE_INTENTS = frozenset(
    {
        IntentKind.STATUS_QUERY,
        IntentKind.BLOCKER_QUERY,
        IntentKind.APPROVAL_QUEUE_QUERY,
        IntentKind.EVIDENCE_QUERY,
        IntentKind.EXPLAIN,
        IntentKind.SHOW_DISAGREEMENTS,
        IntentKind.SET_MODE,
        IntentKind.PROHIBIT_TARGET,
        IntentKind.STOP_ALL,
        IntentKind.CORRECTION,
    }
)


class CommandBrain:
    def __init__(self, runtime, requesting_user: str | None = None):
        self.runtime = runtime
        self.store = runtime.store
        self.intents = IntentEngine()
        self.planner = Planner(runtime.store)
        self.requesting_user = requesting_user or runtime.identity.requesting_user
        self._conversation_id: str | None = None
        self._last_intent: NormalizedIntent | None = None
        self._plans: dict[str, Plan] = {}
        self._envelopes: dict[str, TaskEnvelope] = {}

    # ------------------------------------------------------------------
    # Conversation
    # ------------------------------------------------------------------
    def start_conversation(self, channel: str = "text", project_id: str | None = None) -> str:
        conversation_id = self.store.new_id("conv")
        self.store.execute(
            "INSERT INTO cb_conversations (id, project_id, channel, created_at) VALUES (?, ?, ?, ?)",
            (conversation_id, project_id or self.runtime.identity.project_id, channel, self.store.now()),
        )
        self._conversation_id = conversation_id
        self.store.audit(
            "conversation.started", "conversation", conversation_id, {"channel": channel}
        )
        return conversation_id

    def _record_message(self, role: str, content: str) -> None:
        if self._conversation_id is None:
            self.start_conversation()
        row = self.store.fetchone(
            "SELECT COUNT(*) AS n FROM cb_messages WHERE conversation_id = ?",
            (self._conversation_id,),
        )
        self.store.execute(
            "INSERT INTO cb_messages (id, conversation_id, ordinal, role, content, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                self.store.new_id("msg"),
                self._conversation_id,
                int(row["n"]) + 1,
                role,
                content,
                self.store.now(),
            ),
        )

    def _persist_intent(self, intent: NormalizedIntent, transcript_id: str) -> str:
        intent_id = self.store.new_id("int")
        from .util import canonical_json

        self.store.execute(
            """
            INSERT INTO cb_intents (
                id, transcript_id, kind, risk, confidence, requires_clarification,
                slots_json, quoted_segments_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                intent_id,
                transcript_id,
                intent.kind.value,
                intent.risk.value,
                intent.confidence,
                int(intent.requires_clarification),
                canonical_json(intent.slots),
                canonical_json(list(intent.quoted_segments)),
                self.store.now(),
            ),
        )
        return intent_id

    def _store_transcript(self, transcript: str, channel: str) -> str:
        transcript_id = self.store.new_id("tr")
        self.store.execute(
            """
            INSERT INTO cb_transcripts (id, conversation_id, voice_session_id, raw_text, confirmed, created_at)
            VALUES (?, ?, NULL, ?, 1, ?)
            """,
            (transcript_id, self._conversation_id, transcript, self.store.now()),
        )
        return transcript_id

    # ------------------------------------------------------------------
    # Core loop
    # ------------------------------------------------------------------
    def handle(
        self,
        transcript: str,
        *,
        channel: str = "text",
        project_id: str | None = None,
        voice_session=None,
    ) -> CommandResponse:
        if self._conversation_id is None:
            self.start_conversation(channel, project_id)
        self._record_message("operator", transcript)
        transcript_id = self._store_transcript(transcript, channel)

        authority = (
            AuthoritySource.SPOKEN_UTTERANCE if channel == "voice" else AuthoritySource.TYPED_UTTERANCE
        )
        intent = self.intents.normalize(transcript, authority)
        self._last_intent = intent
        self._persist_intent(intent, transcript_id)
        project = intent.slots.get("project") or project_id or self.runtime.identity.project_id

        warnings = list(intent.detected_injection)
        if intent.quoted_segments:
            warnings.append(
                f"{len(intent.quoted_segments)} quoted document segment(s) were treated as content, "
                "not as instructions."
            )

        self.store.audit(
            "intent.normalized",
            "transcript",
            transcript_id,
            {
                "kind": intent.kind.value,
                "risk": intent.risk.value,
                "confidence": intent.confidence,
                "authority_source": authority.value,
                "injection_findings": list(intent.detected_injection),
            },
            actor_type="operator",
            actor_id=self.requesting_user,
            project_id=project,
        )

        plan = self.planner.build(intent, project)
        self._plans[plan.plan_id] = plan

        response = CommandResponse(
            conversation_id=self._conversation_id,
            transcript=transcript,
            channel=channel,
            intent=intent.to_dict(),
            interpreted_request=intent.restatement,
            plan=plan.to_dict(),
            autonomy_level=int(plan.autonomy_level),
            autonomy_level_name=AutonomyLevel(plan.autonomy_level).name,
            requires_approval=plan.requires_approval,
            warnings=warnings,
            simulated_components=self._simulated_components(),
        )

        if intent.requires_clarification:
            response.requires_approval = False
            response.error = ClarificationRequired(
                intent.clarification_question or "Clarification required."
            ).to_dict()
            response.spoken_summary = intent.clarification_question
            self._record_message("system", response.spoken_summary)
            return response

        try:
            if intent.kind in IMMEDIATE_INTENTS:
                self._run_immediate(intent, plan, response, project, voice_session)
            elif intent.kind in CONSEQUENTIAL or plan.requires_approval:
                self._prepare_approval(intent, plan, response, project, transcript)
            else:
                self._run_immediate(intent, plan, response, project, voice_session)
        except CommandBrainError as exc:
            response.error = exc.to_dict()
            response.spoken_summary = f"Refused: {exc.message}"
            self.store.audit(
                "command.refused",
                "plan",
                plan.plan_id,
                {"code": exc.code, "message": exc.message},
                project_id=project,
            )

        if not response.spoken_summary:
            response.spoken_summary = response.interpreted_request
        self._record_message("system", response.spoken_summary)
        if voice_session is not None:
            voice_session.speak(response.spoken_summary)
        return response

    # ------------------------------------------------------------------
    def _simulated_components(self) -> list:
        simulated = []
        for entry in self.runtime.model_catalog():
            if entry["simulated"]:
                simulated.append(
                    {
                        "component": entry["model_id"],
                        "kind": "model_adapter",
                        "label": "SIMULATED",
                        "detail": entry["display_name"],
                    }
                )
        return simulated

    def _run_immediate(self, intent, plan, response, project, voice_session) -> None:
        kind = intent.kind
        context = self.runtime.tool_context(project_id=project, plan_id=plan.plan_id)

        if kind is IntentKind.SET_MODE:
            response.results = self.apply_modes(intent.slots.get("modes", {}))
            response.spoken_summary = (
                "Mode updated. Current ceiling: "
                f"{self.runtime.policy.profile.autonomy_ceiling.name}; "
                f"local-only: {self.runtime.policy.profile.local_only}; "
                f"cloud models: {self.runtime.policy.profile.cloud_models_allowed}."
            )
            return

        if kind is IntentKind.PROHIBIT_TARGET:
            targets = intent.slots.get("targets", [])
            profile = self.runtime.policy.profile
            for target in targets:
                profile = profile.with_prohibited_target(target)
            self.runtime.policy.set_profile(profile)
            self.runtime.memory.remember(
                MemoryKind.USER_INSTRUCTION,
                f"Operator prohibited: {', '.join(targets)}.",
                f"transcript:{self._conversation_id}",
                project_id=project,
            )
            self.store.audit("policy.target_prohibited", "policy", "profile", {"targets": targets})
            response.results = {"prohibited_targets": sorted(profile.prohibited_targets)}
            response.spoken_summary = f"{', '.join(targets)} is off limits until you lift it."
            return

        if kind is IntentKind.STOP_ALL:
            stopped = self.runtime.stop_all_jobs()
            if voice_session is not None:
                voice_session.emergency_stop("operator said stop")
            response.results = {"stopped_jobs": stopped}
            response.spoken_summary = (
                f"Stopped {len(stopped)} job(s). Nothing further will start without your approval."
            )
            return

        if kind is IntentKind.CORRECTION:
            response.results = {"previous_intent_discarded": True}
            response.spoken_summary = "Discarded. Say the corrected instruction and I will re-read it."
            return

        if kind in (IntentKind.STATUS_QUERY, IntentKind.BLOCKER_QUERY):
            system = self.runtime.tools.invoke("get_system_status", {}, context)
            facts = (
                self.runtime.state.blockers(project)
                if kind is IntentKind.BLOCKER_QUERY
                else self.runtime.state.status_facts(project)
            ) if project else []
            response.facts = [fact.to_dict() for fact in facts]
            response.results = {"system_status": system.output}
            headline = (
                f"{len(response.facts)} finding(s)."
                if response.facts
                else "No project selected; showing system state only."
            )
            response.spoken_summary = " ".join(
                [headline] + [fact["statement"] for fact in response.facts[:3]]
            )
            self._write_answer_receipt(plan, response, project)
            return

        if kind is IntentKind.APPROVAL_QUEUE_QUERY:
            result = self.runtime.tools.invoke("get_pending_approvals", {}, context)
            response.results = result.output
            count = len(result.output.get("items", []))
            response.spoken_summary = f"{count} TaskEnvelope draft(s) are waiting on your approval."
            return

        if kind in (IntentKind.EVIDENCE_QUERY, IntentKind.EXPLAIN, IntentKind.SHOW_DISAGREEMENTS):
            subject_id = intent.slots.get("subject_id") or self._latest_subject()
            if subject_id is None:
                response.spoken_summary = "There is no completed result to explain yet."
                return
            result = self.runtime.tools.invoke(
                "explain_finding",
                {
                    "subject_id": subject_id,
                    "format": intent.slots.get("format", "standard"),
                    "verbosity": intent.slots.get("verbosity", "standard"),
                },
                context,
            )
            response.results = result.output
            response.spoken_summary = result.output["explanation"]
            return

        response.spoken_summary = intent.restatement

    def _latest_subject(self) -> str | None:
        row = self.store.fetchone(
            "SELECT subject_id FROM cb_receipts ORDER BY created_at DESC, receipt_id DESC LIMIT 1"
        )
        return row["subject_id"] if row else None

    def _write_answer_receipt(self, plan, response, project) -> None:
        receipt = self.store.write_receipt(
            "command_answer",
            plan.plan_id,
            {
                "interpreted_request": response.interpreted_request,
                "facts": response.facts,
                "autonomy_level": response.autonomy_level,
                "policy": self.runtime.policy.profile.to_dict(),
            },
            project_id=project,
        )
        response.receipt_id = receipt["receipt_id"]

    # ------------------------------------------------------------------
    def _prepare_approval(self, intent, plan, response, project, transcript) -> None:
        """Draft the envelope and stop. This method never executes anything."""
        roles = [get_role(role_id) for role_id in plan.role_ids if role_id]
        profile = self.runtime.policy.profile
        writer = any(role.is_writer for role in roles)
        level = min(plan.autonomy_level, AutonomyLevel.BOUNDED_WRITER)

        envelope = self.runtime.drafter.draft(
            requesting_user=self.requesting_user,
            transcript=transcript,
            normalized_intent=intent.restatement,
            goal=intent.restatement,
            project_id=project,
            autonomy_level=level,
            plan_id=plan.plan_id,
            inputs=tuple(intent.slots.get("targets", ())),
            controlling_artifacts=tuple(
                artifact["artifact_id"] for artifact in self.runtime.state.artifacts(project)[:10]
            ),
            expected_input_hashes=tuple(
                artifact["sha256"] for artifact in self.runtime.state.artifacts(project)[:10]
            ),
            expected_outputs=("tournament_receipt",) if intent.kind is IntentKind.RUN_TOURNAMENT else ("task_draft",),
            allowed_paths=("<authorized worktree>",) if writer else (),
            prohibited_paths=tuple(sorted(profile.prohibited_targets)) or ("client workbooks", "released reports"),
            tools=tuple(plan.tool_ids),
            assigned_roles=tuple(plan.role_ids),
            model_restrictions={
                "local_only": profile.local_only,
                "cloud_allowed": profile.cloud_models_allowed,
                "simulated_labelled": True,
            },
            data_sensitivity=profile.data_sensitivity,
            approval_requirements=("operator_approval",) + (("writer_ack",) if writer else ()),
            lease_required=writer,
            fencing_token_required=writer,
            timeout_seconds=plan.estimated_seconds,
            cost_budget=profile.cost_ceiling,
            retry_limit=1,
            validation_gates=("schema", "policy", "scoring_rubric", "independent_judge", "receipt"),
            acceptance_criteria=(
                "Every candidate output validates against its role schema.",
                "No blocking scoring gate fails.",
                "The accepted baseline is preserved unless a candidate measurably wins.",
            ),
            rollback_plan=(
                "Nothing accepted is overwritten. Rejected candidates are discarded and quarantined "
                "candidates are retained for inspection only."
            ),
            stop_conditions=plan.stop_conditions,
            hold_state="HOLD" if profile.global_hold else "NONE",
            risk=plan.risk,
        )
        self._envelopes[envelope.task_id] = envelope

        response.envelope = envelope.phone_safe()
        response.envelope_hash = envelope.envelope_hash
        response.requires_approval = True
        response.approval_prompt = envelope.plain_language()
        response.spoken_summary = envelope.plain_language()
        self.runtime.memory.remember(
            MemoryKind.PROPOSED_PLAN,
            f"Proposed: {intent.restatement}",
            f"plan:{plan.plan_id}",
            project_id=project,
            confidence=intent.confidence,
        )

    # ------------------------------------------------------------------
    # Approval and execution
    # ------------------------------------------------------------------
    def envelope(self, envelope_id: str) -> TaskEnvelope:
        envelope = self._envelopes.get(envelope_id) or self.runtime.drafter.load(envelope_id)
        if envelope is None:
            raise ApprovalError(
                f"{envelope_id!r} is not a drafted envelope.", detail={"envelope_id": envelope_id}
            )
        return envelope

    def approve(self, envelope_id: str, approver_id: str, *, method: str = "authenticated_ui", ttl_seconds: int = 900):
        """Authenticated approval of one exact envelope hash. Never callable by voice."""
        envelope = self.envelope(envelope_id)
        return self.runtime.approvals.approve(
            envelope, approver_id, method=method, ttl_seconds=ttl_seconds
        )

    def execute(self, envelope_id: str, approval_id: str) -> dict:
        """Run an approved envelope under a temporarily elevated ceiling."""
        envelope = self.envelope(envelope_id)
        ceiling = self.runtime.policy.profile.autonomy_ceiling
        if envelope.autonomy_level > ceiling:
            # Approval authorizes one envelope; it never raises the operator's
            # standing mode. Both gates have to be open.
            raise AutonomyViolation(
                f"This envelope needs autonomy {envelope.autonomy_level.name} but the current mode "
                f"ceiling is {ceiling.name}. Approval does not raise the mode — change the mode first.",
                detail={"envelope_id": envelope.task_id, "ceiling": ceiling.name},
            )
        approval = self.runtime.approvals.consume(approval_id, envelope)
        plan = self._plan_for_envelope(envelope)

        context = self.runtime.tool_context(
            project_id=envelope.project_id,
            envelope_id=envelope.task_id,
            approval_id=approval.approval_id,
        )
        results = self._execute_plan(plan, envelope, context, approval.approval_id)

        receipt = self.store.write_receipt(
            "command_execution",
            envelope.task_id,
            {
                "envelope_hash": envelope.envelope_hash,
                "approval_id": approval.approval_id,
                "approver": approval.approver_id,
                "plan": plan.to_dict() if plan else None,
                "results": results,
                "policy": self.runtime.policy.profile.to_dict(),
            },
            project_id=envelope.project_id,
        )
        self.store.execute(
            "UPDATE cb_task_envelopes SET state = 'EXECUTED' WHERE envelope_id = ?", (envelope.task_id,)
        )
        results["receipt_id"] = receipt["receipt_id"]
        return results

    def _plan_for_envelope(self, envelope: TaskEnvelope) -> Plan | None:
        for plan in self._plans.values():
            if plan.summary == envelope.normalized_intent:
                return plan
        return None

    def _execute_plan(self, plan, envelope, context, approval_id) -> dict:
        intent_text = envelope.normalized_intent.lower()
        results: dict = {"envelope_id": envelope.task_id, "steps": []}

        def _run(tool_id: str, params: dict) -> ToolResult:
            result = self.runtime.tools.invoke(
                tool_id, params, context, approval_id=approval_id
            )
            results["steps"].append(
                {"tool_id": tool_id, "input_hash": result.input_hash, "output_hash": result.output_hash}
            )
            return result

        if "independent read-only index readings" in intent_text or "tournament" in intent_text:
            tournament = _run(
                "run_synthetic_tournament",
                {
                    "question": envelope.normalized_intent,
                    "candidate_count": self.runtime.policy.profile.max_candidates,
                    "project_id": envelope.project_id,
                },
            )
            results["tournament"] = tournament.output
            results["decision"] = (
                "baseline_preserved"
                if tournament.output["baseline_preserved"]
                else "candidate_accepted"
            )
        elif "improvement loop" in intent_text:
            plan_obj = self.runtime.build_tournament_plan(
                envelope.normalized_intent, self.runtime.policy.profile.max_candidates, envelope.project_id
            )
            results["improvement_loop"] = self.runtime.improvement.run(
                plan_obj,
                max_iterations=self.runtime.policy.profile.max_improvement_iterations,
            )
            results["decision"] = "baseline_preserved"
        elif "reconcile" in intent_text or "runsheet" in intent_text:
            tournament = _run(
                "run_synthetic_tournament",
                {"question": envelope.normalized_intent, "candidate_count": 1, "project_id": envelope.project_id},
            )
            results["tournament"] = tournament.output
            results["decision"] = "reconciliation_reported"
        elif "handoff" in intent_text or "coding" in intent_text:
            results["handoff"] = self._build_handoff(envelope)
            results["decision"] = "handoff_drafted"
        else:
            draft = _run(
                "draft_task_envelope",
                {
                    "goal": envelope.goal,
                    "project_id": envelope.project_id,
                    "autonomy_level": int(AutonomyLevel.DRAFT),
                    "roles": list(envelope.assigned_roles),
                    "tools": list(envelope.tools),
                },
            )
            results["task_draft"] = draft.output
            results["decision"] = "draft_created"

        results["input_manifest_hash"] = canonical_hash(list(envelope.expected_input_hashes))
        return results

    def _build_handoff(self, envelope: TaskEnvelope) -> dict:
        from .dispatcher import build_code_handoff

        return build_code_handoff(
            repository="DataBossX/DataBoss",
            branch="claude/databossx-command-brain-alpha-gh8syu",
            worktree="<isolated worktree assigned by the operator>",
            scope=envelope.goal,
            allowed_files=list(envelope.allowed_paths) or ["<authorized worktree>"],
            prohibited_files=list(envelope.prohibited_paths),
            tests=["command_brain_selftest", "command_brain_policy_gates"],
            acceptance_criteria=list(envelope.acceptance_criteria),
            authority_status="AWAITING_AUTHORIZATION",
            final_sentinel="DATABOSSX_COMMAND_BRAIN_AWAITING_AUTHORIZATION",
        )

    # ------------------------------------------------------------------
    # Modes
    # ------------------------------------------------------------------
    def apply_modes(self, modes: dict) -> dict:
        profile: PolicyProfile = self.runtime.policy.profile
        # Ordered most-restrictive first so a combined utterance such as
        # "read-only, local models only" lands on the tightest ceiling asked for.
        transitions = (
            ("observe_only", PolicyProfile.with_observe_only),
            ("draft_only", PolicyProfile.with_draft_only),
            ("read_only", PolicyProfile.with_read_only),
            ("local_only", PolicyProfile.with_local_only),
            ("no_cloud", PolicyProfile.with_no_cloud),
            ("approval_for_everything", PolicyProfile.with_approval_for_everything),
            ("no_client_files", PolicyProfile.with_no_client_files),
        )
        applied = []
        for mode, transition in transitions:
            if modes.get(mode):
                profile = transition(profile)
                applied.append(mode)
        self.runtime.policy.set_profile(profile)
        for mode in applied:
            self.runtime.memory.remember(
                MemoryKind.USER_INSTRUCTION,
                f"Operator enabled mode: {mode}.",
                f"conversation:{self._conversation_id}",
                project_id=self.runtime.identity.project_id,
            )
        self.store.audit(
            "policy.updated", "policy", "profile", {"applied": applied, "profile": profile.to_dict()}
        )
        return {"applied": applied, "profile": profile.to_dict()}

    # ------------------------------------------------------------------
    def command_center_state(self, project_id: str | None = None) -> dict:
        """Everything the phone/desktop command centre renders, already redacted."""
        project_id = project_id or self.runtime.identity.project_id
        profile = self.runtime.policy.profile
        payload = {
            "policy": profile.to_dict(),
            "autonomy_level": int(profile.autonomy_ceiling),
            "autonomy_level_name": profile.autonomy_ceiling.name,
            "global_hold": profile.global_hold,
            "system": self.runtime.state.system_status(profile, self.runtime.gateway),
            "project": self.runtime.state.project_status(project_id) if project_id else None,
            "pending_approvals": self.runtime.state.pending_approvals(),
            "human_review_queue": self.store.open_human_reviews(project_id),
            "models": self.runtime.model_catalog(),
            "tools": self.runtime.tools.list_tools(),
            "recent_events": self.store.audit_events(limit=25),
            "memory": [item.to_dict() for item in self.runtime.memory.current(project_id)],
            "interpreted_request": self._last_intent.restatement if self._last_intent else None,
            "simulated_components": [
                entry["model_id"] for entry in self.runtime.model_catalog() if entry["simulated"]
            ],
            "priority_actions": [
                "START READ-ONLY TOURNAMENT",
                "REVIEW TASK DRAFT",
                "APPROVE BOUNDED JOB",
                "REJECT PLAN",
                "STOP JOB",
                "QUARANTINE RESULT",
                "OPEN EVIDENCE",
                "ASK FOR HUMAN REVIEW",
            ],
        }
        return redact(payload)
