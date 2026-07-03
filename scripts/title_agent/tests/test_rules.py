"""Phase 5 tests for validators/rules.py — the six quality gates.

Each test asserts both the pass/fail decision and the failure *category*,
because the category is what enforces the Golden Law (auto-repair vs escalate).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from ..core.taxonomy import FailureCategory, is_auto_repairable
from ..validators.rules import (
    AcreageFooting,
    ChainContinuity,
    ChainInstrument,
    InstrumentLine,
    InterestConservation,
    OGLAudit,
    OGLEntry,
    SourceAudit,
    SourceProbeResult,
    TractAcreage,
    WIEntry,
)


# ---- Gate 1 ------------------------------------------------------------- #

def test_interest_conserves_and_escalates(tmp: Path) -> None:
    ic = InterestConservation()
    assert ic.check_zero_sum([0.5, -0.25, -0.25], "Tract 1 / WD").passed
    bad = ic.check_zero_sum([0.5, -0.25], "Tract 1 / WD")
    assert not bad.passed
    # Non-conservation is a substantive gap -> escalate, never auto-fix.
    assert bad.failures[0].category == FailureCategory.TITLE_GAP
    assert not is_auto_repairable(bad.failures[0].category)


# ---- Gate 2 ------------------------------------------------------------- #

def test_pro_rata_missing_formula_is_auto_repairable(tmp: Path) -> None:
    af = AcreageFooting()
    ok = af.verify_pro_rata(TractAcreage(1, gross_acres=63.742, interest_fraction=1.0, net_acres=63.742))
    assert ok.passed
    missing = af.verify_pro_rata(TractAcreage(1, 63.742, 0.5, net_acres=None))
    assert not missing.passed
    assert missing.failures[0].category == FailureCategory.MATH_FOOTING_ERROR
    assert is_auto_repairable(missing.failures[0].category)  # loop may fix
    wrong = af.verify_pro_rata(TractAcreage(1, 63.742, 0.5, net_acres=10.0))
    assert wrong.failures[0].category == FailureCategory.MATH_FOOTING_ERROR


def test_gross_total_637_42(tmp: Path) -> None:
    af = AcreageFooting()
    tracts = [TractAcreage(i, 63.742, 1.0, 63.742) for i in range(1, 11)]  # 637.42
    assert af.verify_gross_total(tracts).passed
    tracts[0] = TractAcreage(1, 60.0, 1.0, 60.0)  # total now 633.678
    bad = af.verify_gross_total(tracts)
    assert not bad.passed and bad.failures[0].category == FailureCategory.MATH_FOOTING_ERROR


# ---- Gate 3 ------------------------------------------------------------- #

def test_chain_gapless_and_break(tmp: Path) -> None:
    cc = ChainContinuity()
    good = [
        ChainInstrument(1, "USA", "John Doe", "1980-01-01"),
        ChainInstrument(2, "JOHN DOE", "Jane Roe", "1990-01-01"),
        ChainInstrument(3, "Jane Roe", "Acme LLC", "2000-01-01"),
    ]
    assert cc.check_gapless_chain(good, "Tract 1").passed
    broken = [
        ChainInstrument(1, "USA", "John Doe"),
        ChainInstrument(2, "SOMEONE ELSE", "Jane Roe"),  # grantor != prev grantee
    ]
    res = cc.check_gapless_chain(broken, "Tract 1")
    assert not res.passed and res.failures[0].category == FailureCategory.TITLE_GAP


def test_chain_chronology(tmp: Path) -> None:
    cc = ChainContinuity()
    reversed_dates = [
        ChainInstrument(1, "USA", "John Doe", "2000-01-01"),
        ChainInstrument(2, "John Doe", "Jane Roe", "1990-01-01"),  # earlier than prev
    ]
    res = cc.check_gapless_chain(reversed_dates, "Tract 1")
    assert any("Chronological" in f.detail for f in res.failures)


# ---- Gate 4 ------------------------------------------------------------- #

class _FakeProbe:
    def __init__(self, mapping): self._m = mapping
    def verify(self, line): return self._m[line.seq]


def test_source_audit_routes(tmp: Path) -> None:
    lines = [
        InstrumentLine(1, "100", "200", "WD", workbook_has_metadata=True),
        InstrumentLine(2, "101", "201", "OL", workbook_has_metadata=False),
        InstrumentLine(3, "999", "999", "WD", workbook_has_metadata=True),
        InstrumentLine(4, "102", "202", "WD", workbook_has_metadata=True),
    ]
    probe = _FakeProbe({
        1: SourceProbeResult(found=True, free_to_view=False),                 # ok
        2: SourceProbeResult(found=True, free_to_view=True),                  # metadata missing
        3: SourceProbeResult(found=False, free_to_view=False, detail="404"),  # unverified
        4: SourceProbeResult(found=True, free_to_view=True,
                             contradiction="royalty 12.5% vs 18.75%"),        # contradiction
    })
    res = SourceAudit().verify_instrument_lines(lines, probe, "Tract 1")
    cats = {f.reference.split("seq ")[1][0]: f.category for f in res.failures}
    assert cats["2"] == FailureCategory.METADATA_MISSING and is_auto_repairable(cats["2"])
    assert cats["3"] == FailureCategory.SOURCE_UNVERIFIED
    assert cats["4"] == FailureCategory.SOURCE_UNVERIFIED
    assert "1" not in cats  # verified line produced no failure


# ---- Gate 5 ------------------------------------------------------------- #

def test_ogl_parity_ok(tmp: Path) -> None:
    ogl = [OGLEntry(1, "Lessor A", royalty_decimal=0.1875)]
    wi = [
        WIEntry(1, "Owner X", wi_decimal=0.5, nri_decimal=0.5 * (1 - 0.1875)),
        WIEntry(1, "Owner Y", wi_decimal=0.5, nri_decimal=0.5 * (1 - 0.1875)),
    ]
    assert OGLAudit().validate_ogl_register(ogl, wi).passed


def test_ogl_parity_violations(tmp: Path) -> None:
    oa = OGLAudit()
    # WI sums to 0.9, not 1.0.
    ogl = [OGLEntry(1, "Lessor A", 0.1875)]
    wi = [WIEntry(1, "Owner X", 0.9, 0.9 * (1 - 0.1875))]
    res = oa.validate_ogl_register(ogl, wi)
    assert not res.passed
    assert all(f.category == FailureCategory.TITLE_GAP for f in res.failures)
    # NRI inconsistent with royalty.
    wi2 = [WIEntry(1, "Owner X", 0.5, 0.5), WIEntry(1, "Owner Y", 0.5, 0.5)]
    res2 = oa.validate_ogl_register(ogl, wi2)
    assert any("NRI" in f.detail for f in res2.failures)
    # Lease with no owners.
    res3 = oa.validate_ogl_register([OGLEntry(2, "L", 0.125)], [])
    assert not res3.passed


def _run_all() -> None:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        with tempfile.TemporaryDirectory() as d:
            fn(Path(d))
        print(f"  PASS  {fn.__name__}")
    print(f"\n{len(tests)} passed.")


if __name__ == "__main__":
    _run_all()
