"""Immutable run receipts (Move #30) — "no receipt means the work did not
officially happen."

Receipts are an append-only, hash-chained JSONL ledger: each receipt embeds
the hash of the previous one, so silent edits or deletions break the chain
and are detectable with ``verify_chain()``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

from .util import canonical_json, sha256_text, random_id, utcnow_iso

GENESIS = "0" * 64


@dataclass
class RunReceipt:
    agent: str
    action: str
    model: str = ""
    prompt_version: str = ""
    input_ids: list = field(default_factory=list)
    output_ids: list = field(default_factory=list)
    tools_used: list = field(default_factory=list)
    files_changed: list = field(default_factory=list)
    tests: dict = field(default_factory=dict)     # e.g. {"passed": 12, "failed": 0}
    errors: list = field(default_factory=list)
    confidence: dict = field(default_factory=dict)
    cost: dict = field(default_factory=dict)      # e.g. {"tokens": 1234, "usd": 0.05}
    receipt_id: str = field(default_factory=lambda: random_id("RUN"))
    timestamp: str = field(default_factory=utcnow_iso)
    prev_hash: str = GENESIS
    receipt_hash: str = ""


class ReceiptLedger:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _last_hash(self) -> str:
        if not self.path.exists():
            return GENESIS
        last = None
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                last = line
        if last is None:
            return GENESIS
        return json.loads(last)["receipt_hash"]

    def record(self, receipt: RunReceipt) -> RunReceipt:
        receipt.prev_hash = self._last_hash()
        body = asdict(receipt)
        body.pop("receipt_hash")
        receipt.receipt_hash = sha256_text(canonical_json(body))
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(receipt), ensure_ascii=False) + "\n")
        return receipt

    def verify_chain(self) -> list[str]:
        """Return a list of chain defects; empty list = intact ledger."""
        problems: list[str] = []
        prev = GENESIS
        if not self.path.exists():
            return problems
        for n, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            rec = json.loads(line)
            claimed = rec.pop("receipt_hash")
            if rec.get("prev_hash") != prev:
                problems.append(f"line {n}: prev_hash mismatch (chain broken)")
            if sha256_text(canonical_json(rec)) != claimed:
                problems.append(f"line {n}: receipt_hash invalid (content altered)")
            prev = claimed
        return problems

    def all(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(l) for l in self.path.read_text(encoding="utf-8").splitlines()
                if l.strip()]
