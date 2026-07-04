"""Phase 6 tests for core/loop.py — the Perfection Loop and Taxonomy Router.

Drives the state machine with in-memory fakes: a scripted evaluator that
returns a queue of failure sets (one per iteration) and a repairer that writes
real bytes to each minted version so version progression and the no-overwrite
rule are exercised end to end.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Sequence

from ..core.loop import (
    LoopState,
    PerfectionLoop,
    Repairer,
    TaxonomyRouter,
)
from ..core.memory import ArtifactVersion, EscalationStore, SQLiteManager, VersionController
from ..core.taxonomy import FailureCategory, Gate
from ..validators.rules import Failure


def _fail(cat: FailureCategory, ref: str = "Tract 1") -> Failure:
    return Failure(gate=Gate.ACREAGE_FOOTING, category=cat, reference=ref, detail="x")


def _vn(version: "ArtifactVersion | None") -> int:
    assert version is not None
    return version.version_number


class _ScriptedEvaluator:
    """Returns each queued failure set in turn, then all-pass forever."""

    def __init__(self, script: list[list[Failure]]) -> None:
        self._script = script
        self.calls = 0

    def evaluate(self, version: ArtifactVersion) -> Sequence[Failure]:
        self.calls += 1
        if self._script:
            return self._script.pop(0)
        return []


class _WritingRepairer:
    """Writes a real file to the minted version path (proving no-overwrite)."""

    def __init__(self) -> None:
        self.applied: list[str] = []

    def apply(self, failures, old_version, new_version) -> None:
        assert not new_version.file_path.exists()  # mint handed us a fresh path
        new_version.file_path.write_text(f"repaired from {old_version.version_label}")
        self.applied.append(new_version.version_label)


def _setup(tmp: Path):
    mgr = SQLiteManager(tmp / "state.db")
    vc = VersionController(mgr, workbook_dir=tmp / "wb")
    v1 = vc.mint_new_version("report", reason="init")
    v1.file_path.write_text("original")
    return mgr, vc


def _loop(mgr, vc, evaluator, repairer, **kw) -> PerfectionLoop:
    # Inject the tmp-scoped VersionController so nothing touches the real
    # config.WORKBOOK_DIR.
    return PerfectionLoop(mgr, "report", evaluator, repairer, versions=vc, **kw)


def test_router_splits_categories(tmp: Path) -> None:
    router = TaxonomyRouter()
    d = router.route([
        _fail(FailureCategory.MATH_FOOTING_ERROR),
        _fail(FailureCategory.TITLE_GAP),
        _fail(FailureCategory.METADATA_MISSING),
        _fail(FailureCategory.SOURCE_UNVERIFIED),
    ])
    assert len(d.auto_repairs) == 2 and len(d.escalations) == 2
    assert d.has_escalations and d.has_auto_repairs


def test_certifies_immediately_when_clean(tmp: Path) -> None:
    mgr, vc = _setup(tmp)
    loop = _loop(mgr, vc, _ScriptedEvaluator([]), _WritingRepairer())
    outcome = loop.run()
    assert outcome.state == LoopState.CERTIFIED
    assert outcome.iterations == 1
    assert _vn(outcome.final_version) == 1  # no repair needed


def test_auto_repairs_then_certifies(tmp: Path) -> None:
    mgr, vc = _setup(tmp)
    evaluator = _ScriptedEvaluator([
        [_fail(FailureCategory.MATH_FOOTING_ERROR)],  # iter 1 -> repair -> v2
        [_fail(FailureCategory.XML_STATE_ERROR)],     # iter 2 -> repair -> v3
        [],                                           # iter 3 -> certified
    ])
    repairer = _WritingRepairer()
    loop = _loop(mgr, vc, evaluator, repairer)
    outcome = loop.run()
    assert outcome.state == LoopState.CERTIFIED
    assert outcome.iterations == 3
    assert _vn(outcome.final_version) == 3  # v1 + two repairs
    assert repairer.applied == ["_v002", "_v003"]
    # Every version file exists and nothing was overwritten.
    assert vc.get_latest_version("report").version_number == 3


def test_escalation_halts_and_opens_queue(tmp: Path) -> None:
    mgr, vc = _setup(tmp)
    evaluator = _ScriptedEvaluator([
        [_fail(FailureCategory.MATH_FOOTING_ERROR), _fail(FailureCategory.TITLE_GAP, "Tract 3")],
    ])
    loop = _loop(mgr, vc, evaluator, _WritingRepairer())
    outcome = loop.run()
    # A single Category B failure halts the whole pass — even alongside an
    # auto-repairable one. No repair version is minted on a halt.
    assert outcome.state == LoopState.ESCALATED
    assert outcome.iterations == 1
    assert _vn(outcome.final_version) == 1
    store = EscalationStore(mgr)
    open_escs = store.list_open()
    assert len(open_escs) == 1 and open_escs[0].category == "TITLE_GAP"


def test_examiner_resolution_resumes_to_certified(tmp: Path) -> None:
    mgr, vc = _setup(tmp)
    # First pass escalates on a title gap.
    evaluator = _ScriptedEvaluator([[_fail(FailureCategory.TITLE_GAP, "Tract 3")]])
    repairer = _WritingRepairer()
    loop = _loop(mgr, vc, evaluator, repairer)
    first = loop.run()
    assert first.state == LoopState.ESCALATED
    esc_id = first.escalations[0].id

    # Examiner supplies the missing Book/Page; agent applies it -> v2.
    loop.apply_examiner_resolution(
        esc_id, examiner_id="examiner-7",
        resolution="Book 412/Page 89 supplies the missing conveyance",
        repairer=repairer, failures=[_fail(FailureCategory.TITLE_GAP, "Tract 3")],
    )
    # The queued evaluator is now empty -> next run certifies from v2.
    second = loop.run()
    assert second.state == LoopState.CERTIFIED
    assert _vn(second.final_version) == 2
    # Escalation is closed and an EXAMINER_OVERRIDE was audited.
    assert EscalationStore(mgr).list_open() == []
    from ..core.memory import AuditLogger
    overrides = AuditLogger(mgr).read_all(action=AuditLogger.EXAMINER_OVERRIDE)
    assert overrides and overrides[0].actor == "examiner-7"


def test_stalled_repair_escalates(tmp: Path) -> None:
    # A Category A failure the repairer never actually clears (same signature
    # every pass) must escalate, not spin silently to MAX_ITERATIONS.
    mgr, vc = _setup(tmp)

    class _Stuck:
        def evaluate(self, version):
            return [_fail(FailureCategory.METADATA_MISSING, "Tract 1 seq 2")]
    loop = _loop(mgr, vc, _Stuck(), _WritingRepairer(), max_iterations=50)
    outcome = loop.run()
    assert outcome.state == LoopState.ESCALATED
    assert outcome.iterations == 2  # iter1 repairs, iter2 sees no change -> escalate
    assert any(e.category == "METADATA_MISSING" for e in outcome.escalations)


def test_repairer_failure_escalates_and_leaves_no_phantom_version(tmp: Path) -> None:
    # A repairer that raises must not crash the loop or wedge a fileless "latest"
    # version — it escalates and the latest version stays v1.
    mgr, vc = _setup(tmp)

    class _Boom:
        def apply(self, failures, old_version, new_version):
            raise RuntimeError("surgery blew up")

    evaluator = _ScriptedEvaluator([[_fail(FailureCategory.MATH_FOOTING_ERROR)]])
    loop = _loop(mgr, vc, evaluator, _Boom())
    outcome = loop.run()
    assert outcome.state == LoopState.ESCALATED
    latest = vc.get_latest_version("report")
    assert latest is not None and latest.version_number == 1  # no phantom v2
    assert latest.file_path.exists()


def test_repairer_writes_then_fails_fully_rolls_back(tmp: Path) -> None:
    # If the repairer writes the file and THEN fails (e.g. recalc raises), the
    # partial file and its version row are both removed — latest stays v1.
    mgr, vc = _setup(tmp)

    class _WriteThenBoom:
        def apply(self, failures, old_version, new_version):
            new_version.file_path.write_text("partially repaired")  # file now exists
            raise RuntimeError("recalc blew up after save")

    evaluator = _ScriptedEvaluator([[_fail(FailureCategory.MATH_FOOTING_ERROR)]])
    loop = _loop(mgr, vc, evaluator, _WriteThenBoom())
    outcome = loop.run()
    assert outcome.state == LoopState.ESCALATED
    latest = vc.get_latest_version("report")
    assert latest is not None and latest.version_number == 1  # v2 fully rolled back
    assert not (tmp / "wb" / "report_v002.xlsx").exists()  # partial file removed


def test_failed_examiner_resolution_keeps_escalation_open(tmp: Path) -> None:
    # If the repair for an Examiner resolution fails, the escalation must stay
    # OPEN so it can be retried — not left closed with no corrected version.
    mgr, vc = _setup(tmp)
    evaluator = _ScriptedEvaluator([[_fail(FailureCategory.TITLE_GAP, "Tract 3")]])
    loop = _loop(mgr, vc, evaluator, _WritingRepairer())
    first = loop.run()
    assert first.state == LoopState.ESCALATED
    esc_id = first.escalations[0].id

    class _Boom:
        def apply(self, failures, old_version, new_version):
            raise RuntimeError("could not apply the verified fact")

    try:
        loop.apply_examiner_resolution(
            esc_id, "examiner-1", "Book 5/Page 9", _Boom(),
            [_fail(FailureCategory.TITLE_GAP, "Tract 3")])
    except RuntimeError:
        pass
    else:
        raise AssertionError("a failed resolution repair should propagate")
    # Escalation is still open and retryable; latest version unchanged.
    still_open = EscalationStore(mgr).list_open()
    assert len(still_open) == 1 and still_open[0].id == esc_id
    latest = vc.get_latest_version("report")
    assert latest is not None and latest.version_number == 1

    # Retry with a working repairer now succeeds and closes the escalation.
    loop.apply_examiner_resolution(
        esc_id, "examiner-1", "Book 5/Page 9", _WritingRepairer(),
        [_fail(FailureCategory.TITLE_GAP, "Tract 3")])
    assert not EscalationStore(mgr).list_open()
    assert vc.get_latest_version("report").version_number == 2


def test_oscillating_repairs_escalate_before_cap(tmp: Path) -> None:
    # A repair that oscillates between two failure sets (A -> B -> A -> ...) is
    # not caught by a consecutive-only stall check, but the seen-signature set
    # detects the cycle and escalates well before MAX_ITERATIONS.
    mgr, vc = _setup(tmp)

    class _Oscillate:
        def __init__(self): self.n = 0
        def evaluate(self, version):
            self.n += 1
            cat = FailureCategory.MATH_FOOTING_ERROR if self.n % 2 else FailureCategory.XML_STATE_ERROR
            return [_fail(cat, "Tract 1")]
    loop = _loop(mgr, vc, _Oscillate(), _WritingRepairer(), max_iterations=50)
    outcome = loop.run()
    assert outcome.state == LoopState.ESCALATED
    # iter1 sig A (new), iter2 sig B (new), iter3 sig A (seen) -> escalate.
    assert outcome.iterations == 3
    assert EscalationStore(mgr).list_open()


def test_max_iterations_guard(tmp: Path) -> None:
    mgr, vc = _setup(tmp)
    # A never-converging stream whose signature *changes* each pass (so stall
    # detection doesn't fire) must still be bounded by the iteration cap.
    class _EverChanging:
        def __init__(self): self.n = 0
        def evaluate(self, version):
            self.n += 1
            return [_fail(FailureCategory.MATH_FOOTING_ERROR, f"Tract {self.n}")]
    loop = _loop(mgr, vc, _EverChanging(), _WritingRepairer(), max_iterations=5)
    outcome = loop.run()
    assert outcome.state == LoopState.MAX_ITERATIONS
    assert outcome.iterations == 5
    # Hitting the cap must still queue the outstanding work for a human, not
    # abandon the workbook with only an audit line.
    assert len(outcome.escalations) >= 1
    assert EscalationStore(mgr).list_open()


def _run_all() -> None:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        with tempfile.TemporaryDirectory() as d:
            fn(Path(d))
        print(f"  PASS  {fn.__name__}")
    print(f"\n{len(tests)} passed.")


if __name__ == "__main__":
    _run_all()
