from __future__ import annotations

import json
import uuid

from databossx.hashing import sha256_bytes

from .models import ImprovementProposal, TaskEnvelope


DEFAULT_CAPABILITIES = ["tests", "docs", "synthetic_fixtures"]
DEFAULT_ALLOWLIST = ["tests/", "docs/"]
DEFAULT_BUDGETS = {"files": 12, "seconds": 180, "tokens": 0}
ALLOWED_AUTONOMY = {"L0", "L1", "L2"}


def compile_envelope(
    proposal: ImprovementProposal,
    *,
    base_commit: str,
    inputs: list[str],
    tests: list[str],
    allowlist: list[str] | None = None,
) -> TaskEnvelope:
    if proposal.status == "vetoed":
        raise ValueError("vetoed proposals cannot compile an envelope")
    if proposal.autonomy_level not in ALLOWED_AUTONOMY:
        raise ValueError("governor may only compile L0-L2 envelopes")
    payload = {
        "proposal_id": proposal.proposal_id,
        "base_commit": base_commit,
        "inputs": sorted(inputs),
        "capabilities": list(DEFAULT_CAPABILITIES),
        "allowlist": sorted(allowlist or list(DEFAULT_ALLOWLIST)),
        "budgets": dict(DEFAULT_BUDGETS),
        "tests": sorted(tests),
        "autonomy_level": proposal.autonomy_level,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return TaskEnvelope(
        envelope_id=uuid.uuid4().hex,
        proposal_id=proposal.proposal_id,
        base_commit=base_commit,
        inputs=payload["inputs"],
        capabilities=payload["capabilities"],
        allowlist=payload["allowlist"],
        budgets=payload["budgets"],
        tests=payload["tests"],
        autonomy_level=proposal.autonomy_level,
        envelope_hash=sha256_bytes(encoded),
        state="COMPILED",
    )
