"""Planning engine.

Turns a normalized intent plus current state into an explicit, inspectable plan:
ordered steps, the tool or role each step uses, the autonomy each step needs, and
the risks the operator should see before approving anything.

The plan is the artifact the operator reads. It is deliberately boring and
enumerable — there is no step called "figure it out".
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .autonomy import AutonomyLevel
from .intent import IntentKind, NormalizedIntent
from .policy import RiskLevel


@dataclass(frozen=True)
class PlanStep:
    ordinal: int
    description: str
    required_level: AutonomyLevel
    tool_id: str | None = None
    role_id: str | None = None

    def to_dict(self) -> dict:
        return {
            "ordinal": self.ordinal,
            "description": self.description,
            "required_level": int(self.required_level),
            "required_level_name": AutonomyLevel(self.required_level).name,
            "tool_id": self.tool_id,
            "role_id": self.role_id,
        }


@dataclass(frozen=True)
class Plan:
    plan_id: str
    title: str
    summary: str
    steps: tuple
    autonomy_level: AutonomyLevel
    risk: RiskLevel
    project_id: str | None = None
    estimated_seconds: int = 60
    requires_approval: bool = False
    risks: tuple = ()
    stop_conditions: tuple = field(
        default_factory=lambda: (
            "Operator says stop.",
            "A blocking validation gate fails.",
            "Cost, token, or timeout budget is exhausted.",
            "Uncertainty requires a human decision.",
        )
    )

    def to_dict(self) -> dict:
        return {
            "plan_id": self.plan_id,
            "title": self.title,
            "summary": self.summary,
            "project_id": self.project_id,
            "autonomy_level": int(self.autonomy_level),
            "autonomy_level_name": AutonomyLevel(self.autonomy_level).name,
            "risk": self.risk.value,
            "estimated_seconds": self.estimated_seconds,
            "requires_approval": self.requires_approval,
            "risks": list(self.risks),
            "stop_conditions": list(self.stop_conditions),
            "steps": [step.to_dict() for step in self.steps],
        }

    @property
    def tool_ids(self) -> tuple:
        return tuple(step.tool_id for step in self.steps if step.tool_id)

    @property
    def role_ids(self) -> tuple:
        seen = []
        for step in self.steps:
            if step.role_id and step.role_id not in seen:
                seen.append(step.role_id)
        return tuple(seen)


L0 = AutonomyLevel.OBSERVE
L1 = AutonomyLevel.DRAFT
L2 = AutonomyLevel.READ_ONLY_EXECUTE
L3 = AutonomyLevel.BOUNDED_WRITER


def _steps(*specs) -> tuple:
    return tuple(
        PlanStep(index, spec[0], spec[1], spec[2] if len(spec) > 2 else None, spec[3] if len(spec) > 3 else None)
        for index, spec in enumerate(specs, start=1)
    )


class Planner:
    def __init__(self, store):
        self.store = store

    def build(self, intent: NormalizedIntent, project_id: str | None = None) -> Plan:
        plan_id = self.store.new_id("plan")
        kind = intent.kind
        project = intent.slots.get("project") or project_id

        if kind in (IntentKind.STATUS_QUERY, IntentKind.BLOCKER_QUERY):
            blocker = kind is IntentKind.BLOCKER_QUERY
            plan = Plan(
                plan_id,
                "Report current state" if not blocker else "Explain what is blocking",
                intent.restatement,
                _steps(
                    ("Read system status.", L0, "get_system_status", "COMMANDER"),
                    ("Read project status, jobs, defects, holds, and approvals.", L0, "get_project_status", "COMMANDER"),
                    ("Summarise each finding with its source and observation time.", L0, None, "COMMANDER"),
                ),
                L0,
                RiskLevel.INFORMATIONAL,
                project,
                estimated_seconds=15,
            )

        elif kind is IntentKind.APPROVAL_QUEUE_QUERY:
            plan = Plan(
                plan_id,
                "List pending approvals",
                intent.restatement,
                _steps(("Read every TaskEnvelope draft awaiting approval.", L0, "get_pending_approvals", "COMMANDER")),
                L0,
                RiskLevel.INFORMATIONAL,
                project,
                estimated_seconds=10,
            )

        elif kind is IntentKind.EVIDENCE_QUERY:
            plan = Plan(
                plan_id,
                "Open supporting evidence",
                intent.restatement,
                _steps(
                    ("Resolve the finding to its receipt.", L0, "read_validation_receipt", "COMMANDER"),
                    ("Show the source regions and hashes behind each asserted value.", L0, "explain_finding", "REPORT_READER"),
                ),
                L0,
                RiskLevel.INFORMATIONAL,
                project,
                estimated_seconds=20,
            )

        elif kind is IntentKind.EXPLAIN:
            plan = Plan(
                plan_id,
                "Explain the current result",
                intent.restatement,
                _steps(("Render a plain-language explanation of the latest result.", L0, "explain_finding", "COMMANDER")),
                L0,
                RiskLevel.INFORMATIONAL,
                project,
                estimated_seconds=10,
            )

        elif kind is IntentKind.SHOW_DISAGREEMENTS:
            plan = Plan(
                plan_id,
                "Show agent disagreements",
                intent.restatement,
                _steps(
                    ("Load the latest tournament scores.", L0, "compare_candidate_scores", "JUDGE"),
                    ("List each disagreement with the competing readings and evidence.", L0, "explain_finding", "JUDGE"),
                ),
                L0,
                RiskLevel.INFORMATIONAL,
                project,
                estimated_seconds=20,
            )

        elif kind is IntentKind.RUN_TOURNAMENT:
            count = int(intent.slots.get("candidate_count", 3))
            plan = Plan(
                plan_id,
                f"Run {count} independent read-only index readings",
                intent.restatement,
                _steps(
                    ("Freeze and hash the accepted baseline reading.", L1, "create_tournament_plan", "PLANNER"),
                    (f"Run {count} independent readers against the registered pages.", L2, "run_synthetic_tournament", "INDEX_READER"),
                    ("Reconcile each reading against the registered Runsheet.", L2, None, "RUNSHEET_RECONCILER"),
                    ("Score every candidate against the frozen rubric.", L2, "compare_candidate_scores", "JUDGE"),
                    ("Judge independently and preserve the baseline unless a candidate wins.", L2, None, "JUDGE"),
                    ("Queue contested cells for human review.", L1, "request_human_review", "HUMAN_REVIEW"),
                ),
                L2,
                RiskLevel.MEDIUM,
                project,
                estimated_seconds=1080,
                requires_approval=True,
                risks=(
                    "Read-only: no workbook, report, or client artifact is modified.",
                    "Candidates may disagree; disagreements are reported, not resolved by vote.",
                    "Simulated readers are labelled as simulated in every result.",
                ),
            )

        elif kind is IntentKind.COMPARE_RUNSHEET:
            plan = Plan(
                plan_id,
                "Reconcile index readings against the Runsheet",
                intent.restatement,
                _steps(
                    ("Load the registered Runsheet artifact by ID.", L0, "get_artifact_metadata", "RUNSHEET_RECONCILER"),
                    ("Compare every extracted entry field by field.", L2, "compare_candidate_scores", "RUNSHEET_RECONCILER"),
                    ("Emit matches, conflicts, and unreadable-source rows separately.", L2, None, "RUNSHEET_RECONCILER"),
                ),
                L2,
                RiskLevel.LOW,
                project,
                estimated_seconds=240,
                requires_approval=True,
                risks=("Read-only comparison. Conflicts are reported, never auto-resolved.",),
            )

        elif kind is IntentKind.IMPROVEMENT_LOOP:
            plan = Plan(
                plan_id,
                "Bounded improvement loop",
                intent.restatement,
                _steps(
                    ("Freeze the accepted baseline and its hash.", L1, "create_tournament_plan", "PLANNER"),
                    ("Generate a candidate under the same frozen criteria.", L2, "run_synthetic_tournament", "INDEX_READER"),
                    ("Score the candidate and compare against the baseline.", L2, "compare_candidate_scores", "JUDGE"),
                    ("Reject regressions; keep the baseline unchanged.", L2, None, "JUDGE"),
                    ("Stop when improvement is insignificant or the budget is reached.", L1, None, "PLANNER"),
                ),
                L2,
                RiskLevel.MEDIUM,
                project,
                estimated_seconds=1800,
                requires_approval=True,
                risks=(
                    "The accepted baseline is never mutated during experimentation.",
                    "A candidate that scores worse is rejected and the baseline is kept.",
                ),
            )

        elif kind is IntentKind.DRAFT_REPAIR_TASK:
            plan = Plan(
                plan_id,
                "Draft the lowest-risk repair task",
                intent.restatement,
                _steps(
                    ("Read the open defects and active holds.", L0, "get_open_defects", "COMMANDER"),
                    ("Identify the smallest change that clears the blocking defect.", L1, None, "PLANNER"),
                    ("Draft a scoped TaskEnvelope with rollback and validation gates.", L1, "draft_task_envelope", "PLANNER"),
                ),
                L1,
                RiskLevel.MEDIUM,
                project,
                estimated_seconds=60,
                requires_approval=True,
                risks=("Draft only. Nothing executes until you approve this exact envelope hash.",),
            )

        elif kind is IntentKind.DISPATCH_CODE_AGENT:
            target = intent.slots.get("agent_target", "a coding agent")
            plan = Plan(
                plan_id,
                f"Prepare a bounded coding handoff for {target}",
                intent.restatement,
                _steps(
                    ("Confirm the repository, branch, and isolated worktree.", L1, None, "PLANNER"),
                    ("Draft a BOUNDED_WRITER TaskEnvelope with allowed and prohibited files.", L1, "draft_task_envelope", "PLANNER"),
                    ("Build the handoff package with authority status and tests.", L1, None, "CODE_BUILDER"),
                    ("Route an independent review to a different lane.", L1, "draft_review_request", "CODE_REVIEWER"),
                ),
                L1,
                RiskLevel.HIGH,
                project,
                estimated_seconds=120,
                requires_approval=True,
                risks=(
                    "Writer authority requires an approved envelope, a lease, and a current fencing token.",
                    "The writer and reviewer may not share a worktree lane.",
                    "Alpha produces the handoff package; it does not execute the coding agent.",
                ),
            )

        elif kind is IntentKind.REQUEST_REVIEW:
            plan = Plan(
                plan_id,
                "Request an independent review",
                intent.restatement,
                _steps(
                    ("Identify the subject and its receipt.", L0, "read_validation_receipt", "COMMANDER"),
                    ("Draft the review request for an independent reviewer lane.", L1, "draft_review_request", "CODE_REVIEWER"),
                ),
                L1,
                RiskLevel.LOW,
                project,
                estimated_seconds=45,
            )

        elif kind is IntentKind.SET_MODE:
            plan = Plan(
                plan_id,
                "Change operating mode",
                intent.restatement,
                _steps(("Apply the requested policy change and record it in memory and audit.", L0, None, "COMMANDER")),
                L0,
                RiskLevel.LOW,
                project,
                estimated_seconds=5,
            )

        elif kind is IntentKind.PROHIBIT_TARGET:
            plan = Plan(
                plan_id,
                "Mark targets off limits",
                intent.restatement,
                _steps(("Add the named targets to the prohibited list until you lift it.", L0, None, "COMMANDER")),
                L0,
                RiskLevel.LOW,
                project,
                estimated_seconds=5,
            )

        elif kind is IntentKind.STOP_ALL:
            plan = Plan(
                plan_id,
                "Stop queued work",
                intent.restatement,
                _steps(
                    ("List every queued and running job.", L0, "get_active_jobs", "COMMANDER"),
                    ("Request a stop on each stoppable job.", L0, "stop_queued_job", "COMMANDER"),
                ),
                L0,
                RiskLevel.LOW,
                project,
                estimated_seconds=5,
            )

        elif kind is IntentKind.QUARANTINE:
            plan = Plan(
                plan_id,
                "Quarantine a result",
                intent.restatement,
                _steps(("Quarantine the named subject so it cannot be accepted.", L1, "quarantine_candidate", "COMMANDER")),
                L1,
                RiskLevel.MEDIUM,
                project,
                estimated_seconds=5,
                risks=("Quarantine only restricts; it never alters the accepted baseline.",),
            )

        elif kind is IntentKind.CORRECTION:
            plan = Plan(
                plan_id,
                "Discard the previous interpretation",
                intent.restatement,
                _steps(("Supersede the previous intent and wait for the corrected instruction.", L0, None, "COMMANDER")),
                L0,
                RiskLevel.INFORMATIONAL,
                project,
                estimated_seconds=1,
            )

        else:
            plan = Plan(
                plan_id,
                "Clarification required",
                intent.clarification_question or "The request could not be mapped to a known action.",
                _steps(("Ask the operator to restate the request.", L0, None, "COMMANDER")),
                L0,
                RiskLevel.INFORMATIONAL,
                project,
                estimated_seconds=1,
            )

        self._persist(plan, intent)
        return plan

    def _persist(self, plan: Plan, intent: NormalizedIntent) -> None:
        self.store.execute(
            """
            INSERT INTO cb_plans (id, intent_id, project_id, title, summary, autonomy_level, status, created_at)
            VALUES (?, NULL, ?, ?, ?, ?, 'DRAFT', ?)
            """,
            (
                plan.plan_id,
                plan.project_id,
                plan.title,
                plan.summary,
                int(plan.autonomy_level),
                self.store.now(),
            ),
        )
        for step in plan.steps:
            self.store.execute(
                """
                INSERT INTO cb_plan_steps (id, plan_id, ordinal, description, tool_id, role_id, required_level, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'PENDING')
                """,
                (
                    self.store.new_id("step"),
                    plan.plan_id,
                    step.ordinal,
                    step.description,
                    step.tool_id,
                    step.role_id,
                    int(step.required_level),
                ),
            )
        self.store.audit(
            "plan.created",
            "plan",
            plan.plan_id,
            {
                "title": plan.title,
                "intent": intent.kind.value,
                "autonomy_level": int(plan.autonomy_level),
                "steps": len(plan.steps),
                "requires_approval": plan.requires_approval,
            },
            project_id=plan.project_id,
        )
