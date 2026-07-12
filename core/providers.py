"""Policy-controlled provider registry with local and mock implementations."""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional
from urllib.error import URLError
from urllib.request import Request, urlopen

from .security import credential_status


@dataclass(frozen=True)
class ProviderResponse:
    provider: str
    model: str
    status: str
    content: Dict[str, Any]
    latency_ms: int
    retries: int = 0
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cost_usd: str = "0"

    @property
    def response_hash(self) -> str:
        data = json.dumps(self.content, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(data.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    credential_env: Optional[str]
    endpoint_env: Optional[str]
    default_endpoint: Optional[str]
    capabilities: frozenset[str] = field(default_factory=frozenset)
    local_only: bool = False


PROVIDERS = {
    "openai": ProviderConfig(
        "openai", "OPENAI_API_KEY", None, "https://api.openai.com/v1",
        frozenset({"reasoning", "vision", "coding", "structured"}),
    ),
    "anthropic": ProviderConfig(
        "anthropic", "ANTHROPIC_API_KEY", None, "https://api.anthropic.com/v1",
        frozenset({"reasoning", "vision", "long_context", "structured"}),
    ),
    "google": ProviderConfig(
        "google", "GOOGLE_API_KEY", None, "https://generativelanguage.googleapis.com/v1beta",
        frozenset({"reasoning", "vision", "long_context", "structured"}),
    ),
    "xai": ProviderConfig(
        "xai", "XAI_API_KEY", None, "https://api.x.ai/v1",
        frozenset({"reasoning", "structured"}),
    ),
    "ollama": ProviderConfig(
        "ollama", None, "OLLAMA_BASE_URL", "http://127.0.0.1:11434",
        frozenset({"local", "privacy"}), True,
    ),
    "lmstudio": ProviderConfig(
        "lmstudio", None, "LMSTUDIO_BASE_URL", "http://127.0.0.1:1234/v1",
        frozenset({"local", "privacy", "structured"}), True,
    ),
    "mock": ProviderConfig(
        "mock", None, None, None, frozenset({"test", "structured"}), True
    ),
}


class MockProvider:
    name = "mock"

    def complete(self, task: Dict[str, Any], model: str = "deterministic-mock-v1") -> ProviderResponse:
        started = time.monotonic()
        content = {
            "status": "SUCCEEDED",
            "task_id": task.get("task_id"),
            "claims": [],
            "citations": [],
            "summary": "Deterministic mock response; no evidentiary claims asserted.",
        }
        return ProviderResponse(
            provider=self.name,
            model=model,
            status="SUCCEEDED",
            content=content,
            latency_ms=int((time.monotonic() - started) * 1000),
        )


def route_provider(
    required_capabilities: Iterable[str],
    *,
    local_only: bool = False,
    approved: Iterable[str] = PROVIDERS,
    health: Optional[Dict[str, bool]] = None,
) -> str:
    requirements = set(required_capabilities)
    candidates: List[str] = []
    for name in approved:
        config = PROVIDERS.get(name)
        if config is None or (local_only and not config.local_only):
            continue
        if not requirements.issubset(config.capabilities):
            continue
        if health is not None and not health.get(name, False):
            continue
        candidates.append(name)
    if not candidates:
        raise LookupError("no approved healthy provider satisfies task policy")
    return candidates[0]


def provider_health(*, network_checks: bool = False, timeout: float = 0.75) -> List[Dict[str, str]]:
    report: List[Dict[str, str]] = []
    for name, config in PROVIDERS.items():
        credential = (
            credential_status(config.credential_env) if config.credential_env else "NOT_REQUIRED"
        )
        endpoint = (
            os.environ.get(config.endpoint_env, config.default_endpoint or "")
            if config.endpoint_env
            else (config.default_endpoint or "")
        )
        reachable = "NOT_TESTED"
        discovery = "NO"
        completion = "NO"
        if name == "mock":
            reachable = discovery = completion = "YES"
        elif network_checks and endpoint and (
            config.local_only or credential == "YES"
        ):
            try:
                request = Request(endpoint.rstrip("/") + "/models", method="GET")
                with urlopen(request, timeout=timeout) as response:
                    reachable = "YES" if response.status < 500 else "NO"
                    discovery = "YES" if response.status < 400 else "NO"
            except (OSError, URLError, ValueError):
                reachable = "NO"
        report.append(
            {
                "provider": name,
                "configured": "YES",
                "credential_detected": credential,
                "endpoint_reachable": reachable,
                "model_discovery_successful": discovery,
                "test_completion_successful": completion,
            }
        )
    return report
