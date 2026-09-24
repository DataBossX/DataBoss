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
from .loopback_http import HttpResult, LoopbackClient, LoopbackHttpError
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
_SHOW_KEEP_KEYS = (
    "capabilities",
    "details",
    "modified_at",
    *_THINKING_VALUE_KEYS,
    *_THINKING_DEFAULT_KEYS,
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


def _response_error(response: HttpResult, fallback: str) -> str:
    return response.error if response.error is not UNKNOWN else fallback


def _fail(result: dict[str, Any], error: str) -> dict[str, Any]:
    result["errors"].append(error)
    return redact(result)


def _kept_show_fields(payload: dict[str, Any]) -> dict[str, Any]:
    kept = {key: payload[key] for key in _SHOW_KEEP_KEYS if key in payload}
    parameters = payload.get("parameters")
    if isinstance(parameters, dict):
        kept["parameters"] = parameters
    return kept


def _blank_model(item: Any, identity: Any) -> dict[str, Any]:
    details = item.get("details", UNKNOWN) if isinstance(item, dict) else UNKNOWN
    digest = item.get("digest", UNKNOWN) if isinstance(item, dict) else UNKNOWN
    return {
        "name": identity,
        "digest": digest,
        "details": details,
        "show": UNKNOWN,
        "thinking": thinking_from_show(None),
        "errors": [],
    }


def _inventory_model(
    http: LoopbackClient,
    host: str,
    port: int,
    item: Any,
) -> tuple[dict[str, Any], bool]:
    identity = _model_identity(item)
    entry = _blank_model(item, identity)
    if identity is UNKNOWN:
        entry["errors"].append("model_identity_absent")
        return entry, True
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
        return entry, True
    if not show.ok or not isinstance(show.json_body, dict):
        entry["errors"].append(_response_error(show, "show_unreadable"))
        return entry, True
    # Record supplied capability fields only. Do not keep license text
    # or templates that can be large or sensitive.
    entry["show"] = _kept_show_fields(show.json_body)
    entry["thinking"] = thinking_from_show(show.json_body)
    return entry, False


def _read_json(http: LoopbackClient, host: str, port: int, path: str) -> HttpResult:
    return http.request("GET", host, port, path, allowed=OLLAMA_ALLOWED_PATHS)


def probe_ollama(
    *,
    host: str = LOOPBACK_HOST,
    port: int = OLLAMA_PORT,
    client: Optional[LoopbackClient] = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema_id": "databossx.rd.ollama_inventory",
        "schema_version": "1.0",
        "read_only": True,
        "host": host,
        "port": port,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "verdict": "fail",
        "ollama_version": UNKNOWN,
        "models": [],
        "errors": [],
        "unknowns": ["ollama_version", "models"],
        "downloads_attempted": False,
        "cloud_calls_attempted": False,
    }
    if host != LOOPBACK_HOST:
        return _fail(result, f"non_loopback_host:{host}")

    http = client or LoopbackClient()
    try:
        version = _read_json(http, host, port, "/api/version")
    except LoopbackHttpError as exc:
        return _fail(result, str(exc))
    if not version.ok or not isinstance(version.json_body, dict):
        return _fail(result, _response_error(version, "version_unreadable"))

    ollama_version = version.json_body.get("version", UNKNOWN)
    result["ollama_version"] = ollama_version if ollama_version else UNKNOWN
    if result["ollama_version"] is UNKNOWN:
        return _fail(result, "ollama_version_unknown")
    result["unknowns"].remove("ollama_version")

    try:
        tags = _read_json(http, host, port, "/api/tags")
    except LoopbackHttpError as exc:
        return _fail(result, str(exc))
    if not tags.ok or not isinstance(tags.json_body, dict):
        return _fail(result, _response_error(tags, "tags_unreadable"))

    raw_models = tags.json_body.get("models", UNKNOWN)
    if raw_models is UNKNOWN or raw_models is None:
        return _fail(result, "models_field_absent")
    if not isinstance(raw_models, list):
        return _fail(result, "models_field_unusable")

    result["unknowns"].remove("models")
    models: list[dict[str, Any]] = []
    show_failures = 0
    for item in raw_models:
        entry, failed = _inventory_model(http, host, port, item)
        models.append(entry)
        show_failures += int(failed)

    result["models"] = models
    if show_failures:
        return _fail(result, f"show_incomplete:{show_failures}")

    result["verdict"] = "pass"
    return redact(result)
