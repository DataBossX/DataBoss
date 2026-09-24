"""Read-only n8n version and observable agent-safety guard.

Never edits n8n configuration or workflows. Never upgrades n8n.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .constants import (
    LOOPBACK_HOST,
    MANIFEST_ROOT,
    N8N_AGENTS_REVIEW_MINOR,
    N8N_ALLOWED_PATHS,
    N8N_MIN_STABLE,
    N8N_MIN_STABLE_LABEL,
    N8N_OBSERVABLE_ENV_KEYS,
    N8N_PORT,
    N8N_PRERELEASE_ALLOWLIST_ENV,
    UNKNOWN,
)
from .loopback_http import LoopbackClient, LoopbackHttpError
from .redact import is_secret_key, redact

_PRERELEASE_TOKEN_RE = re.compile(
    r"(alpha|beta|rc|nightly|dev|next|canary|pre|preview|snapshot)",
    re.IGNORECASE,
)
_AGENT_KEY_RE = re.compile(
    r"(agent|instance[_-]?ai|instanceai|aiassistant)",
    re.IGNORECASE,
)
_VERSION_RE = re.compile(r"^(\d+)\.(\d+)(?:\.(\d+))?(.*)$")
_VERSION_KEYS = (
    "versionCli",
    "version",
    "n8nVersion",
    "cliVersion",
)
_N8N_GET_PATHS = (
    ("health", "/healthz"),
    ("readiness", "/healthz/readiness"),
    ("settings", "/rest/settings"),
)


def _suffix_is_prerelease(extra: str) -> bool:
    extra = extra.strip()
    if extra.startswith("+"):
        return False
    if extra.startswith("-") or _PRERELEASE_TOKEN_RE.search(extra):
        return True
    return bool(extra)


def _parse_version(label: Any) -> tuple[Any, Any]:
    """Return ((major, minor, patch), is_prerelease) or (UNKNOWN, UNKNOWN)."""
    if not isinstance(label, str) or not label.strip():
        return UNKNOWN, UNKNOWN
    match = _VERSION_RE.match(label.strip().lstrip("vV"))
    if not match:
        return UNKNOWN, UNKNOWN
    major, minor, patch, extra = match.groups()
    parsed = (int(major), int(minor), int(patch or 0))
    return parsed, _suffix_is_prerelease(extra)


def load_prerelease_allowlist(
    path: Optional[Path] = None,
    environ: Optional[dict[str, str]] = None,
) -> set[str]:
    env = environ if environ is not None else os.environ
    allowed = {
        part.strip()
        for part in env.get(N8N_PRERELEASE_ALLOWLIST_ENV, "").split(",")
        if part.strip()
    }
    manifest = path or (MANIFEST_ROOT / "n8n_prerelease_allowlist.json")
    if not manifest.exists():
        return allowed
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return allowed
    listed = payload.get("allowlist", [])
    if isinstance(listed, list):
        allowed.update(str(item).strip() for item in listed if str(item).strip())
    return allowed


def _first_version_field(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return UNKNOWN
    for key in _VERSION_KEYS:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return UNKNOWN


def _version_from_payload(payload: Any, headers: dict[str, str]) -> Any:
    version = _first_version_field(payload)
    if version is not UNKNOWN:
        return version
    nested = _first_version_field(
        payload.get("versionNotifications") if isinstance(payload, dict) else None
    )
    if nested is not UNKNOWN:
        return nested
    for header_name in ("n8n-version", "x-n8n-version"):
        for key, value in headers.items():
            if key.lower() == header_name and value.strip():
                return value.strip()
    return UNKNOWN


def _agent_settings(payload: Any) -> dict[str, Any]:
    found: dict[str, Any] = {}
    if not isinstance(payload, dict):
        return found

    def walk(node: Any, prefix: str) -> None:
        if not isinstance(node, dict):
            return
        for key, value in node.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if _AGENT_KEY_RE.search(str(key)):
                found[path] = value
            walk(value, path)

    walk(payload, "")
    return found


def _observable_env(environ: Optional[dict[str, str]]) -> dict[str, Any]:
    env = environ if environ is not None else os.environ
    observed: dict[str, Any] = {}
    for key in N8N_OBSERVABLE_ENV_KEYS:
        if key not in env:
            continue
        observed[key] = "REDACTED" if is_secret_key(key) else env[key]
    return observed


def _safety_record(
    *,
    verdict: str,
    parsed_version: Any,
    prerelease: Any,
    prerelease_allowlisted: bool,
    agents_owner_review: Any,
    upgrade_candidate: Any,
    flags: list[str],
    errors: list[str],
) -> dict[str, Any]:
    return {
        "verdict": verdict,
        "parsed_version": parsed_version,
        "prerelease": prerelease,
        "prerelease_allowlisted": prerelease_allowlisted,
        "agents_owner_review": agents_owner_review,
        "upgrade_candidate": upgrade_candidate,
        "flags": flags,
        "errors": errors,
    }


def _release_type_is_prerelease(release_type: Any) -> bool:
    return (
        isinstance(release_type, str)
        and release_type != UNKNOWN
        and bool(_PRERELEASE_TOKEN_RE.search(release_type))
    )


def _agents_need_owner_review(
    parsed: Any,
    agent_settings: dict[str, Any],
    flags: list[str],
) -> bool:
    review = False
    if isinstance(parsed, tuple) and parsed[:2] == N8N_AGENTS_REVIEW_MINOR:
        review = True
        flags.append("n8n_2_41_default_enabled_agents")
    enabled_hints = [
        key
        for key, value in agent_settings.items()
        if value is True or (isinstance(value, str) and value.lower() in {"true", "enabled"})
    ]
    if enabled_hints:
        review = True
        flags.append("observable_agents_enabled")
    return review


def evaluate_n8n_safety(
    version_label: Any,
    *,
    agent_settings: Optional[dict[str, Any]] = None,
    release_type: Any = UNKNOWN,
    allowlist: Optional[set[str]] = None,
) -> dict[str, Any]:
    flags: list[str] = []
    errors: list[str] = []
    parsed, prerelease = _parse_version(version_label)

    if version_label is UNKNOWN or parsed is UNKNOWN:
        errors.append("n8n_version_unknown")
        return _safety_record(
            verdict="fail",
            parsed_version=UNKNOWN,
            prerelease=UNKNOWN,
            prerelease_allowlisted=False,
            agents_owner_review=UNKNOWN,
            upgrade_candidate=UNKNOWN,
            flags=flags,
            errors=errors,
        )

    prerelease_flag = bool(prerelease) or _release_type_is_prerelease(release_type)
    allowlisted = str(version_label) in (allowlist or set())
    if prerelease_flag and not allowlisted:
        errors.append("prerelease_not_allowlisted")
        verdict = "fail"
    elif prerelease_flag:
        flags.append("prerelease_allowlisted")
        verdict = "owner_review"
    else:
        verdict = "pass"

    agents_review = _agents_need_owner_review(parsed, agent_settings or {}, flags)
    if agents_review and verdict == "pass":
        verdict = "owner_review"

    upgrade_candidate: Any = UNKNOWN
    if isinstance(parsed, tuple) and not prerelease_flag and parsed < N8N_MIN_STABLE:
        upgrade_candidate = N8N_MIN_STABLE_LABEL
        flags.append("upgrade_candidate_only")
        if verdict == "pass":
            verdict = "owner_review"

    return _safety_record(
        verdict=verdict,
        parsed_version=list(parsed) if isinstance(parsed, tuple) else UNKNOWN,
        prerelease=prerelease_flag,
        prerelease_allowlisted=allowlisted,
        agents_owner_review=agents_review,
        upgrade_candidate=upgrade_candidate,
        flags=flags,
        errors=errors,
    )


def _record_settings(result: dict[str, Any], response: Any) -> tuple[Any, dict[str, str]]:
    if response.ok and isinstance(response.json_body, dict):
        payload = response.json_body
        result["observable_settings"] = {
            key: payload[key]
            for key in payload
            if _AGENT_KEY_RE.search(str(key)) or key in _VERSION_KEYS
        }
        return payload, response.headers
    result["errors"].append(
        response.error if response.error is not UNKNOWN else "settings_unreadable"
    )
    return UNKNOWN, {}


def _n8n_reached(result: dict[str, Any], settings_payload: Any) -> bool:
    if settings_payload is not UNKNOWN:
        return True
    for key in ("health", "readiness"):
        payload = result.get(key)
        if isinstance(payload, dict) and payload.get("ok") is True:
            return True
    return False


def probe_n8n(
    *,
    host: str = LOOPBACK_HOST,
    port: int = N8N_PORT,
    client: Optional[LoopbackClient] = None,
    environ: Optional[dict[str, str]] = None,
    allowlist_path: Optional[Path] = None,
) -> dict[str, Any]:
    env_observed = _observable_env(environ)
    result: dict[str, Any] = {
        "schema_id": "databossx.rd.n8n_guard",
        "schema_version": "1.0",
        "read_only": True,
        "host": host,
        "port": port,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "verdict": "fail",
        "n8n_version": UNKNOWN,
        "health": UNKNOWN,
        "readiness": UNKNOWN,
        "observable_settings": UNKNOWN,
        "observable_env": env_observed,
        "agent_related": UNKNOWN,
        "safety": UNKNOWN,
        "errors": [],
        "unknowns": ["n8n_version", "agent_related"],
        "config_edited": False,
        "workflows_edited": False,
        "upgrade_attempted": False,
        "cloud_calls_attempted": False,
    }
    if host != LOOPBACK_HOST:
        result["errors"].append(f"non_loopback_host:{host}")
        return redact(result)

    http = client or LoopbackClient()
    settings_payload: Any = UNKNOWN
    headers: dict[str, str] = {}
    for label, path in _N8N_GET_PATHS:
        try:
            response = http.request("GET", host, port, path, allowed=N8N_ALLOWED_PATHS)
        except LoopbackHttpError as exc:
            result["errors"].append(str(exc))
            continue
        if label == "settings":
            settings_payload, headers = _record_settings(result, response)
        else:
            result[label] = response.as_dict()

    version = _version_from_payload(settings_payload, headers)
    if version is UNKNOWN:
        version = env_observed.get("N8N_VERSION", UNKNOWN)
    result["n8n_version"] = version if version else UNKNOWN
    if result["n8n_version"] is not UNKNOWN:
        result["unknowns"].remove("n8n_version")

    agent_related = _agent_settings(settings_payload) if settings_payload is not UNKNOWN else {}
    if agent_related:
        result["agent_related"] = agent_related
        result["unknowns"].remove("agent_related")
    else:
        result["agent_related"] = UNKNOWN

    safety = evaluate_n8n_safety(
        result["n8n_version"],
        agent_settings=agent_related or None,
        release_type=env_observed.get("N8N_RELEASE_TYPE", UNKNOWN),
        allowlist=load_prerelease_allowlist(allowlist_path, environ),
    )
    result["safety"] = safety
    if _n8n_reached(result, settings_payload):
        result["verdict"] = safety["verdict"]
    else:
        result["errors"].append("n8n_loopback_unreachable")
        result["verdict"] = "fail"
    result["errors"].extend(safety["errors"])
    return redact(result)
