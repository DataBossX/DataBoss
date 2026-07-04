"""The Perfection Loop (Component 8) — deterministic control state machine.

run() ingests a workbook, snapshots v0, then loops:
    recalc -> validate -> classify -> route (SAFE / NEEDS_SOURCE / UNSAFE)
    -> apply SAFE fixes -> emit next version -> repeat
until all gates pass (CERTIFIED) or an unsafe/no-progress/escalation condition
halts the loop (ESCALATED). The loop never fabricates title data.
"""
from __future__ import annotations

import hashlib
import shutil
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from . import config
from .ingestion.workbook_map import WorkbookMapper, WorkbookModel
from .memory import db
from .memory.audit_log import AuditLog
from .memory.spend_ledger import SpendLedger
from .models import (
    AuditEntry,
    EscalationTicket,
    Failure,
    LoopState,
    RiskClass,
    Scorecard,
)
from .repair.recalc_engine import RecalcEngine
from .repair.safe_fixes import SafeFixRegistry
from .repair.taxonomy import FailureTaxonomy
from .repair.xml_surgery import XmlWorkbook
from .validation import default_suite


@dataclass
class LoopOutcome:
    run_id: str
    state: LoopState
    iterations: int
    final_version: int
    final_path: Path
    scorecard: Optional[Scorecard]
    escalations: list[EscalationTicket] = field(default_factory=list)


class PerfectionLoop:
    def __init__(
        self,
        source_path: str | Path,
        recalc: Optional[RecalcEngine] = None,
        registry: Optional[SafeFixRegistry] = None,
    ) -> None:
        self._source = Path(source_path)
        self._run_id = uuid.uuid4().hex[:12]
        self._workdir = config.ensure_output_dir() / self._run_id
        self._workdir.mkdir(parents=True, exist_ok=True)
        self._conn = db.get_connection(self._workdir / "run.db")
        db.init_schema(self._conn)
        self._audit = AuditLog(self._conn, self._run_id)
        self._ledger = SpendLedger(self._conn, self._run_id)
        self._recalc = recalc or RecalcEngine()
        self._registry = registry or SafeFixRegistry()
        self._suite = default_suite()

    @property
    def run_id(self) -> str:
        return self._run_id

    # -- public ----------------------------------------------------------- #
    def run(self, max_iterations: int = config.MAX_ITERATIONS) -> LoopOutcome:
        self._conn.execute(
            "INSERT INTO runs(run_id, source_path, created_ts, state) VALUES(?,?,?,?)",
            (self._run_id, str(self._source),
             datetime.now(timezone.utc).isoformat(), LoopState.INGESTED.value),
        )
        self._conn.commit()

        version = 0
        current = self._snapshot(self._source, version, parent=None)
        self._log("orchestrator", "ingest", "v0 snapshot", coord=None)

        prev_fail_sig: Optional[frozenset[str]] = None
        no_progress = 0
        escalations: list[EscalationTicket] = []
        scorecard: Optional[Scorecard] = None

        for iteration in range(1, max_iterations + 1):
            model = WorkbookMapper.load(current)
            outcome = self._recalc.recalc(current)
            if not outcome.ok:
                # Formula errors are SAFE-fixable via force recalc once; if they
                # persist, escalate as XML damage.
                self._log("recalc", "formula_errors",
                          f"{len(outcome.errors)} errors", coord=None)
            results, scorecard = self._suite.run_all(model, outcome.values)
            for r in results:
                self._audit.record_validation(version, r)

            if scorecard.all_pass and outcome.ok:
                self._set_state(LoopState.CERTIFIED)
                self._log("orchestrator", "certified",
                          f"all gates pass at v{version}", coord=None)
                return LoopOutcome(self._run_id, LoopState.CERTIFIED, iteration,
                                   version, current, scorecard, escalations)

            failures = [FailureTaxonomy.to_failure(r, i)
                        for i, r in enumerate(results) if not r.passed]
            fail_sig = frozenset(f"{f.gate.value}:{f.coord}:{f.detail[:40]}"
                                 for f in failures)

            safe, needs_source, unsafe = self._route(results, failures, model)

            # No-progress guard.
            if prev_fail_sig is not None and fail_sig == prev_fail_sig and not safe:
                escalations.append(self._escalate(
                    version, failures, "no-progress: identical failure set, "
                    "no SAFE fix available"))
                self._set_state(LoopState.ESCALATED)
                return LoopOutcome(self._run_id, LoopState.ESCALATED, iteration,
                                   version, current, scorecard, escalations)
            prev_fail_sig = fail_sig

            if unsafe:
                escalations.append(self._escalate(
                    version, unsafe, "unsafe failures require examiner judgment"))
                self._set_state(LoopState.ESCALATED)
                return LoopOutcome(self._run_id, LoopState.ESCALATED, iteration,
                                   version, current, scorecard, escalations)

            if not safe:
                # Only source-needing / already-highlighted items remain.
                escalations.append(self._escalate(
                    version, needs_source,
                    "remaining gaps need source images (okcr/OCC) — degrade to "
                    "escalation; loop will not fabricate title data"))
                self._set_state(LoopState.ESCALATED)
                return LoopOutcome(self._run_id, LoopState.ESCALATED, iteration,
                                   version, current, scorecard, escalations)

            # Apply SAFE fixes -> emit next version.
            self._set_state(LoopState.REPAIRING)
            xw = XmlWorkbook.open(current)
            for fix in safe:
                self._apply(xw, fix)
                self._audit.record_fix(version + 1, fix)
            xw.drop_calc_chain()
            xw.force_full_calc()
            version += 1
            nxt = self._workdir / f"report_v{version}.xlsx"
            xw.save_as(nxt)
            self._register_version(nxt, version, parent=version - 1)
            current = nxt

        # Iteration budget exhausted.
        escalations.append(self._escalate(
            version, [], f"iteration budget {max_iterations} exhausted"))
        self._set_state(LoopState.HALTED)
        return LoopOutcome(self._run_id, LoopState.HALTED, max_iterations,
                           version, current, scorecard, escalations)

    # -- routing ---------------------------------------------------------- #
    def _route(self, results, failures, model):
        safe, needs_source, unsafe = [], [], []
        for r in results:
            if r.passed:
                continue
            _, risk = FailureTaxonomy.classify(r)
            failure = FailureTaxonomy.to_failure(r, 0)
            if risk == RiskClass.SAFE:
                plan = self._registry.plan_for(failure, model)
                if plan is not None:
                    safe.append(plan)
                else:
                    unsafe.append(failure)
            elif risk == RiskClass.NEEDS_SOURCE:
                needs_source.append(failure)
            else:
                unsafe.append(failure)
        return safe, needs_source, unsafe

    def _apply(self, xw: XmlWorkbook, fix) -> None:
        # SAFE fixes are cell writes or highlight toggles; force_full_calc handled
        # separately. Only act on plans with a concrete target+after value.
        if fix.strategy_id == "force_full_calc":
            return  # handled by drop_calc_chain/force_full_calc after the loop
        if isinstance(fix.after, str) and fix.after.startswith("HIGHLIGHT:"):
            on = fix.after.endswith("ON")
            xw.set_highlight(fix.target.sheet, fix.target.cell, on)
        else:
            xw.set_cell(fix.target.sheet, fix.target.cell, fix.after)

    # -- persistence helpers --------------------------------------------- #
    def _snapshot(self, src: Path, version: int, parent: Optional[int]) -> Path:
        dst = self._workdir / f"report_v{version}.xlsx"
        shutil.copy(src, dst)
        self._register_version(dst, version, parent)
        return dst

    def _register_version(self, path: Path, version: int, parent: Optional[int]) -> None:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        self._conn.execute(
            "INSERT OR IGNORE INTO versions(version, run_id, path, sha256, created_ts, parent_version) "
            "VALUES(?,?,?,?,?,?)",
            (version, self._run_id, str(path), digest,
             datetime.now(timezone.utc).isoformat(), parent),
        )
        self._conn.commit()

    def _escalate(self, version: int, failures: list[Failure], reason: str) -> EscalationTicket:
        gate = failures[0].gate if failures else list(self._suite._validators)[0].gate
        cat = failures[0].category if failures else None
        self._conn.execute(
            "INSERT INTO escalations(ts, run_id, version, gate, category, reason, payload) "
            "VALUES(?,?,?,?,?,?,?)",
            (datetime.now(timezone.utc).isoformat(), self._run_id, version,
             gate.value, cat.value if cat else "", reason,
             "; ".join(f.detail for f in failures[:20])),
        )
        self._conn.commit()
        from .models import FailureCategory
        return EscalationTicket(
            run_id=self._run_id, gate=gate,
            category=cat or FailureCategory.XML_DAMAGE,
            reason=reason, version=version, failures=failures,
        )

    def _set_state(self, state: LoopState) -> None:
        self._conn.execute(
            "INSERT INTO runs(run_id, source_path, created_ts, state) VALUES(?,?,?,?) "
            "ON CONFLICT(run_id) DO UPDATE SET state=excluded.state",
            (self._run_id, str(self._source),
             datetime.now(timezone.utc).isoformat(), state.value),
        )
        self._conn.commit()

    def _log(self, actor: str, action: str, result: str, coord) -> None:
        self._audit.record(AuditEntry(
            run_id=self._run_id, actor=actor, action=action, result=result, coord=coord))

    @property
    def conn(self):
        return self._conn
