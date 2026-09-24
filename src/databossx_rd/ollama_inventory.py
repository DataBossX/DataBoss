"""Read-only inventory of a loopback Ollama instance.

Never downloads models, never infers capabilities from model names, and never
calls a non-127.0.0.1 host.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from .constants import (
    LOOPBACK_HOST,
    OLLAMA_ALLOWED_PATHS,
    OLLAMA_PORT,
    UNKNOWN,
)
from .loopback_http import LoopbackClient, LoopbackHttpError
from .redact import redact

_THINKING_VALUE_KEYS = (
    "supported_thinking_values",
    "thinking_values",
    "think_values",
    "think_levels",
    "supported_think_values",
)
_THINKING_DEFAULT_KEYS = (
    "default_thinking",
    "default_think",
    "think_default",
    "thinking_default",
)


def _lookup_supplied(payload: Any, names: tuple[str, ...]) -> Any:
    if not isinstance(payload, dict):
        return UNKNOWN
    buckets: list[dict[str, Any]] = [payload]
    for nest in ("details", "model_info", "parameters"):
        value = payload.get(nest)
        if isinstance(value, dict):
            buckets.append(value)
    for bucket in buckets:
        for name in names:
            if name in bucket:
                return bucket[name]
    return UNKNOWN


def thinking_from_show(show_payload: Any) -> dict[str, Any]:
    """Record thinking fields only when /api/show supplied them."""
    record = {
        "capabilities": UNKNOWN,
        "thinking_listed_in_capabilities": UNKNOWN,
        "supported_thinking_values": UNKNOWN,
        "default_thinking": UNKNOWN,
        "evidence": "absent",
    }
    if not isinstance(show_payload, dict):
        return record
    if "capabilities" not in show_payload:
        record["evidence"] = "show_without_capabilities"
    else:
        caps = show_payload["capabilities"]
        if isinstance(caps, list) and all(isinstance(item, str) for item in caps):
            record["capabilities"] = list(caps)
            record["thinking_listed_in_capabilities"] = any(
                item.lower() == "thinking" for item in caps
            )
            record["evidence"] = "capabilities_field"
        else:
            record["evidence"] = "capabilities_unusable"
    supplied_values = _lookup_supplied(show_payload, _THINKING_VALUE_KEYS)
    supplied_default = _lookup_supplied(show_payload, _THINKING_DEFAULT_KEYS)
    if supplied_values is not UNKNOWN:
        record["supported_thinking_values"] = supplied_values
        record["evidence"] = "supplied_thinking_fields"
    if supplied_default is not UNKNOWN:
        record["default_thinking"] = supplied_default
        record["evidence"] = "supplied_thinking_fields"
    return record


def _model_identity(item: Any) -> Any:
    if not isinstance(item, dict):
        return UNKNOWN
    for key in ("model", "name"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return UNKNOWN


def probe_ollama(
    *,
    host: str = LOOPBACK_HOST,
    port: int = OLLAMA_PORT,
    client: Optional[LoopbackClient] = None,
) -> dict[str, Any]:
    observed_at = datetime.now(timezone.utc).isoformat()
    result: dict[str, Any] = {
        "schema_id": "databossx.rd.ollama_inventory",
        "schema_version": "1.0",
        "read_only": True,
        "host": host,
        "port": port,
        "observed_at": observed_at,
        "verdict": "fail",
        "ollama_version": UNKNOWN,
        "models": [],
        "errors": [],
        "unknowns": ["ollama_version", "models"],
        "downloads_attempted": False,
        "cloud_calls_attempted": False,
    }
    if host != LOOPBACK_HOST:
        result["errors"].append(f"non_loopback_host:{host}")
        return redact(result)

    http = client or LoopbackClient()
    try:
        version = http.request(
            "GET", host, port, "/api/version", allowed=OLLAMA_ALLOWED_PATHS
        )
    except LoopbackHttpError as exc:
        result["errors"].append(str(exc))
        return redact(result)

    if not version.ok or not isinstance(version.json_body, dict):
        result["errors"].append(version.error if version.error is not UNKNOWN else "version_unreadable")
        return redact(result)

    ollama_version = version.json_body.get("version", UNKNOWN)
    result["ollama_version"] = ollama_version if ollama_version else UNKNOWN
    if result["ollama_version"] is UNKNOWN:
        result["errors"].append("ollama_version_unknown")
        return redact(result)
    result["unknowns"].remove("ollama_version")

    try:
        tags = http.request(
            "GET", host, port, "/api/tags", allowed=OLLAMA_ALLOWED_PATHS
        )
    except LoopbackHttpError as exc:
        result["errors"].append(str(exc))
        return redact(result)

    if not tags.ok or not isinstance(tags.json_body, dict):
        result["errors"].append(tags.error if tags.error is not UNKNOWN else "tags_unreadable")
        return redact(result)

    raw_models = tags.json_body.get("models", UNKNOWN)
    if raw_models is UNKNOWN or raw_models is None:
        result["errors"].append("models_field_absent")
        return redact(result)
    if not isinstance(raw_models, list):
        result["errors"].append("models_field_unusable")
        return redact(result)

    result["unknowns"].remove("models")
    models: list[dict[str, Any]] = []
    show_failures = 0
    for item in raw_models:
        identity = _model_identity(item)
        entry = {
            "name": identity,
            "digest": item.get("digest", UNKNOWN) if isinstance(item, dict) else UNKNOWN,
            "details": item.get("details", UNKNOWN) if isinstance(item, dict) else UNKNOWN,
            "show": UNKNOWN,
            "thinking": thinking_from_show(None),
            "errors": [],
        }
        if identity is UNKNOWN:
            entry["errors"].append("model_identity_absent")
            show_failures += 1
            models.append(entry)
            continue
        try:
            show = http.request(
                "POST",
                host,
                port,
                "/api/show",
                allowed=OLLAMA_ALLOWED_PATHS,
                body={"model": identity},
            )
        except LoopbackHttpError as exc:
            entry["errors"].append(str(exc))
            show_failures += 1
            models.append(entry)
            continue
        if not show.ok or not isinstance(show.json_body, dict):
            entry["errors"].append(
                show.error if show.error is not UNKNOWN else "show_unreadable"
            )
            show_failures += 1
            models.append(entry)
            continue
        # Record supplied capability fields only. Do not keep license text
        # or templates that can be large or sensitive.
        show_keep = {
            key: show.json_body[key]
            for key in (
                "capabilities",
                "details",
                "modified_at",
                "supported_thinking_values",
                "thinking_values",
                "think_values",
                "think_levels",
                "supported_think_values",
                "default_thinking",
                "default_think",
                "think_default",
                "thinking_default",
            )
            if key in show.json_body
        }
        if isinstance(show.json_body.get("parameters"), dict):
            show_keep["parameters"] = show.json_body["parameters"]
        entry["show"] = show_keep
        entry["thinking"] = thinking_from_show(show.json_body)
        models.append(entry)

    result["models"] = models
    if show_failures:
        result["errors"].append(f"show_incomplete:{show_failures}")
        return redact(result)

    result["verdict"] = "pass"
    return redact(result)
