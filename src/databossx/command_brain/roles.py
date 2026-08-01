"""Bounded agent-role registry.

A role is a permission envelope, not a personality. Each role declares exactly
which tools it may call, which it may never call, what it may read and write,
how autonomous it may be, and the schema its output must satisfy. Dispatching a
role that is not in this registry is a refusal.
"""

from __future__ import annotations

from dataclasses import dataclass

from .autonomy import AutonomyLevel
from .errors import AgentNotRegistered, RegistryFrozen
from .schemas import AGENT_OUTPUT_SCHEMAS
from .util import canonical_hash


@dataclass(frozen=True)
class AgentRole:
    role_id: str
    description: str
    permitted_tools: tuple
    prohibited_tools: tuple
    read_scope: tuple
    write_scope: tuple
    project_scope: str
    max_autonomy: AutonomyLevel
    required_approvals: tuple
    required_validation: tuple
    timeout_seconds: int
    retry_limit: int
    cost_limit: str
    output_schema: dict
    receipt_required: bool = True
    #: A writer role holds a single-writer lease on its lane while it runs.
    is_writer: bool = False
    #: True for roles that may never sign off on their own output.
    self_judgement_prohibited: bool = True

    def __post_init__(self):
        object.__setattr__(self, "max_autonomy", AutonomyLevel.parse(self.max_autonomy))
        for name in ("permitted_tools", "prohibited_tools", "read_scope", "write_scope",
                     "required_approvals", "required_validation"):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        overlap = set(self.permitted_tools) & set(self.prohibited_tools)
        if overlap:
            raise RegistryFrozen(
                f"Role {self.role_id} both permits and prohibits {sorted(overlap)}.",
                detail={"role_id": self.role_id},
            )
        if self.is_writer and self.max_autonomy < AutonomyLevel.BOUNDED_WRITER:
            raise RegistryFrozen(
                f"Role {self.role_id} claims writer status below BOUNDED_WRITER.",
                detail={"role_id": self.role_id},
            )
        if not self.is_writer and self.write_scope:
            raise RegistryFrozen(
                f"Non-writer role {self.role_id} declares a write scope.",
                detail={"role_id": self.role_id},
            )

    def may_use(self, tool_id: str) -> bool:
        if tool_id in self.prohibited_tools:
            return False
        return "*" in self.permitted_tools or tool_id in self.permitted_tools

    def output_schema_hash(self) -> str:
        return canonical_hash(self.output_schema)

    def to_dict(self) -> dict:
        return {
            "role_id": self.role_id,
            "description": self.description,
            "permitted_tools": list(self.permitted_tools),
            "prohibited_tools": list(self.prohibited_tools),
            "read_scope": list(self.read_scope),
            "write_scope": list(self.write_scope),
            "project_scope": self.project_scope,
            "max_autonomy": int(self.max_autonomy),
            "max_autonomy_name": self.max_autonomy.name,
            "required_approvals": list(self.required_approvals),
            "required_validation": list(self.required_validation),
            "timeout_seconds": self.timeout_seconds,
            "retry_limit": self.retry_limit,
            "cost_limit": self.cost_limit,
            "receipt_required": self.receipt_required,
            "is_writer": self.is_writer,
            "self_judgement_prohibited": self.self_judgement_prohibited,
            "output_schema_hash": self.output_schema_hash(),
        }


_READ_ONLY_TOOLS = (
    "get_system_status",
    "get_project_status",
    "get_active_jobs",
    "get_open_defects",
    "get_pending_approvals",
    "get_release_holds",
    "get_artifact_metadata",
    "get_artifact_hash",
    "verify_artifact_hash",
    "compare_artifact_metadata",
    "read_validation_receipt",
    "explain_finding",
)

_MUTATING_TOOLS = (
    "draft_task_envelope",
    "draft_review_request",
    "assign_read_only_agent",
    "create_tournament_plan",
    "run_synthetic_tournament",
    "quarantine_candidate",
    "request_human_review",
    "stop_queued_job",
)


def _role(**kwargs) -> AgentRole:
    kwargs.setdefault("output_schema", AGENT_OUTPUT_SCHEMAS[kwargs["role_id"]])
    return AgentRole(**kwargs)


ROLES: dict[str, AgentRole] = {}


def _add(role: AgentRole) -> AgentRole:
    ROLES[role.role_id] = role
    return role


_add(
    _role(
        role_id="COMMANDER",
        description=(
            "Understands the operator's request, retrieves current state, and proposes a plan. "
            "Never writes client artifacts."
        ),
        permitted_tools=_READ_ONLY_TOOLS + ("draft_task_envelope", "request_human_review"),
        prohibited_tools=("run_registered_test_suite", "inspect_registered_workbook_read_only"),
        read_scope=("operational_state", "plans", "receipts"),
        write_scope=(),
        project_scope="any",
        max_autonomy=AutonomyLevel.DRAFT,
        required_approvals=(),
        required_validation=("schema",),
        timeout_seconds=60,
        retry_limit=1,
        cost_limit="LOW",
    )
)

_add(
    _role(
        role_id="PLANNER",
        description="Decomposes an approved goal into inputs, outputs, dependencies, risks, and gates.",
        permitted_tools=_READ_ONLY_TOOLS + ("draft_task_envelope", "create_tournament_plan"),
        prohibited_tools=("run_synthetic_tournament",),
        read_scope=("operational_state", "plans"),
        write_scope=(),
        project_scope="any",
        max_autonomy=AutonomyLevel.DRAFT,
        required_approvals=(),
        required_validation=("schema",),
        timeout_seconds=120,
        retry_limit=1,
        cost_limit="LOW",
    )
)

_add(
    _role(
        role_id="CODE_BUILDER",
        description=(
            "Works on application code inside an authorized worktree. May route to Claude Code or "
            "Codex as a handoff draft; in Alpha it produces the handoff, never the commit."
        ),
        permitted_tools=("draft_task_envelope", "run_registered_test_suite"),
        prohibited_tools=("inspect_registered_workbook_read_only", "run_synthetic_tournament"),
        read_scope=("repository",),
        write_scope=("authorized_worktree",),
        project_scope="repository",
        max_autonomy=AutonomyLevel.BOUNDED_WRITER,
        required_approvals=("task_envelope", "writer_ack"),
        required_validation=("schema", "tests", "code_review"),
        timeout_seconds=1800,
        retry_limit=1,
        cost_limit="MEDIUM",
        is_writer=True,
    )
)

_add(
    _role(
        role_id="CODE_REVIEWER",
        description="Independently reviews code and tests. Never the writer on the same lane.",
        permitted_tools=_READ_ONLY_TOOLS + ("run_registered_test_suite", "draft_review_request"),
        prohibited_tools=("draft_task_envelope",),
        read_scope=("repository",),
        write_scope=(),
        project_scope="repository",
        max_autonomy=AutonomyLevel.READ_ONLY_EXECUTE,
        required_approvals=(),
        required_validation=("schema",),
        timeout_seconds=900,
        retry_limit=1,
        cost_limit="MEDIUM",
    )
)

_add(
    _role(
        role_id="REPORT_READER",
        description="Reads report structures and evidence read-only.",
        permitted_tools=_READ_ONLY_TOOLS,
        prohibited_tools=_MUTATING_TOOLS,
        read_scope=("reports", "evidence"),
        write_scope=(),
        project_scope="any",
        max_autonomy=AutonomyLevel.READ_ONLY_EXECUTE,
        required_approvals=(),
        required_validation=("schema", "evidence_citation"),
        timeout_seconds=300,
        retry_limit=1,
        cost_limit="LOW",
    )
)

_add(
    _role(
        role_id="INDEX_READER",
        description=(
            "Attempts transcription and interpretation of handwritten or scanned index pages. "
            "Distinguishes unreadable from absent and never silently guesses."
        ),
        permitted_tools=("inspect_registered_images_read_only", "get_artifact_metadata", "get_artifact_hash"),
        prohibited_tools=_MUTATING_TOOLS + ("inspect_registered_workbook_read_only",),
        read_scope=("registered_images",),
        write_scope=(),
        project_scope="any",
        max_autonomy=AutonomyLevel.READ_ONLY_EXECUTE,
        required_approvals=(),
        required_validation=("schema", "source_region", "confidence_calibration"),
        timeout_seconds=600,
        retry_limit=1,
        cost_limit="MEDIUM",
    )
)

_add(
    _role(
        role_id="RUNSHEET_RECONCILER",
        description="Compares extracted index entries with Runsheet entries.",
        permitted_tools=("get_artifact_metadata", "compare_artifact_metadata", "read_validation_receipt"),
        prohibited_tools=_MUTATING_TOOLS,
        read_scope=("registered_runsheet", "candidate_outputs"),
        write_scope=(),
        project_scope="any",
        max_autonomy=AutonomyLevel.READ_ONLY_EXECUTE,
        required_approvals=(),
        required_validation=("schema", "evidence_citation"),
        timeout_seconds=600,
        retry_limit=1,
        cost_limit="LOW",
    )
)

_add(
    _role(
        role_id="TITLE_ANALYSIS_ASSISTANT",
        description=(
            "Identifies gaps, inconsistencies, and questions. Issues no final legal conclusion: "
            "examination for a marketability opinion is legal work for a licensed attorney."
        ),
        permitted_tools=_READ_ONLY_TOOLS + ("request_human_review",),
        prohibited_tools=("draft_task_envelope",),
        read_scope=("reconciliation", "evidence"),
        write_scope=(),
        project_scope="any",
        max_autonomy=AutonomyLevel.READ_ONLY_EXECUTE,
        required_approvals=(),
        required_validation=("schema", "human_review_routing"),
        timeout_seconds=600,
        retry_limit=1,
        cost_limit="LOW",
    )
)

_add(
    _role(
        role_id="FORMULA_VALIDATOR",
        description="Deterministic workbook and formula checks. Never routed to a language model.",
        permitted_tools=("inspect_registered_workbook_read_only", "verify_artifact_hash", "read_validation_receipt"),
        prohibited_tools=_MUTATING_TOOLS,
        read_scope=("registered_workbook",),
        write_scope=(),
        project_scope="any",
        max_autonomy=AutonomyLevel.READ_ONLY_EXECUTE,
        required_approvals=(),
        required_validation=("schema", "deterministic"),
        timeout_seconds=300,
        retry_limit=0,
        cost_limit="FREE",
    )
)

_add(
    _role(
        role_id="PAGE_RENDER_REVIEWER",
        description="Checks visual output: blank pages, clipping, scaling, and headers.",
        permitted_tools=("inspect_registered_images_read_only", "get_artifact_metadata"),
        prohibited_tools=_MUTATING_TOOLS,
        read_scope=("rendered_pages",),
        write_scope=(),
        project_scope="any",
        max_autonomy=AutonomyLevel.READ_ONLY_EXECUTE,
        required_approvals=(),
        required_validation=("schema",),
        timeout_seconds=300,
        retry_limit=1,
        cost_limit="LOW",
    )
)

_add(
    _role(
        role_id="SECURITY_REVIEWER",
        description="Reviews permissions, secrets, routes, paths, task scopes, and agent capabilities.",
        permitted_tools=_READ_ONLY_TOOLS + ("run_registered_test_suite",),
        prohibited_tools=("draft_task_envelope", "assign_read_only_agent"),
        read_scope=("repository", "policy", "tool_registry"),
        write_scope=(),
        project_scope="any",
        max_autonomy=AutonomyLevel.READ_ONLY_EXECUTE,
        required_approvals=(),
        required_validation=("schema",),
        timeout_seconds=900,
        retry_limit=1,
        cost_limit="MEDIUM",
    )
)

_add(
    _role(
        role_id="JUDGE",
        description=(
            "Compares candidates against evidence and objective metrics. May not accept a candidate "
            "it generated without independent validation."
        ),
        permitted_tools=("compare_candidate_scores", "read_validation_receipt", "explain_finding"),
        prohibited_tools=("run_synthetic_tournament", "draft_task_envelope"),
        read_scope=("candidate_outputs", "scores", "baseline"),
        write_scope=(),
        project_scope="any",
        max_autonomy=AutonomyLevel.READ_ONLY_EXECUTE,
        required_approvals=(),
        required_validation=("schema", "evidence_citation", "independence"),
        timeout_seconds=300,
        retry_limit=1,
        cost_limit="LOW",
    )
)

_add(
    _role(
        role_id="HUMAN_REVIEW",
        description="Routes uncertain or consequential decisions to the operator or an authorized examiner.",
        permitted_tools=("request_human_review", "explain_finding"),
        prohibited_tools=("draft_task_envelope", "run_synthetic_tournament", "stop_queued_job"),
        read_scope=("everything_the_operator_may_see",),
        write_scope=(),
        project_scope="any",
        max_autonomy=AutonomyLevel.OBSERVE,
        required_approvals=(),
        required_validation=("schema",),
        timeout_seconds=60,
        retry_limit=0,
        cost_limit="FREE",
        self_judgement_prohibited=False,
    )
)


def get_role(role_id: str) -> AgentRole:
    try:
        return ROLES[role_id]
    except KeyError:
        raise AgentNotRegistered(
            f"{role_id!r} is not a registered agent role.",
            detail={"role_id": role_id, "registered": sorted(ROLES)},
        ) from None


def list_roles() -> list[dict]:
    return [ROLES[key].to_dict() for key in sorted(ROLES)]


def sync_roles(store) -> None:
    """Record the role registry in the ledger-backed database."""
    for role in ROLES.values():
        store.execute(
            """
            INSERT OR REPLACE INTO cb_agent_roles (
                role_id, description, max_autonomy, output_schema_hash, registered_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                role.role_id,
                role.description,
                int(role.max_autonomy),
                role.output_schema_hash(),
                store.now(),
            ),
        )
