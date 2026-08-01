"""The allowlisted tool set.

Every tool takes stable IDs and returns a schema-validated object. None of them
accepts a path, a command, a locator, or a credential — the server resolves all
of that from the registry.

Two tools are deliberately *not* gated behind approval even though they change
records: ``stop_queued_job`` and ``quarantine_candidate``. Both only ever
restrict what the system may do, and an emergency brake that needs a signature
is not a brake.
"""

from __future__ import annotations

from .autonomy import AutonomyLevel
from .policy import RiskLevel
from .schemas import STABLE_ID_SCHEMA
from .tools import ToolDefinition, ToolRegistry

_NO_INPUT = {"type": "object", "additionalProperties": False, "properties": {}}


def _object(required=(), **properties) -> dict:
    return {
        "type": "object",
        "required": list(required),
        "additionalProperties": True,
        "properties": dict(properties),
    }


def _strict(required=(), **properties) -> dict:
    schema = _object(required, **properties)
    schema["additionalProperties"] = False
    return schema


_OPTIONAL_PROJECT = _strict((), project_id={"anyOf": [STABLE_ID_SCHEMA, {"type": "null"}]})
_ARTIFACT_INPUT = _strict(("artifact_id",), artifact_id=STABLE_ID_SCHEMA)

_LIST_OUTPUT = _object(("items", "observed_at"), items={"type": "array"}, observed_at={"type": "string"})
_FREE_TEXT = {"type": "string", "maxLength": 2000, "x_free_text": True}


def build_registry(runtime, store=None, policy=None) -> ToolRegistry:
    """Construct and freeze the registry for one runtime."""
    registry = ToolRegistry(store=store or runtime.store, policy=policy or runtime.policy)

    def tool(**kwargs):
        registry.register(ToolDefinition(**kwargs))

    # -- status and inventory --------------------------------------------
    tool(
        tool_id="get_system_status",
        description="Current DataBossX operational state, policy profile, and model verification.",
        input_schema=_NO_INPUT,
        output_schema=_object(("observed_at",), observed_at={"type": "string"}),
        handler=lambda ctx, params: runtime.state.system_status(runtime.policy.profile, runtime.gateway),
    )

    tool(
        tool_id="get_project_status",
        description="Status, jobs, defects, holds, approvals, and artifacts for one project.",
        input_schema=_strict(("project_id",), project_id=STABLE_ID_SCHEMA),
        output_schema=_object(("observed_at",), observed_at={"type": "string"}),
        handler=lambda ctx, params: runtime.state.project_status(params["project_id"]),
    )

    tool(
        tool_id="get_active_jobs",
        description="Jobs currently queued or running.",
        input_schema=_OPTIONAL_PROJECT,
        output_schema=_LIST_OUTPUT,
        handler=lambda ctx, params: {
            "items": runtime.state.active_jobs(params.get("project_id")),
            "observed_at": runtime.store.now(),
        },
    )

    tool(
        tool_id="get_open_defects",
        description="Open defects, most severe first.",
        input_schema=_OPTIONAL_PROJECT,
        output_schema=_LIST_OUTPUT,
        handler=lambda ctx, params: {
            "items": runtime.state.open_defects(params.get("project_id")),
            "observed_at": runtime.store.now(),
        },
    )

    tool(
        tool_id="get_pending_approvals",
        description="TaskEnvelope drafts awaiting the operator's approval.",
        input_schema=_NO_INPUT,
        output_schema=_LIST_OUTPUT,
        handler=lambda ctx, params: {
            "items": runtime.state.pending_approvals(),
            "observed_at": runtime.store.now(),
        },
    )

    tool(
        tool_id="get_release_holds",
        description="Active release and workbook holds.",
        input_schema=_OPTIONAL_PROJECT,
        output_schema=_LIST_OUTPUT,
        handler=lambda ctx, params: {
            "items": runtime.state.release_holds(params.get("project_id")),
            "observed_at": runtime.store.now(),
        },
    )

    # -- artifacts --------------------------------------------------------
    tool(
        tool_id="get_artifact_metadata",
        description="Registered artifact metadata. Never returns a filesystem locator.",
        input_schema=_ARTIFACT_INPUT,
        output_schema=_object(("artifact_id", "sha256"), artifact_id={"type": "string"}, sha256={"type": "string"}),
        handler=lambda ctx, params: runtime.state.artifact_metadata(params["artifact_id"]),
    )

    tool(
        tool_id="get_artifact_hash",
        description="Recorded SHA-256 of a registered artifact.",
        input_schema=_ARTIFACT_INPUT,
        output_schema=_strict(("artifact_id", "sha256"), artifact_id={"type": "string"}, sha256={"type": "string"}),
        handler=lambda ctx, params: {
            "artifact_id": params["artifact_id"],
            "sha256": runtime.state.artifact_hash(params["artifact_id"]),
        },
    )

    tool(
        tool_id="verify_artifact_hash",
        description="Recompute an artifact hash from its registered bytes; NOT_VERIFIED if unreachable.",
        input_schema=_ARTIFACT_INPUT,
        output_schema=_object(("artifact_id", "state"), artifact_id={"type": "string"}, state={"type": "string"}),
        required_level=AutonomyLevel.READ_ONLY_EXECUTE,
        handler=lambda ctx, params: runtime.state.verify_artifact_hash(params["artifact_id"]),
    )

    def _compare_metadata(ctx, params):
        left = runtime.state.artifact_metadata(params["artifact_id_a"])
        right = runtime.state.artifact_metadata(params["artifact_id_b"])
        differences = sorted(
            key for key in left if key not in ("artifact_id", "registered_at") and left[key] != right.get(key)
        )
        return {
            "artifact_id_a": left["artifact_id"],
            "artifact_id_b": right["artifact_id"],
            "identical_bytes": left["sha256"] == right["sha256"],
            "differences": differences,
        }

    tool(
        tool_id="compare_artifact_metadata",
        description="Compare two registered artifacts by metadata and content hash.",
        input_schema=_strict(
            ("artifact_id_a", "artifact_id_b"),
            artifact_id_a=STABLE_ID_SCHEMA,
            artifact_id_b=STABLE_ID_SCHEMA,
        ),
        output_schema=_object(("identical_bytes",), identical_bytes={"type": "boolean"}),
        handler=_compare_metadata,
    )

    tool(
        tool_id="read_validation_receipt",
        description="Read one immutable receipt by ID.",
        input_schema=_strict(("receipt_id",), receipt_id=STABLE_ID_SCHEMA),
        output_schema=_object(("receipt_id",), receipt_id={"type": "string"}),
        handler=lambda ctx, params: runtime.read_receipt(params["receipt_id"]),
    )

    # -- read-only inspection --------------------------------------------
    tool(
        tool_id="inspect_registered_workbook_read_only",
        description="Deterministic read-only structural inspection of a registered workbook.",
        input_schema=_ARTIFACT_INPUT,
        output_schema=_object(("artifact_id", "state"), artifact_id={"type": "string"}, state={"type": "string"}),
        required_level=AutonomyLevel.READ_ONLY_EXECUTE,
        handler=lambda ctx, params: runtime.inspect_workbook(params["artifact_id"]),
    )

    tool(
        tool_id="inspect_registered_images_read_only",
        description=(
            "Read-only structural view of a registered index page: rows, regions, and per-cell "
            "legibility. Returns no transcribed values — reading is an agent's job, not a tool's."
        ),
        input_schema=_ARTIFACT_INPUT,
        output_schema=_object(("artifact_id", "rows"), artifact_id={"type": "string"}, rows={"type": "array"}),
        required_level=AutonomyLevel.READ_ONLY_EXECUTE,
        handler=lambda ctx, params: runtime.inspect_index_page(params["artifact_id"]),
    )

    tool(
        tool_id="run_registered_test_suite",
        description="Run one registered test suite by ID. Arbitrary commands are not accepted.",
        input_schema=_strict(("suite_id",), suite_id=STABLE_ID_SCHEMA),
        output_schema=_object(("suite_id", "state"), suite_id={"type": "string"}, state={"type": "string"}),
        required_level=AutonomyLevel.READ_ONLY_EXECUTE,
        handler=lambda ctx, params: runtime.run_test_suite(params["suite_id"]),
    )

    # -- drafting ---------------------------------------------------------
    tool(
        tool_id="draft_task_envelope",
        description="Draft a scoped TaskEnvelope. Drafting never executes anything.",
        input_schema=_strict(
            ("goal",),
            goal=_FREE_TEXT,
            project_id={"anyOf": [STABLE_ID_SCHEMA, {"type": "null"}]},
            autonomy_level={"type": "integer", "minimum": 0, "maximum": 3},
            roles={"type": "array", "items": STABLE_ID_SCHEMA, "maxItems": 12},
            tools={"type": "array", "items": STABLE_ID_SCHEMA, "maxItems": 24},
        ),
        output_schema=_object(("task_id", "envelope_hash"), task_id={"type": "string"}, envelope_hash={"type": "string"}),
        required_level=AutonomyLevel.DRAFT,
        handler=lambda ctx, params: runtime.draft_envelope_tool(ctx, params),
    )

    tool(
        tool_id="draft_review_request",
        description="Draft an independent review request for a named subject.",
        input_schema=_strict(
            ("subject_id", "question"), subject_id=STABLE_ID_SCHEMA, question=_FREE_TEXT
        ),
        output_schema=_object(("subject_id", "question"), subject_id={"type": "string"}, question={"type": "string"}),
        required_level=AutonomyLevel.DRAFT,
        handler=lambda ctx, params: {
            "subject_id": params["subject_id"],
            "question": params["question"],
            "reviewer_role": "CODE_REVIEWER",
            "state": "DRAFT",
            "note": "Draft only. Dispatch requires an approved TaskEnvelope.",
        },
    )

    # -- read-only execution ----------------------------------------------
    tool(
        tool_id="assign_read_only_agent",
        description="Dispatch one registered read-only agent against one registered artifact.",
        input_schema=_strict(
            ("role_id", "model_id", "artifact_id"),
            role_id=STABLE_ID_SCHEMA,
            model_id=STABLE_ID_SCHEMA,
            artifact_id=STABLE_ID_SCHEMA,
        ),
        output_schema=_object(("role_id", "assignment_id"), role_id={"type": "string"}, assignment_id={"type": "string"}),
        required_level=AutonomyLevel.READ_ONLY_EXECUTE,
        risk=RiskLevel.MEDIUM,
        handler=lambda ctx, params: runtime.assign_read_only_agent(ctx, params),
    )

    tool(
        tool_id="create_tournament_plan",
        description="Build a tournament plan: baseline, candidates, judge, and scoring criteria.",
        input_schema=_strict(
            ("question",),
            question=_FREE_TEXT,
            candidate_count={"type": "integer", "minimum": 1, "maximum": 5},
            runsheet_id={"anyOf": [STABLE_ID_SCHEMA, {"type": "null"}]},
            page_ids={"type": "array", "items": STABLE_ID_SCHEMA, "maxItems": 50},
            project_id={"anyOf": [STABLE_ID_SCHEMA, {"type": "null"}]},
        ),
        output_schema=_object(("question", "candidates"), question={"type": "string"}, candidates={"type": "array"}),
        required_level=AutonomyLevel.DRAFT,
        handler=lambda ctx, params: runtime.create_tournament_plan(ctx, params).to_dict(),
    )

    tool(
        tool_id="run_synthetic_tournament",
        description="Run a read-only tournament against the SYNTHETIC corpus and score every candidate.",
        input_schema=_strict(
            ("question",),
            question=_FREE_TEXT,
            candidate_count={"type": "integer", "minimum": 1, "maximum": 5},
            project_id={"anyOf": [STABLE_ID_SCHEMA, {"type": "null"}]},
        ),
        output_schema=_object(
            ("tournament_id", "baseline_preserved"),
            tournament_id={"type": "string"},
            baseline_preserved={"type": "boolean"},
        ),
        required_level=AutonomyLevel.READ_ONLY_EXECUTE,
        risk=RiskLevel.MEDIUM,
        handler=lambda ctx, params: runtime.run_tournament_tool(ctx, params),
    )

    tool(
        tool_id="compare_candidate_scores",
        description="Score comparison for every candidate in one tournament.",
        input_schema=_strict(("tournament_id",), tournament_id=STABLE_ID_SCHEMA),
        output_schema=_object(("tournament_id", "candidates"), tournament_id={"type": "string"}, candidates={"type": "array"}),
        handler=lambda ctx, params: runtime.compare_candidate_scores(params["tournament_id"]),
    )

    # -- protective controls ----------------------------------------------
    # These change records but only ever restrict. They stay at low autonomy on
    # purpose: an operator must always be able to stop and quarantine.
    tool(
        tool_id="quarantine_candidate",
        description="Quarantine a candidate or artifact so it can never be accepted.",
        input_schema=_strict(
            ("subject_id", "reason"), subject_id=STABLE_ID_SCHEMA, reason=_FREE_TEXT
        ),
        output_schema=_strict(
            ("subject_id", "quarantined"), subject_id={"type": "string"}, quarantined={"type": "boolean"},
            quarantine_id={"type": "string"},
        ),
        required_level=AutonomyLevel.DRAFT,
        risk=RiskLevel.LOW,
        handler=lambda ctx, params: {
            "subject_id": params["subject_id"],
            "quarantined": True,
            "quarantine_id": runtime.store.quarantine(
                "candidate", params["subject_id"], params["reason"]
            ),
        },
    )

    tool(
        tool_id="request_human_review",
        description="Route a decision to the operator or an authorized examiner.",
        input_schema=_strict(
            ("subject_id", "question"), subject_id=STABLE_ID_SCHEMA, question=_FREE_TEXT
        ),
        output_schema=_strict(("item_id", "state"), item_id={"type": "string"}, state={"type": "string"}),
        handler=lambda ctx, params: {
            "item_id": runtime.store.queue_human_review(
                "operator_request",
                params["subject_id"],
                params["question"],
                project_id=getattr(ctx, "project_id", None),
            ),
            "state": "OPEN",
        },
    )

    tool(
        tool_id="explain_finding",
        description="Plain-language explanation of a finding, receipt, or tournament result.",
        input_schema=_strict(
            ("subject_id",),
            subject_id=STABLE_ID_SCHEMA,
            format={"type": "string", "enum": ["standard", "phone"]},
            verbosity={"type": "string", "enum": ["concise", "standard", "detailed"]},
        ),
        output_schema=_object(("subject_id", "explanation"), subject_id={"type": "string"}, explanation={"type": "string"}),
        handler=lambda ctx, params: runtime.explain(
            params["subject_id"], params.get("format", "standard"), params.get("verbosity", "standard")
        ),
    )

    tool(
        tool_id="stop_queued_job",
        description="Request a stop on one queued or running job. Always available.",
        input_schema=_strict(("job_id",), job_id=STABLE_ID_SCHEMA),
        output_schema=_strict(("job_id", "state"), job_id={"type": "string"}, state={"type": "string"}),
        handler=lambda ctx, params: runtime.stop_job(params["job_id"]),
    )

    return registry.freeze()
