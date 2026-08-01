"""Agent dispatcher.

Routes one bounded unit of work to one registered role running on one registered
model. Everything the dispatcher does is gated in this order, and a failure at
any step is recorded before it is raised:

    role registered → tool/role compatibility → policy → writer authority
    (envelope, approval, lease, fencing token) → model available → invoke
    → schema-validate output → receipt

Writer authority is not a flag. A role marked ``is_writer`` cannot run without an
approved BOUNDED_WRITER envelope, a live single-writer lease on its lane, and a
current fencing token — and two writers can never hold the same lane.
"""

from __future__ import annotations

from dataclasses import dataclass

from .autonomy import AutonomyLevel
from .envelope import TaskEnvelope
from .errors import AuthorityError, CommandBrainError
from .leases import Lease, LeaseManager
from .model_gateway import Modality, ModelGateway, ModelRequest
from .policy import ActionRequest, AuthoritySource, PolicyEngine, RiskLevel
from .roles import AgentRole, get_role
from .schemas import HANDOFF_SCHEMA, validate
from .util import canonical_hash


@dataclass(frozen=True)
class AgentResult:
    assignment_id: str
    role_id: str
    model_id: str
    output: dict
    output_hash: str
    simulated: bool
    verification_state: str
    receipt_id: str | None = None

    def to_dict(self) -> dict:
        return {
            "assignment_id": self.assignment_id,
            "role_id": self.role_id,
            "model_id": self.model_id,
            "output": self.output,
            "output_hash": self.output_hash,
            "simulated": self.simulated,
            "verification_state": self.verification_state,
            "receipt_id": self.receipt_id,
        }


class AgentDispatcher:
    def __init__(
        self,
        store,
        gateway: ModelGateway,
        policy: PolicyEngine,
        leases: LeaseManager,
        approvals=None,
    ):
        self.store = store
        self.gateway = gateway
        self.policy = policy
        self.leases = leases
        self.approvals = approvals

    # -- authority --------------------------------------------------------
    def _check_writer_authority(
        self,
        role: AgentRole,
        envelope: TaskEnvelope | None,
        approval_id: str | None,
        lease: Lease | None,
    ) -> None:
        if not role.is_writer:
            return
        if envelope is None:
            raise AuthorityError(
                f"Role {role.role_id} is a writer; a scoped TaskEnvelope is required.",
                detail={"role_id": role.role_id},
            )
        if envelope.autonomy_level < AutonomyLevel.BOUNDED_WRITER:
            raise AuthorityError(
                "Writer execution requires a BOUNDED_WRITER envelope.",
                detail={"role_id": role.role_id, "envelope_level": int(envelope.autonomy_level)},
            )
        if approval_id is None:
            raise AuthorityError(
                "Writer execution requires an accepted approval bound to this envelope hash.",
                detail={"envelope_id": envelope.task_id},
            )
        if self.approvals is None:
            raise AuthorityError(
                "No approval service is configured; writer execution cannot be authorized.",
                detail={"envelope_id": envelope.task_id},
            )
        self.approvals.verify(approval_id, envelope)
        if lease is None:
            raise AuthorityError(
                "Writer execution requires a single-writer lease and a current fencing token.",
                detail={"envelope_id": envelope.task_id},
            )
        self.leases.validate(lease)

    # -- dispatch ---------------------------------------------------------
    def dispatch(
        self,
        role_id: str,
        model_id: str,
        payload: dict,
        *,
        capability: str = "analyse",
        modality: Modality = Modality.TEXT,
        envelope: TaskEnvelope | None = None,
        approval_id: str | None = None,
        lease: Lease | None = None,
        job_id: str | None = None,
        project_class: str = "synthetic",
        authority_source: AuthoritySource = AuthoritySource.TYPED_UTTERANCE,
    ) -> AgentResult:
        role = get_role(role_id)
        assignment_id = self.store.new_id("asg")
        lane_id = lease.lane_id if lease else None

        def _record(status: str, output_hash: str | None, error_code: str | None) -> None:
            self.store.execute(
                """
                INSERT INTO cb_agent_assignments (
                    id, job_id, envelope_id, role_id, model_id, lane_id, status,
                    output_hash, error_code, created_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    assignment_id,
                    job_id,
                    envelope.task_id if envelope else None,
                    role_id,
                    model_id,
                    lane_id,
                    status,
                    output_hash,
                    error_code,
                    self.store.now(),
                    self.store.now(),
                ),
            )
            self.store.audit(
                f"agent.{status.lower()}",
                "agent_assignment",
                assignment_id,
                {
                    "role_id": role_id,
                    "model_id": model_id,
                    "lane_id": lane_id,
                    "output_hash": output_hash,
                    "error_code": error_code,
                },
                actor_type="agent",
                actor_id=role_id,
            )

        try:
            required_level = min(role.max_autonomy, AutonomyLevel.BOUNDED_WRITER if role.is_writer else role.max_autonomy)
            self.policy.enforce(
                ActionRequest(
                    action_type=f"agent:{role_id}",
                    required_level=required_level,
                    risk=RiskLevel.HIGH if role.is_writer else RiskLevel.LOW,
                    mutates_state=role.is_writer,
                    authority_source=authority_source,
                    approval_id=approval_id,
                    remote_model=not self.gateway.get(model_id).descriptor.is_local,
                )
            )
            self._check_writer_authority(role, envelope, approval_id, lease)
        except CommandBrainError as exc:
            _record("REJECTED", None, exc.code)
            raise

        request = ModelRequest(capability=capability, payload=payload, modality=modality)
        try:
            response = self.gateway.invoke(
                model_id, request, self.policy.profile, project_class=project_class
            )
        except CommandBrainError as exc:
            _record("FAILED", None, exc.code)
            raise

        try:
            validate(response.output, role.output_schema, f"$agent.{role_id}.output")
        except CommandBrainError as exc:
            _record("REJECTED", canonical_hash(response.output), exc.code)
            raise

        receipt_id = None
        if role.receipt_required:
            receipt = self.store.write_receipt(
                "agent_assignment",
                assignment_id,
                {
                    "role_id": role_id,
                    "model_id": model_id,
                    "capability": capability,
                    "simulated": response.simulated,
                    "verification_state": response.verification_state.value,
                    "input_hash": response.input_hash,
                    "output_hash": response.output_hash,
                    "envelope_id": envelope.task_id if envelope else None,
                    "envelope_hash": envelope.envelope_hash if envelope else None,
                    "approval_id": approval_id,
                    "fencing_token": lease.fencing_token if lease else None,
                    "validation_gates": list(role.required_validation),
                },
                project_id=envelope.project_id if envelope else None,
            )
            receipt_id = receipt["receipt_id"]

        _record("SUCCEEDED", response.output_hash, None)
        return AgentResult(
            assignment_id=assignment_id,
            role_id=role_id,
            model_id=model_id,
            output=response.output,
            output_hash=response.output_hash,
            simulated=response.simulated,
            verification_state=response.verification_state.value,
            receipt_id=receipt_id,
        )


def build_code_handoff(
    *,
    repository: str,
    branch: str,
    worktree: str,
    scope: str,
    allowed_files: list,
    prohibited_files: list,
    tests: list,
    acceptance_criteria: list,
    authority_status: str = "AWAITING_AUTHORIZATION",
    final_sentinel: str = "DATABOSSX_COMMAND_BRAIN_AWAITING_AUTHORIZATION",
) -> dict:
    """Structured handoff package for an external coding agent.

    Producing this is not the same as running it. The package always states its
    own authority status so the receiving agent cannot assume it was authorized.
    """
    payload = {
        "repository": repository,
        "branch": branch,
        "worktree": worktree,
        "scope": scope,
        "allowed_files": list(allowed_files),
        "prohibited_files": list(prohibited_files),
        "tests": list(tests),
        "acceptance_criteria": list(acceptance_criteria),
        "authority_status": authority_status,
        "final_sentinel": final_sentinel,
    }
    validate(payload, HANDOFF_SCHEMA, "$handoff")
    return payload
