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


def test_max_iterations_guard(tmp: Path) -> None:
    mgr, vc = _setup(tmp)
    # An auto-repairable failure that never clears would loop forever without
    # the cap.
    class _Always:
        def evaluate(self, version): return [_fail(FailureCategory.MATH_FOOTING_ERROR)]
    loop = _loop(mgr, vc, _Always(), _WritingRepairer(), max_iterations=5)
    outcome = loop.run()
    assert outcome.state == LoopState.MAX_ITERATIONS
    assert outcome.iterations == 5


def _run_all() -> None:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        with tempfile.TemporaryDirectory() as d:
            fn(Path(d))
        print(f"  PASS  {fn.__name__}")
    print(f"\n{len(tests)} passed.")


if __name__ == "__main__":
    _run_all()
