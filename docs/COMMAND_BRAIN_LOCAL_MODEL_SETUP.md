# Command Brain — Local Model Setup

For running DataBossX Command Brain on a Windows PC with local models and no
outbound model traffic.

## What works with no setup at all

The Command Brain has **no third-party Python dependency**. On a machine with only
CPython installed:

```
python -m databossx.command_brain.demo     # full controlled demo, synthetic data
python -m pytest tests/test_command_brain_*.py
```

The deterministic workers (`deterministic.reconciler`, `deterministic.judge`,
`deterministic.commander`, `deterministic.validator`, `human.review_queue`) are
VERIFIED out of the box because they are in-process and reproducible. The four
`simulated.reader.*` adapters are LIMITED and labelled SIMULATED everywhere they
appear.

Everything else stays NOT_VERIFIED until you configure a transport. That is
deliberate: the gateway will not claim a capability it has not observed.

## Turning on local-only mode

Spoken or typed:

> "Use only local models."
> "Use no cloud models."

Or in code:

```python
from databossx.command_brain.policy import PolicyProfile
runtime.policy.set_profile(PolicyProfile().with_local_only().with_read_only())
```

Under `local_only`:

- every non-local adapter is excluded from routing
- a direct call to a remote adapter raises `EgressDenied`
- `cloud_models_allowed` is forced to `False` — the stronger statement wins
- deterministic validators and the job queue keep working

## Wiring a local OpenAI-compatible endpoint

`local.openai_compatible` is registered pointing at `http://127.0.0.1:11434`
(Ollama's default) with **no transport**, so it reports:

```
NOT_VERIFIED — No transport configured for http://127.0.0.1:11434; capability is unproven.
```

To make it real, supply `probe_fn` and `invoke_fn` using whatever HTTP client the
machine actually has. Nothing is imported at module scope, so an environment
without `requests` or `httpx` still starts.

```python
import json, urllib.request
from databossx.command_brain.model_gateway import (
    HttpModelAdapter, Modality, ModelDescriptor,
)
from databossx.command_brain.policy import DataSensitivity


def probe(base_url, descriptor):
    with urllib.request.urlopen(f"{base_url}/api/tags", timeout=5) as response:
        tags = json.load(response)
    names = [model["name"] for model in tags.get("models", [])]
    if descriptor.display_name not in names:
        raise RuntimeError(f"{descriptor.display_name} is not pulled on this host")
    return f"Reachable; {len(names)} model(s) available."


def invoke(base_url, descriptor, request):
    body = json.dumps({
        "model": descriptor.display_name,
        "prompt": request.payload["prompt"],
        "format": "json",
        "stream": False,
    }).encode()
    call = urllib.request.Request(
        f"{base_url}/api/generate", data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(call, timeout=120) as response:
        return json.loads(json.load(response)["response"])


runtime.gateway.register(
    HttpModelAdapter(
        ModelDescriptor(
            model_id="local.llama",
            provider="ollama",
            display_name="llama3.1:8b",
            modalities={Modality.TEXT},
            context_limit=131_072,
            tool_use=False,
            structured_output=True,
            is_local=True,
            cost_category="LOCAL",
            latency_category="VARIABLE",
            data_sensitivity_policy=DataSensitivity.INTERNAL,
            permitted_project_classes=("synthetic", "internal"),
        ),
        base_url="http://127.0.0.1:11434",
        probe_fn=probe,
        invoke_fn=invoke,
    )
)
runtime.gateway.probe_all()
```

The probe must *fail* when the model is absent. An adapter whose probe raises
becomes OFFLINE, and OFFLINE models are ineligible for routing. Do not write a
probe that returns success on a connection error.

### Vision

Do not register `Modality.VISION` unless the specific pulled model actually has
verified vision capability. Claiming vision a model does not have means index
pages get "read" by something that cannot see them, which is precisely the
failure the scoring rubric exists to catch.

If you do register a vision model, `permitted_project_classes` should stay at
`("synthetic",)` until it has been benchmarked against the ground-truth corpus in
`synthetic.py`.

## Confirming nothing leaves the machine

```python
profile = runtime.policy.profile
assert profile.local_only
for model_id in runtime.gateway.eligible(profile):
    assert runtime.gateway.get(model_id).descriptor.is_local
```

`tests/test_command_brain_privacy_audit.py::test_local_only_tournament_uses_only_local_models`
runs a full tournament and asserts that every succeeded assignment used a local
model.

For belt and braces, block outbound traffic at the OS firewall for the Python
process. Local-only mode is enforced in the gateway, but a host-level rule is a
second, independent control.

## Hardware notes

- The whole subsystem is CPU-only and I/O-light. The synthetic tournament runs in
  well under a second.
- SQLite runs in WAL mode. Keep the runtime directory on a local disk, not a
  synced cloud folder — a sync client rewriting the database file underneath WAL
  is a corruption risk.
- The database is small (tens of KB for a demo run). Receipt and audit growth is
  linear in decisions, not in evidence.

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| `ModelUnavailable: … is NOT_VERIFIED` | No transport, or the probe never ran | Configure `probe_fn`, call `gateway.probe_all()` |
| `EgressDenied` | `local_only` is on and the model is remote | Expected. Register a local model instead |
| `ModelUnavailable: … has no verified vision capability` | Descriptor omits `Modality.VISION` | Only add it if the model genuinely has it |
| `AutonomyViolation: Requires autonomy READ_ONLY_EXECUTE` | Mode is draft-only | Say "Read-only mode" first — approval does not raise the mode |
| Adapter shows OFFLINE | Probe raised | Check the endpoint is running; the state is accurate |
