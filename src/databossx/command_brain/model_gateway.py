"""Provider-neutral Model Gateway.

Nothing in the Command Brain talks to a model directly. Every call goes through
an adapter that declares its capabilities honestly and reports one of five
verification states. **A green state is never assumed**: an adapter starts at
NOT_VERIFIED and only becomes VERIFIED after a probe actually succeeds.

Adapters here are deliberately thin. Real network SDKs (Anthropic, OpenAI,
Ollama, local OpenAI-compatible servers) are selected at runtime from what the
environment actually has installed — this module never imports them at module
scope, so the Command Brain runs on a stdlib-only machine.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .errors import EgressDenied, ModelUnavailable, RegistryFrozen
from .policy import DataSensitivity, PolicyProfile
from .util import Clock, canonical_hash


class VerificationState(str, Enum):
    VERIFIED = "VERIFIED"
    LIMITED = "LIMITED"
    NOT_VERIFIED = "NOT_VERIFIED"
    OFFLINE = "OFFLINE"
    QUARANTINED = "QUARANTINED"


USABLE_STATES = frozenset({VerificationState.VERIFIED, VerificationState.LIMITED})


class Modality(str, Enum):
    TEXT = "text"
    VISION = "vision"
    AUDIO = "audio"
    EMBEDDINGS = "embeddings"
    DETERMINISTIC = "deterministic"


@dataclass(frozen=True)
class ModelDescriptor:
    model_id: str
    provider: str
    display_name: str
    modalities: frozenset
    context_limit: int
    tool_use: bool
    structured_output: bool
    is_local: bool
    cost_category: str
    latency_category: str
    data_sensitivity_policy: DataSensitivity
    permitted_project_classes: tuple
    simulated: bool = False

    def __post_init__(self):
        object.__setattr__(self, "modalities", frozenset(Modality(m) for m in self.modalities))
        object.__setattr__(self, "data_sensitivity_policy", DataSensitivity(self.data_sensitivity_policy))
        object.__setattr__(self, "permitted_project_classes", tuple(self.permitted_project_classes))

    def supports(self, modality) -> bool:
        return Modality(modality) in self.modalities

    def to_dict(self) -> dict:
        return {
            "model_id": self.model_id,
            "provider": self.provider,
            "display_name": self.display_name,
            "modalities": sorted(m.value for m in self.modalities),
            "context_limit": self.context_limit,
            "tool_use": self.tool_use,
            "structured_output": self.structured_output,
            "is_local": self.is_local,
            "cost_category": self.cost_category,
            "latency_category": self.latency_category,
            "data_sensitivity_policy": self.data_sensitivity_policy.value,
            "permitted_project_classes": list(self.permitted_project_classes),
            "simulated": self.simulated,
        }


@dataclass
class ModelHealth:
    state: VerificationState = VerificationState.NOT_VERIFIED
    detail: str = "No verification probe has run."
    last_verified_at: str | None = None

    def to_dict(self) -> dict:
        return {
            "verification_state": self.state.value,
            "detail": self.detail,
            "last_verified_at": self.last_verified_at,
        }


@dataclass(frozen=True)
class ModelRequest:
    capability: str
    payload: dict
    modality: Modality = Modality.TEXT
    max_output_tokens: int = 2048


@dataclass(frozen=True)
class ModelResponse:
    model_id: str
    output: dict
    simulated: bool
    verification_state: VerificationState
    input_hash: str
    output_hash: str
    detail: str = ""

    def to_dict(self) -> dict:
        return {
            "model_id": self.model_id,
            "output": self.output,
            "simulated": self.simulated,
            "verification_state": self.verification_state.value,
            "input_hash": self.input_hash,
            "output_hash": self.output_hash,
            "detail": self.detail,
        }


class ModelAdapter:
    """Base adapter. Subclasses implement :meth:`probe` and :meth:`invoke`."""

    def __init__(self, descriptor: ModelDescriptor):
        self.descriptor = descriptor
        self.health = ModelHealth()

    @property
    def model_id(self) -> str:
        return self.descriptor.model_id

    def probe(self, clock: Clock) -> ModelHealth:
        """Honest availability check. Must not claim VERIFIED without evidence."""
        raise NotImplementedError

    def invoke(self, request: ModelRequest) -> dict:
        raise NotImplementedError

    def quarantine(self, reason: str) -> None:
        self.health = ModelHealth(VerificationState.QUARANTINED, reason, self.health.last_verified_at)


class DeterministicAdapter(ModelAdapter):
    """A pure-Python worker exposed through the gateway.

    Deterministic validators are routed here rather than to a language model, so
    workbook checks, hashing, and title math never depend on generation.
    """

    def __init__(self, descriptor: ModelDescriptor, fn):
        super().__init__(descriptor)
        self._fn = fn

    def probe(self, clock: Clock) -> ModelHealth:
        self.health = ModelHealth(
            VerificationState.VERIFIED,
            "Deterministic in-process worker; no network dependency.",
            clock.now_iso(),
        )
        return self.health

    def invoke(self, request: ModelRequest) -> dict:
        return self._fn(request)


class SimulatedAdapter(ModelAdapter):
    """Clearly-labelled stand-in used for the synthetic demo and tests.

    Every response it produces carries ``simulated: True`` and the descriptor is
    forced to ``simulated=True`` at construction, so a simulated result can never
    be presented as a real model reading.
    """

    def __init__(self, descriptor: ModelDescriptor, fn):
        if not descriptor.simulated:
            raise RegistryFrozen(
                f"{descriptor.model_id} is registered as a simulated adapter but not labelled simulated.",
                detail={"model_id": descriptor.model_id},
            )
        super().__init__(descriptor)
        self._fn = fn

    def probe(self, clock: Clock) -> ModelHealth:
        self.health = ModelHealth(
            VerificationState.LIMITED,
            "SIMULATED adapter. Produces deterministic stand-in output, not a real model reading.",
            clock.now_iso(),
        )
        return self.health

    def invoke(self, request: ModelRequest) -> dict:
        output = self._fn(request)
        if isinstance(output, dict):
            output.setdefault("simulated", True)
        return output


class HttpModelAdapter(ModelAdapter):
    """Adapter for an OpenAI-compatible HTTP endpoint (local or remote).

    Used for local Ollama / llama.cpp / vLLM servers and for cloud endpoints
    alike. The transport is injected: ``probe_fn`` and ``invoke_fn`` are supplied
    by whatever HTTP client the host environment actually has. With no transport
    the adapter stays NOT_VERIFIED — it never pretends.
    """

    def __init__(self, descriptor: ModelDescriptor, base_url: str, probe_fn=None, invoke_fn=None):
        super().__init__(descriptor)
        self.base_url = base_url
        self._probe_fn = probe_fn
        self._invoke_fn = invoke_fn

    def probe(self, clock: Clock) -> ModelHealth:
        if self._probe_fn is None:
            self.health = ModelHealth(
                VerificationState.NOT_VERIFIED,
                f"No transport configured for {self.base_url}; capability is unproven.",
                self.health.last_verified_at,
            )
            return self.health
        try:
            detail = self._probe_fn(self.base_url, self.descriptor)
        except Exception as exc:  # noqa: BLE001 - a failed probe is a real result
            self.health = ModelHealth(
                VerificationState.OFFLINE, f"Probe failed: {exc}", self.health.last_verified_at
            )
            return self.health
        self.health = ModelHealth(VerificationState.VERIFIED, str(detail), clock.now_iso())
        return self.health

    def invoke(self, request: ModelRequest) -> dict:
        if self._invoke_fn is None:
            raise ModelUnavailable(
                f"{self.model_id} has no configured transport.", detail={"model_id": self.model_id}
            )
        return self._invoke_fn(self.base_url, self.descriptor, request)


class HandoffAdapter(ModelAdapter):
    """A coding agent reached by handoff, not by API call.

    Claude Code and Codex lanes are represented here. In Alpha they emit a
    structured handoff package for a human to carry across; the adapter never
    claims the work was performed.
    """

    def __init__(self, descriptor: ModelDescriptor, builder):
        super().__init__(descriptor)
        self._builder = builder

    def probe(self, clock: Clock) -> ModelHealth:
        self.health = ModelHealth(
            VerificationState.NOT_VERIFIED,
            "Handoff lane: produces a task package for an external coding agent. "
            "No execution is performed or claimed by DataBossX.",
            clock.now_iso(),
        )
        return self.health

    def invoke(self, request: ModelRequest) -> dict:
        return self._builder(request)


class ModelGateway:
    """Registry, health tracker, and policy-aware router for model adapters."""

    def __init__(self, clock: Clock | None = None, store=None):
        self.clock = clock or Clock()
        self.store = store
        self._adapters: dict[str, ModelAdapter] = {}

    def register(self, adapter: ModelAdapter) -> ModelAdapter:
        if adapter.model_id in self._adapters:
            raise RegistryFrozen(
                f"Model {adapter.model_id!r} is already registered.",
                detail={"model_id": adapter.model_id},
            )
        self._adapters[adapter.model_id] = adapter
        return adapter

    def get(self, model_id: str) -> ModelAdapter:
        try:
            return self._adapters[model_id]
        except KeyError:
            raise ModelUnavailable(
                f"{model_id!r} is not a registered model endpoint.",
                detail={"model_id": model_id, "registered": sorted(self._adapters)},
            ) from None

    def probe_all(self) -> dict:
        results = {}
        for model_id, adapter in self._adapters.items():
            if adapter.health.state is VerificationState.QUARANTINED:
                results[model_id] = adapter.health.to_dict()
                continue
            results[model_id] = adapter.probe(self.clock).to_dict()
        self.sync(self.store)
        return results

    def catalog(self) -> list[dict]:
        entries = []
        for model_id in sorted(self._adapters):
            adapter = self._adapters[model_id]
            entry = adapter.descriptor.to_dict()
            entry.update(adapter.health.to_dict())
            entries.append(entry)
        return entries

    def verified_models(self) -> list[str]:
        return sorted(
            model_id
            for model_id, adapter in self._adapters.items()
            if adapter.health.state is VerificationState.VERIFIED
        )

    def unverified_models(self) -> list[str]:
        return sorted(
            model_id
            for model_id, adapter in self._adapters.items()
            if adapter.health.state is not VerificationState.VERIFIED
        )

    # -- routing ----------------------------------------------------------
    def eligible(
        self,
        profile: PolicyProfile,
        *,
        modality: Modality = Modality.TEXT,
        structured_output: bool = True,
        project_class: str = "synthetic",
    ) -> list[str]:
        """Hard policy filters first; capability second. No ranking by vibes."""
        eligible = []
        for model_id in sorted(self._adapters):
            adapter = self._adapters[model_id]
            descriptor = adapter.descriptor
            if adapter.health.state not in USABLE_STATES:
                continue
            if profile.local_only and not descriptor.is_local:
                continue
            if not profile.cloud_models_allowed and not descriptor.is_local:
                continue
            if not descriptor.supports(modality):
                continue
            if structured_output and not descriptor.structured_output:
                continue
            if descriptor.permitted_project_classes and project_class not in descriptor.permitted_project_classes:
                continue
            eligible.append(model_id)
        return eligible

    def invoke(
        self,
        model_id: str,
        request: ModelRequest,
        profile: PolicyProfile,
        *,
        project_class: str = "synthetic",
    ) -> ModelResponse:
        adapter = self.get(model_id)
        descriptor = adapter.descriptor
        state = adapter.health.state

        if state is VerificationState.QUARANTINED:
            raise ModelUnavailable(
                f"{model_id} is quarantined: {adapter.health.detail}", detail={"model_id": model_id}
            )
        if state not in USABLE_STATES:
            raise ModelUnavailable(
                f"{model_id} is {state.value}: {adapter.health.detail}",
                detail={"model_id": model_id, "verification_state": state.value},
            )
        if not descriptor.is_local and (profile.local_only or not profile.cloud_models_allowed):
            raise EgressDenied(
                f"{model_id} is a remote endpoint and the current profile forbids egress.",
                detail={"model_id": model_id},
            )
        if not descriptor.supports(request.modality):
            raise ModelUnavailable(
                f"{model_id} has no verified {request.modality.value} capability.",
                detail={"model_id": model_id, "modality": request.modality.value},
            )
        if descriptor.permitted_project_classes and project_class not in descriptor.permitted_project_classes:
            raise ModelUnavailable(
                f"{model_id} is not permitted for project class {project_class!r}.",
                detail={"model_id": model_id},
            )

        input_hash = canonical_hash(request.payload)
        output = adapter.invoke(request)
        response = ModelResponse(
            model_id=model_id,
            output=output,
            simulated=descriptor.simulated,
            verification_state=state,
            input_hash=input_hash,
            output_hash=canonical_hash(output),
            detail=adapter.health.detail,
        )
        if self.store is not None:
            self.store.audit(
                "model.invoked",
                "model",
                model_id,
                {
                    "input_hash": response.input_hash,
                    "output_hash": response.output_hash,
                    "simulated": response.simulated,
                    "verification_state": state.value,
                    "capability": request.capability,
                    "is_local": descriptor.is_local,
                },
            )
        return response

    # -- persistence ------------------------------------------------------
    def sync(self, store) -> None:
        if store is None:
            return
        for adapter in self._adapters.values():
            descriptor = adapter.descriptor
            store.execute(
                """
                INSERT OR REPLACE INTO cb_model_providers (provider_id, display_name, is_local, registered_at)
                VALUES (?, ?, ?, ?)
                """,
                (descriptor.provider, descriptor.provider, int(descriptor.is_local), store.now()),
            )
            store.execute(
                """
                INSERT OR REPLACE INTO cb_model_endpoints (
                    model_id, provider_id, display_name, is_local, simulated, verification_state,
                    context_limit, tool_use, structured_output, cost_category, latency_category,
                    data_sensitivity_policy, permitted_project_classes, last_verified_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    descriptor.model_id,
                    descriptor.provider,
                    descriptor.display_name,
                    int(descriptor.is_local),
                    int(descriptor.simulated),
                    adapter.health.state.value,
                    descriptor.context_limit,
                    int(descriptor.tool_use),
                    int(descriptor.structured_output),
                    descriptor.cost_category,
                    descriptor.latency_category,
                    descriptor.data_sensitivity_policy.value,
                    ",".join(descriptor.permitted_project_classes),
                    adapter.health.last_verified_at,
                ),
            )
            for modality in Modality:
                store.execute(
                    """
                    INSERT OR REPLACE INTO cb_model_capabilities (model_id, capability, supported)
                    VALUES (?, ?, ?)
                    """,
                    (descriptor.model_id, modality.value, int(descriptor.supports(modality))),
                )
