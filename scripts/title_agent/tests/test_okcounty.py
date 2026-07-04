"""Phase 2 tests for api/okcounty.py.

Exercises CurlClient against a fake ``curl`` script placed on PATH, the
free-to-view parser across ambiguous shapes, and the $100 budget cap.
"""

from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path

from ..api.okcounty import (
    ApiKeyMissingError,
    BudgetCapReached,
    BudgetManager,
    CurlClient,
    DocumentVerifier,
)
from ..core.memory import SQLiteManager


def _mgr(tmp: Path) -> SQLiteManager:
    return SQLiteManager(tmp / "state.db")


def _install_fake_curl(tmp: Path, body: str, status: str) -> None:
    """Write a fake `curl` that ignores args, prints body + sentinel + status,
    mimicking our -w format, and prepend it to PATH."""
    bindir = tmp / "bin"
    bindir.mkdir(exist_ok=True)
    fake = bindir / "curl"
    sep = "\\n<<<TITLE_AGENT_HTTP_STATUS>>>"
    fake.write_text(
        "#!/usr/bin/env bash\n"
        f'printf "%s" {shell_quote(body)}\n'
        f'printf "{sep}%s" "{status}"\n'
    )
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC | stat.S_IRWXU)
    os.environ["PATH"] = f"{bindir}:{os.environ['PATH']}"


def shell_quote(s: str) -> str:
    return "'" + s.replace("'", "'\\''") + "'"


def test_curl_client_parses_json_and_status(tmp: Path) -> None:
    os.environ["OKCOUNTY_API_KEY"] = "test-key-123"
    _install_fake_curl(tmp, '{"results":[{"id":"D1","free_to_view":true}]}', "200")
    client = CurlClient(_mgr(tmp))
    resp = client.execute("documents/search", {"book": "100", "page": "200"})
    assert resp.status_code == 200 and resp.ok
    assert resp.json is not None and resp.json["results"][0]["id"] == "D1"


def test_curl_client_surfaces_404(tmp: Path) -> None:
    os.environ["OKCOUNTY_API_KEY"] = "test-key-123"
    _install_fake_curl(tmp, '{"error":"not found"}', "404")
    resp = CurlClient(_mgr(tmp)).execute("documents/search", {"book": "9", "page": "9"})
    assert resp.status_code == 404 and not resp.ok


def test_curl_client_requires_key(tmp: Path) -> None:
    os.environ.pop("OKCOUNTY_API_KEY", None)
    _install_fake_curl(tmp, "{}", "200")
    try:
        CurlClient(_mgr(tmp)).execute("documents/search", {})
    except ApiKeyMissingError:
        return
    raise AssertionError("missing key should raise ApiKeyMissingError")


def test_free_flag_variants(tmp: Path) -> None:
    v = DocumentVerifier()
    assert v.evaluate_free_flag({"results": [{"id": "A", "free_to_view": True}]}).free_to_view
    assert v.evaluate_free_flag({"documents": [{"id": "B", "cost": 0}]}).free_to_view
    billable = v.evaluate_free_flag({"results": [{"id": "C", "cost": 0.5}]})
    assert billable.found and not billable.free_to_view and billable.estimated_cost == 0.5
    # Ambiguous: no flag, no cost -> conservative not-free.
    amb = v.evaluate_free_flag({"results": [{"id": "D"}]})
    assert amb.found and not amb.free_to_view
    # Empty -> not found.
    assert not v.evaluate_free_flag({}).found


def test_budget_tracks_and_caps(tmp: Path) -> None:
    mgr = _mgr(tmp)
    budget = BudgetManager(mgr, cap=100.0)
    assert budget.total_spent() == 0.0
    budget.track_spend(40.0, "img-1")
    budget.track_spend(50.0, "img-2")
    assert abs(budget.total_spent() - 90.0) < 1e-9
    assert abs(budget.remaining() - 10.0) < 1e-9
    # A charge that would push to/over 100 is refused and NOT recorded.
    try:
        budget.track_spend(15.0, "img-3")
    except BudgetCapReached as exc:
        assert exc.spent == 90.0 and exc.attempted == 15.0
    else:
        raise AssertionError("cap breach should raise BudgetCapReached")
    assert abs(budget.total_spent() - 90.0) < 1e-9  # ledger unchanged


def test_budget_refuses_charge_that_reaches_cap(tmp: Path) -> None:
    # A charge bringing cumulative spend to *exactly* the cap must be refused
    # (reach-or-exceed), so the ledger never reaches or breaches the ceiling.
    budget = BudgetManager(_mgr(tmp), cap=100.0)
    budget.track_spend(95.0, "img-1")
    assert budget.would_exceed(5.0)  # 95 + 5 == 100 -> would reach the cap
    try:
        budget.track_spend(5.0, "img-2")
    except BudgetCapReached:
        pass
    else:
        raise AssertionError("a charge reaching exactly the cap must be refused")
    assert abs(budget.total_spent() - 95.0) < 1e-9  # ledger unchanged
    # A charge staying strictly under the cap is still allowed.
    budget.track_spend(4.5, "img-3")
    assert abs(budget.total_spent() - 99.5) < 1e-9


def test_budget_persists_across_instances(tmp: Path) -> None:
    mgr = _mgr(tmp)
    BudgetManager(mgr, cap=100.0).track_spend(25.0, "img-1")
    # A fresh manager on the same DB sees the prior spend.
    assert abs(BudgetManager(mgr, cap=100.0).total_spent() - 25.0) < 1e-9


def test_budget_allows_free_fetches(tmp: Path) -> None:
    budget = BudgetManager(_mgr(tmp), cap=100.0)
    status = budget.track_spend(0.0, "free-img")
    assert status.spent == 0.0 and not status.halted


def test_source_probe_caches_and_charges_once_per_document(tmp: Path) -> None:
    # The loop re-evaluates every iteration; the probe must charge the budget
    # once per distinct (book, page), not once per verify() call, or a
    # multi-pass run would consume the cap by iteration count.
    from ..api.okcounty import DocumentVerifier
    from ..core.wiring import OKCountySourceProbe
    from ..validators.rules import InstrumentLine

    class _FakeResp:
        status_code = 200
        json = {"results": [{"id": "D1", "cost": 0.5}]}  # billable

    class _FakeClient:
        def __init__(self): self.calls = 0
        def execute(self, endpoint, payload=None, method="GET"):
            self.calls += 1
            return _FakeResp()

    mgr = _mgr(tmp)
    budget = BudgetManager(mgr, cap=100.0)
    client = _FakeClient()
    probe = OKCountySourceProbe(client, DocumentVerifier(), budget)
    line = InstrumentLine(1, "100", "200", "WD")

    r1 = probe.verify(line)
    r2 = probe.verify(line)  # same document, re-verified (as the loop would)
    assert r1.found and r2.found
    assert client.calls == 1               # network hit once
    assert abs(budget.total_spent() - 0.5) < 1e-9  # charged once, not twice


def _run_all() -> None:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    saved_path = os.environ["PATH"]
    saved_key = os.environ.get("OKCOUNTY_API_KEY")
    try:
        for fn in tests:
            with tempfile.TemporaryDirectory() as d:
                fn(Path(d))
            os.environ["PATH"] = saved_path
            print(f"  PASS  {fn.__name__}")
    finally:
        os.environ["PATH"] = saved_path
        if saved_key is not None:
            os.environ["OKCOUNTY_API_KEY"] = saved_key
        else:
            os.environ.pop("OKCOUNTY_API_KEY", None)
    print(f"\n{len(tests)} passed.")


if __name__ == "__main__":
    _run_all()
