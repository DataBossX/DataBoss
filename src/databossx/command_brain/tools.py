"""Allowlisted tool registry.

Three properties matter here:

1. **Allowlist only.** An unknown ``tool_id`` is a refusal, never a fallback.
2. **No path, no shell, no credential.** Tools take stable IDs; the server
   resolves those to locators and permissions. A browser (or a model) never
   hands the system a filesystem path or a command line.
3. **A tool cannot widen its own permissions.** The registry is frozen before
   the first invocation, and handlers receive a read-only context with no
   grant/register surface.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

from .autonomy import AutonomyLevel
from .errors import RegistryFrozen, ToolInputRejected, ToolNotRegistered
from .policy import ActionRequest, AuthoritySource, PolicyEngine, RiskLevel
from .redaction import (
    POSIX_PATH_PATTERN,
    SECRET_KEY_PATTERN,
    SECRET_VALUE_PATTERNS,
    UNC_PATH_PATTERN,
    WINDOWS_PATH_PATTERN,
)
from .schemas import validate
from .util import canonical_hash

# Shell metacharacters and command shapes. Present in no legitimate tool input.
SHELL_PATTERNS = (
    re.compile(r"[;|&`]"),
    re.compile(r"\$\("),
    re.compile(r"\$\{"),
    re.compile(r"(^|\s)(rm|del|curl|wget|bash|sh|cmd|powershell|python|node|npm|git|scp|ssh)\s+-?"),
    re.compile(r"[<>]\s*\S"),
    re.compile(r"\n"),
)

TRAVERSAL_PATTERN = re.compile(r"(^|[\\/])\.\.([\\/]|$)")


def _scan_string(value: str, *, key: str, free_text: bool) -> None:
    if TRAVERSAL_PATTERN.search(value):
        raise ToolInputRejected(
            f"Tool input {key!r} contains a path traversal sequence.", detail={"field": key}
        )
    if WINDOWS_PATH_PATTERN.search(value) or UNC_PATH_PATTERN.search(value) or POSIX_PATH_PATTERN.search(value):
        raise ToolInputRejected(
            f"Tool input {key!r} contains a filesystem path. Tools accept stable IDs only; "
            "the server resolves locations.",
            detail={"field": key},
        )
    for pattern in SECRET_VALUE_PATTERNS:
        if pattern.search(value):
            raise ToolInputRejected(
                f"Tool input {key!r} looks like a credential. Tools never accept raw secrets.",
                detail={"field": key},
            )
    if not free_text:
        for pattern in SHELL_PATTERNS:
            if pattern.search(value):
                raise ToolInputRejected(
                    f"Tool input {key!r} contains shell syntax. Tools do not execute commands.",
                    detail={"field": key},
                )


def scan_tool_input(payload, schema: dict | None = None, key: str = "$") -> None:
    """Reject shell, paths, traversal, and credentials anywhere in tool input.

    A property may opt into relaxed shell checking with ``"x_free_text": True``
    in its schema (used by prose fields such as a review question). Path,
    traversal, and credential checks are never relaxed.
    """
    properties = (schema or {}).get("properties", {})
    if isinstance(payload, dict):
        for name, value in payload.items():
            if SECRET_KEY_PATTERN.search(str(name)):
                raise ToolInputRejected(
                    f"Tool input {name!r} is a credential-shaped field.", detail={"field": name}
                )
            scan_tool_input(value, properties.get(name), f"{key}.{name}")
    elif isinstance(payload, (list, tuple)):
        item_schema = (schema or {}).get("items")
        for index, item in enumerate(payload):
            scan_tool_input(item, item_schema, f"{key}[{index}]")
    elif isinstance(payload, str):
        _scan_string(payload, key=key, free_text=bool((schema or {}).get("x_free_text")))


@dataclass(frozen=True)
class ToolDefinition:
    tool_id: str
    description: str
    input_schema: dict
    output_schema: dict
    handler: Callable
    required_level: AutonomyLevel = AutonomyLevel.OBSERVE
    read_only: bool = True
    mutates_state: bool = False
    external_effect: bool = False
    risk: RiskLevel = RiskLevel.INFORMATIONAL
    requires_approval: bool = False

    def __post_init__(self):
        object.__setattr__(self, "required_level", AutonomyLevel.parse(self.required_level))
        object.__setattr__(self, "risk", RiskLevel(self.risk))

    def to_dict(self) -> dict:
        return {
            "tool_id": self.tool_id,
            "description": self.description,
            "required_level": int(self.required_level),
            "required_level_name": self.required_level.name,
            "read_only": self.read_only,
            "mutates_state": self.mutates_state,
            "external_effect": self.external_effect,
            "risk": self.risk.value,
            "requires_approval": self.requires_approval,
            "input_schema_hash": canonical_hash(self.input_schema),
            "output_schema_hash": canonical_hash(self.output_schema),
        }


@dataclass(frozen=True)
class ToolContext:
    """What a handler is allowed to see.

    Deliberately has no registry, no policy engine, and no grant method: a tool
    body has no surface through which to widen its own permissions.
    """

    runtime: object
    project_id: str | None = None
    plan_id: str | None = None
    envelope_id: str | None = None
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ToolResult:
    tool_id: str
    output: dict
    input_hash: str
    output_hash: str
    invocation_id: str


class ToolRegistry:
    def __init__(self, store=None, policy: PolicyEngine | None = None):
        self._tools: dict[str, ToolDefinition] = {}
        self._frozen = False
        self.store = store
        self.policy = policy or PolicyEngine()

    # -- registration -----------------------------------------------------
    def register(self, tool: ToolDefinition) -> ToolDefinition:
        if self._frozen:
            raise RegistryFrozen(
                f"Tool registry is frozen; {tool.tool_id!r} cannot be added at runtime.",
                detail={"tool_id": tool.tool_id},
            )
        if tool.tool_id in self._tools:
            raise RegistryFrozen(
                f"Tool {tool.tool_id!r} is already registered.", detail={"tool_id": tool.tool_id}
            )
        if tool.external_effect:
            raise RegistryFrozen(
                f"Tool {tool.tool_id!r} declares an external effect; Alpha registers no such tool.",
                detail={"tool_id": tool.tool_id},
            )
        self._tools[tool.tool_id] = tool
        return tool

    def freeze(self) -> "ToolRegistry":
        self._frozen = True
        if self.store is not None:
            for tool in self._tools.values():
                record = tool.to_dict()
                self.store.execute(
                    """
                    INSERT OR REPLACE INTO cb_tool_definitions (
                        tool_id, description, required_level, read_only,
                        input_schema_hash, output_schema_hash, registered_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        tool.tool_id,
                        tool.description,
                        int(tool.required_level),
                        int(tool.read_only),
                        record["input_schema_hash"],
                        record["output_schema_hash"],
                        self.store.now(),
                    ),
                )
        return self

    @property
    def frozen(self) -> bool:
        return self._frozen

    # -- lookup -----------------------------------------------------------
    def get(self, tool_id: str) -> ToolDefinition:
        try:
            return self._tools[tool_id]
        except KeyError:
            raise ToolNotRegistered(
                f"{tool_id!r} is not an allowlisted tool.",
                detail={"tool_id": tool_id, "allowlist": sorted(self._tools)},
            ) from None

    def list_tools(self) -> list[dict]:
        return [self._tools[key].to_dict() for key in sorted(self._tools)]

    def tool_ids(self) -> list[str]:
        return sorted(self._tools)

    def __contains__(self, tool_id: str) -> bool:
        return tool_id in self._tools

    # -- invocation -------------------------------------------------------
    def invoke(
        self,
        tool_id: str,
        params: dict | None = None,
        context: ToolContext | None = None,
        *,
        authority_source: AuthoritySource = AuthoritySource.TYPED_UTTERANCE,
        approval_id: str | None = None,
    ) -> ToolResult:
        params = dict(params or {})
        tool = self.get(tool_id)
        input_hash = canonical_hash(params)
        invocation_id = self.store.new_id("inv") if self.store else f"inv_{input_hash[:16]}"

        def _record(status: str, output_hash: str | None, error_code: str | None) -> None:
            if self.store is None:
                return
            self.store.execute(
                """
                INSERT INTO cb_tool_invocations (
                    id, tool_id, plan_id, envelope_id, input_hash, output_hash,
                    status, error_code, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    invocation_id,
                    tool_id,
                    getattr(context, "plan_id", None),
                    getattr(context, "envelope_id", None),
                    input_hash,
                    output_hash,
                    status,
                    error_code,
                    self.store.now(),
                ),
            )
            self.store.audit(
                f"tool.{status.lower()}",
                "tool",
                tool_id,
                {
                    "invocation_id": invocation_id,
                    "input_hash": input_hash,
                    "output_hash": output_hash,
                    "error_code": error_code,
                },
                project_id=getattr(context, "project_id", None),
            )

        try:
            scan_tool_input(params, tool.input_schema)
            validate(params, tool.input_schema, f"${tool_id}.input")
            self.policy.enforce(
                ActionRequest(
                    action_type=f"tool:{tool_id}",
                    required_level=tool.required_level,
                    risk=tool.risk,
                    mutates_state=tool.mutates_state,
                    external_effect=tool.external_effect,
                    authority_source=authority_source,
                    approval_id=approval_id,
                    project_id=getattr(context, "project_id", None),
                    target_ids=tuple(
                        str(value) for value in params.values() if isinstance(value, str)
                    ),
                )
            )
        except Exception as exc:  # noqa: BLE001 - recorded then re-raised
            _record("REJECTED", None, getattr(exc, "code", exc.__class__.__name__))
            raise

        try:
            output = tool.handler(context, params)
        except Exception as exc:  # noqa: BLE001 - recorded then re-raised
            _record("FAILED", None, getattr(exc, "code", exc.__class__.__name__))
            raise

        # A tool's own output is untrusted too: it may have come from a model.
        validate(output, tool.output_schema, f"${tool_id}.output")
        output_hash = canonical_hash(output)
        _record("OK", output_hash, None)
        return ToolResult(
            tool_id=tool_id,
            output=output,
            input_hash=input_hash,
            output_hash=output_hash,
            invocation_id=invocation_id,
        )
