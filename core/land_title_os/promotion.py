"""Canonical-file promotion system (Move #6).

Files pass through SOURCE → STAGING → EXTRACTED → RECONCILED → QA → APPROVED
→ DELIVERED, one stage at a time. A promotion happens only after every check
registered for the target stage passes; each promotion records the file hash
and writes a hash-chained receipt. This prevents an AI from silently
replacing the best workbook with a worse one.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .receipts import ReceiptLedger, RunReceipt
from .util import sha256_file, utcnow_iso

STAGES = ("SOURCE", "STAGING", "EXTRACTED", "RECONCILED", "QA", "APPROVED", "DELIVERED")

# Stages beyond which an unattended agent may not promote on its own.
HUMAN_GATE_FROM = "APPROVED"   # QA -> APPROVED and APPROVED -> DELIVERED need a human


class PromotionError(Exception):
    pass


@dataclass
class PromotionRecord:
    path: str
    sha256: str
    from_stage: str
    to_stage: str
    checks_passed: list
    approved_by: str            # agent name, or human identity for gated stages
    receipt_id: str
    timestamp: str = field(default_factory=utcnow_iso)


class PromotionEngine:
    """Tracks each file's stage in a JSON state file; receipts go to the ledger."""

    def __init__(self, state_path: str | Path, receipts: ReceiptLedger):
        self.state_path = Path(state_path)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.receipts = receipts
        self._checks: dict[str, list[tuple[str, Callable]]] = {}
        self.state: dict[str, dict] = {}
        if self.state_path.exists():
            self.state = json.loads(self.state_path.read_text(encoding="utf-8"))

    def _save(self) -> None:
        self.state_path.write_text(
            json.dumps(self.state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def register_check(self, to_stage: str, name: str, fn: Callable[[Path], bool]) -> None:
        """fn(path) -> True on pass. Checks gate entry INTO to_stage."""
        if to_stage not in STAGES:
            raise ValueError(f"unknown stage {to_stage}")
        self._checks.setdefault(to_stage, []).append((name, fn))

    def stage_of(self, path: str | Path) -> str:
        rec = self.state.get(str(Path(path).resolve()))
        return rec["stage"] if rec else "SOURCE"

    def promote(self, path: str | Path, to_stage: str, actor: str,
                human_approved: bool = False) -> PromotionRecord:
        p = Path(path).resolve()
        if not p.exists():
            raise PromotionError(f"file does not exist: {p}")
        if to_stage not in STAGES:
            raise PromotionError(f"unknown stage {to_stage}")

        current = self.stage_of(p)
        cur_i, new_i = STAGES.index(current), STAGES.index(to_stage)
        if new_i != cur_i + 1:
            raise PromotionError(
                f"illegal promotion {current} -> {to_stage}: stages may not be skipped "
                f"or reversed (expected {STAGES[cur_i + 1] if cur_i + 1 < len(STAGES) else 'none'})")

        if STAGES.index(to_stage) >= STAGES.index(HUMAN_GATE_FROM) and not human_approved:
            raise PromotionError(
                f"promotion to {to_stage} requires human approval (human_approved=True "
                f"with the approving person's name as actor)")

        passed = []
        for name, fn in self._checks.get(to_stage, []):
            try:
                ok = bool(fn(p))
            except Exception as exc:  # a crashing check is a failing check
                raise PromotionError(f"check {name!r} crashed: {exc}") from exc
            if not ok:
                raise PromotionError(f"check {name!r} failed for {p}")
            passed.append(name)

        digest = sha256_file(p)
        receipt = self.receipts.record(RunReceipt(
            agent=actor,
            action=f"promote:{current}->{to_stage}",
            files_changed=[str(p)],
            tests={"checks_passed": passed},
            confidence={},
        ))
        record = PromotionRecord(
            path=str(p), sha256=digest, from_stage=current, to_stage=to_stage,
            checks_passed=passed, approved_by=actor, receipt_id=receipt.receipt_id)
        self.state[str(p)] = {
            "stage": to_stage, "sha256": digest,
            "history": self.state.get(str(p), {}).get("history", []) + [record.__dict__],
        }
        self._save()
        return record
