"""Structured-output contracts and a stdlib schema validator.

Model output is untrusted input. Every agent result, tool input, tool output,
and judge decision is validated here before it is allowed to influence state.
The validator is a deliberately small subset of JSON Schema so it has no
third-party dependency and no surprising coercion behaviour.
"""

from __future__ import annotations

import re

from .errors import SchemaViolation

_TYPES = {
    "object": dict,
    "array": list,
    "string": str,
    "boolean": bool,
    "null": type(None),
}


def _type_ok(value, expected: str) -> bool:
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    python_type = _TYPES.get(expected)
    if python_type is None:
        raise SchemaViolation(f"Unsupported schema type: {expected}")
    if python_type is str and isinstance(value, bool):
        return False
    return isinstance(value, python_type)


def validate(instance, schema: dict, path: str = "$") -> None:
    """Validate ``instance`` against ``schema``; raise :class:`SchemaViolation`."""

    if "const" in schema and instance != schema["const"]:
        raise SchemaViolation(
            f"{path}: expected constant {schema['const']!r}", detail={"path": path}
        )

    if "anyOf" in schema:
        errors = []
        for index, option in enumerate(schema["anyOf"]):
            try:
                validate(instance, option, path)
                break
            except SchemaViolation as exc:
                errors.append(f"[{index}] {exc.message}")
        else:
            raise SchemaViolation(
                f"{path}: matched none of the allowed shapes ({'; '.join(errors)})",
                detail={"path": path},
            )

    expected = schema.get("type")
    if expected is not None:
        options = expected if isinstance(expected, list) else [expected]
        if not any(_type_ok(instance, option) for option in options):
            raise SchemaViolation(
                f"{path}: expected type {'/'.join(options)}, got {type(instance).__name__}",
                detail={"path": path},
            )

    if "enum" in schema and instance not in schema["enum"]:
        raise SchemaViolation(
            f"{path}: {instance!r} is not one of {schema['enum']}", detail={"path": path}
        )

    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            raise SchemaViolation(f"{path}: shorter than {schema['minLength']}", detail={"path": path})
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            raise SchemaViolation(f"{path}: longer than {schema['maxLength']}", detail={"path": path})
        pattern = schema.get("pattern")
        if pattern and not re.match(pattern, instance):
            raise SchemaViolation(f"{path}: does not match {pattern}", detail={"path": path})

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            raise SchemaViolation(f"{path}: below minimum {schema['minimum']}", detail={"path": path})
        if "maximum" in schema and instance > schema["maximum"]:
            raise SchemaViolation(f"{path}: above maximum {schema['maximum']}", detail={"path": path})

    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            raise SchemaViolation(f"{path}: fewer than {schema['minItems']} items", detail={"path": path})
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            raise SchemaViolation(f"{path}: more than {schema['maxItems']} items", detail={"path": path})
        item_schema = schema.get("items")
        if item_schema:
            for index, item in enumerate(instance):
                validate(item, item_schema, f"{path}[{index}]")

    if isinstance(instance, dict):
        for key in schema.get("required", []):
            if key not in instance:
                raise SchemaViolation(f"{path}: missing required property {key!r}", detail={"path": path})
        properties = schema.get("properties", {})
        for key, value in instance.items():
            if key in properties:
                validate(value, properties[key], f"{path}.{key}")
            elif schema.get("additionalProperties", True) is False:
                raise SchemaViolation(
                    f"{path}: unexpected property {key!r}", detail={"path": path, "property": key}
                )


def is_valid(instance, schema: dict) -> bool:
    try:
        validate(instance, schema)
    except SchemaViolation:
        return False
    return True


# --------------------------------------------------------------------------
# Shared primitives
# --------------------------------------------------------------------------

# Every server-facing identifier. Deliberately excludes "/", "\", spaces, and
# shell metacharacters so a path or command can never be smuggled in as an ID.
STABLE_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"

STABLE_ID_SCHEMA = {"type": "string", "pattern": STABLE_ID_PATTERN}

# Value states. "unreadable" and "absent" are distinct on purpose: a field the
# reader could not decipher is not the same as a field the page does not have.
VALUE_STATE = ["known", "uncertain", "unreadable", "absent", "not_applicable"]

SOURCE_REGION_SCHEMA = {
    "type": "object",
    "required": ["page_id", "region"],
    "properties": {
        "page_id": STABLE_ID_SCHEMA,
        "region": {
            "type": "object",
            "required": ["x", "y", "width", "height"],
            "properties": {
                "x": {"type": "number", "minimum": 0},
                "y": {"type": "number", "minimum": 0},
                "width": {"type": "number", "minimum": 0},
                "height": {"type": "number", "minimum": 0},
            },
        },
        "row": {"type": ["integer", "null"]},
    },
}

FIELD_SCHEMA = {
    "type": "object",
    "required": ["value", "state", "confidence"],
    "additionalProperties": False,
    "properties": {
        "value": {"type": ["string", "null"], "maxLength": 512},
        "state": {"type": "string", "enum": VALUE_STATE},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "alternatives": {
            "type": "array",
            "maxItems": 8,
            "items": {"type": "string", "maxLength": 512},
        },
        "source_region": {"anyOf": [SOURCE_REGION_SCHEMA, {"type": "null"}]},
    },
}

INDEX_ENTRY_FIELDS = (
    "grantor",
    "grantee",
    "instrument_type",
    "recording_date",
    "execution_date",
    "book",
    "page",
    "document_number",
    "legal_description",
    "section",
    "township",
    "range",
    "county",
    "state",
    "interest_or_burden",
)

INDEX_ENTRY_SCHEMA = {
    "type": "object",
    "required": ["index_entry_id", "page_id", "row", "fields"],
    "additionalProperties": False,
    "properties": {
        "index_entry_id": STABLE_ID_SCHEMA,
        "page_id": STABLE_ID_SCHEMA,
        "row": {"type": "integer", "minimum": 0},
        "notes": {"type": "string", "maxLength": 1024},
        "fields": {
            "type": "object",
            "required": list(INDEX_ENTRY_FIELDS),
            "additionalProperties": False,
            "properties": {name: FIELD_SCHEMA for name in INDEX_ENTRY_FIELDS},
        },
    },
}

CANDIDATE_OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["candidate_id", "agent_role", "model_id", "entries"],
    "additionalProperties": False,
    "properties": {
        "candidate_id": STABLE_ID_SCHEMA,
        "agent_role": STABLE_ID_SCHEMA,
        "model_id": STABLE_ID_SCHEMA,
        "simulated": {"type": "boolean"},
        "reasoning_summary": {"type": "string", "maxLength": 2000},
        "entries": {"type": "array", "maxItems": 500, "items": INDEX_ENTRY_SCHEMA},
    },
}

RECONCILIATION_CATEGORIES = [
    "exact_match",
    "normalized_match",
    "probable_match",
    "index_only",
    "runsheet_only",
    "conflicting_parties",
    "conflicting_recording_reference",
    "conflicting_legal_description",
    "conflicting_dates",
    "unreadable_source_field",
    "possible_duplicate",
    "uncertain_chain_link",
]

RECONCILIATION_ROW_SCHEMA = {
    "type": "object",
    "required": ["category", "index_entry_id", "runsheet_entry_id", "evidence"],
    "additionalProperties": False,
    "properties": {
        "category": {"type": "string", "enum": RECONCILIATION_CATEGORIES},
        "index_entry_id": {"anyOf": [STABLE_ID_SCHEMA, {"type": "null"}]},
        "runsheet_entry_id": {"anyOf": [STABLE_ID_SCHEMA, {"type": "null"}]},
        "field": {"type": ["string", "null"]},
        "index_value": {"type": ["string", "null"], "maxLength": 512},
        "runsheet_value": {"type": ["string", "null"], "maxLength": 512},
        "evidence": {"type": "string", "maxLength": 1024},
        "requires_human_review": {"type": "boolean"},
    },
}

RECONCILIATION_SCHEMA = {
    "type": "object",
    "required": ["rows"],
    "additionalProperties": False,
    "properties": {
        "rows": {"type": "array", "maxItems": 2000, "items": RECONCILIATION_ROW_SCHEMA},
    },
}

JUDGE_DECISION_SCHEMA = {
    "type": "object",
    "required": ["decision", "rationale", "evidence_refs", "blocking_regressions"],
    "additionalProperties": False,
    "properties": {
        "decision": {"type": "string", "enum": ["ACCEPT", "REJECT", "QUARANTINE", "HUMAN_REVIEW"]},
        "rationale": {"type": "string", "minLength": 1, "maxLength": 2000},
        "evidence_refs": {"type": "array", "minItems": 1, "items": {"type": "string", "maxLength": 512}},
        "blocking_regressions": {"type": "array", "items": {"type": "string", "maxLength": 512}},
    },
}

STATUS_ANSWER_SCHEMA = {
    "type": "object",
    "required": ["summary", "facts"],
    "additionalProperties": False,
    "properties": {
        "summary": {"type": "string", "maxLength": 4000},
        "facts": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["statement", "source", "observed_at"],
                "properties": {
                    "statement": {"type": "string", "maxLength": 1000},
                    "source": {"type": "string", "maxLength": 256},
                    "observed_at": {"type": "string", "maxLength": 64},
                },
            },
        },
    },
}

REVIEW_OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["verdict", "findings"],
    "additionalProperties": False,
    "properties": {
        "verdict": {"type": "string", "enum": ["PASS", "CONCERNS", "FAIL", "NOT_VERIFIED"]},
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["severity", "summary"],
                "properties": {
                    "severity": {"type": "string", "enum": ["INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL"]},
                    "summary": {"type": "string", "maxLength": 1000},
                    "evidence": {"type": "string", "maxLength": 1000},
                },
            },
        },
    },
}

HANDOFF_SCHEMA = {
    "type": "object",
    "required": [
        "repository",
        "branch",
        "worktree",
        "scope",
        "allowed_files",
        "prohibited_files",
        "tests",
        "acceptance_criteria",
        "authority_status",
        "final_sentinel",
    ],
    "additionalProperties": False,
    "properties": {
        "repository": {"type": "string", "maxLength": 256},
        "branch": {"type": "string", "maxLength": 256},
        "worktree": {"type": "string", "maxLength": 512},
        "scope": {"type": "string", "maxLength": 2000},
        "allowed_files": {"type": "array", "items": {"type": "string", "maxLength": 512}},
        "prohibited_files": {"type": "array", "items": {"type": "string", "maxLength": 512}},
        "tests": {"type": "array", "items": {"type": "string", "maxLength": 512}},
        "acceptance_criteria": {"type": "array", "items": {"type": "string", "maxLength": 512}},
        "authority_status": {
            "type": "string",
            "enum": ["AUTHORIZED", "AWAITING_AUTHORIZATION", "DRAFT_ONLY"],
        },
        "final_sentinel": {"type": "string", "maxLength": 128},
    },
}

#: Role ID -> output contract. A role with no entry here may not be dispatched.
AGENT_OUTPUT_SCHEMAS = {
    "INDEX_READER": CANDIDATE_OUTPUT_SCHEMA,
    "RUNSHEET_RECONCILER": RECONCILIATION_SCHEMA,
    "JUDGE": JUDGE_DECISION_SCHEMA,
    "COMMANDER": STATUS_ANSWER_SCHEMA,
    "PLANNER": STATUS_ANSWER_SCHEMA,
    "REPORT_READER": STATUS_ANSWER_SCHEMA,
    "TITLE_ANALYSIS_ASSISTANT": REVIEW_OUTPUT_SCHEMA,
    "FORMULA_VALIDATOR": REVIEW_OUTPUT_SCHEMA,
    "PAGE_RENDER_REVIEWER": REVIEW_OUTPUT_SCHEMA,
    "SECURITY_REVIEWER": REVIEW_OUTPUT_SCHEMA,
    "CODE_REVIEWER": REVIEW_OUTPUT_SCHEMA,
    "CODE_BUILDER": HANDOFF_SCHEMA,
    "HUMAN_REVIEW": {
        "type": "object",
        "required": ["queued", "question"],
        "additionalProperties": False,
        "properties": {
            "queued": {"type": "boolean"},
            "question": {"type": "string", "maxLength": 2000},
            "context_refs": {"type": "array", "items": {"type": "string", "maxLength": 512}},
        },
    },
}
