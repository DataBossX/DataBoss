from __future__ import annotations

import json
import uuid

from databossx.hashing import sha256_bytes

from .models import ImprovementProposal, TaskEnvelope


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
    if proposal.autonomy_level not in {"L0", "L1", "L2"}:
        raise ValueError("governor may only compile L0-L2 envelopes")
    payload = {
        "proposal_id": proposal.proposal_id,
        "base_commit": base_commit,
        "inputs": sorted(inputs),
        "capabilities": ["tests", "docs", "synthetic_fixtures"],
        "allowlist": sorted(allowlist or ["tests/", "src/databossx/governor/", "docs/"]),
        "budgets": {"files": 12, "seconds": 180, "tokens": 0},
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
