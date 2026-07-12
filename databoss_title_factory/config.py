"""Validated configuration loading with explicit environment substitution."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .security import EvidenceStatus, resolve_allowed_path

_ENV_PATTERN = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)\}")


class ConfigError(ValueError):
    """Configuration is missing, malformed, or violates a safety policy."""


def _expand(value: Any, environment: Mapping[str, str]) -> Any:
    if isinstance(value, dict):
        return {key: _expand(item, environment) for key, item in value.items()}
    if isinstance(value, list):
        return [_expand(item, environment) for item in value]
    if not isinstance(value, str):
        return value

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if not environment.get(name):
            raise ConfigError(f"required environment variable is not set: {name}")
        return environment[name]

    return _ENV_PATTERN.sub(replace, value)


def _validate_evidence_labels(value: Any, location: str = "$") -> None:
    if isinstance(value, dict):
        if "evidence_status" in value:
            try:
                EvidenceStatus(value["evidence_status"])
            except (TypeError, ValueError) as exc:
                raise ConfigError(
                    f"{location}.evidence_status is not a recognized EvidenceStatus"
                ) from exc
        for key, item in value.items():
            _validate_evidence_labels(item, f"{location}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _validate_evidence_labels(item, f"{location}[{index}]")


@dataclass(frozen=True)
class ProjectConfig:
    path: Path
    data: Mapping[str, Any]

    @property
    def source_root(self) -> Path:
        value = self.data.get("source_root")
        if not isinstance(value, str) or not value:
            raise ConfigError("source_root is required")
        return Path(value).expanduser()

    @property
    def external_providers_enabled(self) -> bool:
        return any(
            bool(provider.get("enabled"))
            for provider in self.data.get("providers", [])
            if isinstance(provider, dict) and provider.get("provider") != "local"
        )

    def resolve_source_root(
        self,
        allowed_roots: tuple[str | os.PathLike[str], ...],
    ) -> Path:
        return resolve_allowed_path(self.source_root, allowed_roots)


def load_config(
    path: str | os.PathLike[str],
    *,
    environment: Mapping[str, str] | None = None,
    allowed_roots: tuple[str | os.PathLike[str], ...] | None = None,
) -> ProjectConfig:
    config_path = Path(path).expanduser()
    if allowed_roots is not None:
        config_path = resolve_allowed_path(config_path, allowed_roots)
    else:
        config_path = config_path.resolve(strict=True)
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"cannot load JSON configuration: {config_path}") from exc
    if not isinstance(raw, dict):
        raise ConfigError("configuration root must be a JSON object")
    expansion_environment = os.environ if environment is None else environment
    data = _expand(raw, expansion_environment)
    _validate_evidence_labels(data)
    providers = data.get("providers", [])
    if not isinstance(providers, list):
        raise ConfigError("providers must be a list")
    allow_external = bool(data.get("external_model_upload_enabled", False))
    if not allow_external:
        enabled_external = [
            provider.get("provider", "unknown")
            for provider in providers
            if isinstance(provider, dict)
            and provider.get("provider") != "local"
            and provider.get("enabled")
        ]
        if enabled_external:
            raise ConfigError(
                "external providers cannot be enabled while external_model_upload_enabled is false"
            )
    if data.get("readiness_default") not in {None, "BLOCKED", "NOT READY TO SUBMIT"}:
        raise ConfigError("readiness_default must fail closed")
    return ProjectConfig(config_path, data)
