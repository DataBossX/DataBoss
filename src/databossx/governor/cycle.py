from __future__ import annotations

import json
import uuid
from pathlib import Path

from databossx.config import DataBossConfig
from databossx.database import DataBossDatabase
from databossx.hashing import sha256_bytes

from .envelope import compile_envelope
from .inventory import census_repository
from .lease import acquire_lease, assert_lease
from .models import CycleReceipt, ImprovementProposal
from .ranker import rank_proposals


ISSUE94_SEEDS = [
    ImprovementProposal(
        proposal_id="issue94-repair-error-literal",
        title="Refuse workbook error-formula downgrade",
        evidence=["https://github.com/DataBossX/DataBoss/issues/94", "horizon/repair.py"],
        value_score=1.0,
        risk_score=0.2,
        cost_score=0.2,
        reversibility="high",
        confidence=0.95,
        autonomy_level="L2",
    ),
    ImprovementProposal(
        proposal_id="issue94-recording-date",
        title="Stop fabricating recording_date from unlabeled dates",
        evidence=["https://github.com/DataBossX/DataBoss/issues/94", "grocery_report_pipeline.py"],
        value_score=0.95,
        risk_score=0.15,
        cost_score=0.15,
        reversibility="high",
        confidence=0.95,
        autonomy_level="L2",
    ),
    ImprovementProposal(
        proposal_id="issue94-decimal-parser",
        title="Parse ordinary decimals; assert sum-to-one only when complete",
        evidence=["https://github.com/DataBossX/DataBoss/issues/94", "grocery_report_pipeline.py"],
        value_score=0.9,
        risk_score=0.15,
        cost_score=0.2,
        reversibility="high",
        confidence=0.9,
        autonomy_level="L2",
    ),
    ImprovementProposal(
        proposal_id="issue94-backend-fail-closed",
        title="Fail-closed demo backend auth/CORS/OCR",
        evidence=["https://github.com/DataBossX/DataBoss/issues/94", "backend/server.py"],
        value_score=0.85,
        risk_score=0.25,
        cost_score=0.25,
        reversibility="high",
        confidence=0.9,
        autonomy_level="L2",
    ),
    ImprovementProposal(
        proposal_id="client-release-forbidden",
        title="Autonomous client report release",
        evidence=["publication hold"],
        value_score=0.1,
        risk_score=1.0,
        cost_score=1.0,
        reversibility="none",
        confidence=1.0,
        autonomy_level="L4",
        vetoes=["external_release", "client_evidence", "auto_merge"],
        status="proposed",
    ),
]


def _persist_proposal(db: DataBossDatabase, proposal: ImprovementProposal) -> None:
    db.execute(
        """
        INSERT OR REPLACE INTO improvement_proposals (
            proposal_id, title, evidence_json, value_score, risk_score, cost_score,
            reversibility, confidence, autonomy_level, vetoes_json, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            proposal.proposal_id,
            proposal.title,
            json.dumps(proposal.evidence, sort_keys=True),
            proposal.value_score,
            proposal.risk_score,
            proposal.cost_score,
            proposal.reversibility,
            proposal.confidence,
            proposal.autonomy_level,
            json.dumps(proposal.vetoes, sort_keys=True),
            proposal.status,
        ),
    )


def run_synthetic_cycle(
    repo_root: str | Path,
    *,
    base_commit: str = "unknown",
    worker_id: str = "governor-l2",
) -> CycleReceipt:
    """One finite L2 cycle against synthetic seeds. Never mutates client bytes."""
    root = Path(repo_root)
    config = DataBossConfig.from_repo_root(root)
    config.ensure_runtime_dirs("governor")
    db = DataBossDatabase(config.project_db_path("governor"))
    db.initialize()

    census = census_repository(root)
    ranked = rank_proposals(list(ISSUE94_SEEDS))
    for proposal in ranked:
        _persist_proposal(db, proposal)

    chosen = next(item for item in ranked if item.status != "vetoed")
    envelope = compile_envelope(
        chosen,
        base_commit=base_commit,
        inputs=chosen.evidence,
        tests=["tests/test_issue94_integrity.py", "tests/test_governor.py"],
    )
    db.execute(
        """
        INSERT INTO task_envelopes (
            envelope_id, proposal_id, base_commit, payload_json, envelope_hash, state
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            envelope.envelope_id,
            envelope.proposal_id,
            envelope.base_commit,
            json.dumps(
                {
                    "inputs": envelope.inputs,
                    "tests": envelope.tests,
                    "allowlist": envelope.allowlist,
                },
                sort_keys=True,
            ),
            envelope.envelope_hash,
            envelope.state,
        ),
    )
    fence = acquire_lease(db, scope="repo:governor", worker_id=worker_id)
    assert_lease(db, "repo:governor", worker_id, fence)

    required = [
        root / "tests" / "test_issue94_integrity.py",
        root / "tests" / "test_governor.py",
        root / "tests" / "test_backend_security.py",
        root / "tests" / "test_publication_policy.py",
    ]
    missing = [str(path) for path in required if not path.exists()]
    outcome = "CYCLE_ACCEPTED_FOR_INDEPENDENT_REVIEW" if not missing else "CYCLE_BLOCKED_MISSING_REGRESSIONS"
    payload = {
        "census": census,
        "chosen": chosen.as_dict(),
        "envelope_hash": envelope.envelope_hash,
        "fence": fence,
        "missing_regressions": missing,
        "client_bytes_mutated": "NO",
        "external_release": "NO",
        "auto_merge": "NO",
    }
    receipt = CycleReceipt(
        receipt_id=uuid.uuid4().hex,
        envelope_hash=envelope.envelope_hash,
        outcome=outcome,
        payload=payload,
    )
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    db.execute(
        """
        INSERT INTO cycle_receipts (receipt_id, envelope_hash, outcome, payload_json)
        VALUES (?, ?, ?, ?)
        """,
        (receipt.receipt_id, receipt.envelope_hash, receipt.outcome, encoded.decode("utf-8")),
    )
    db.execute(
        """
        INSERT INTO learning_records (record_id, source_receipt_id, reviewed, claim, evidence_json)
        VALUES (?, ?, 0, ?, ?)
        """,
        (
            uuid.uuid4().hex,
            receipt.receipt_id,
            "Issue #94 public-safe regressions are the next bounded cycle.",
            json.dumps({"receipt_hash": sha256_bytes(encoded)}, sort_keys=True),
        ),
    )
    return receipt
