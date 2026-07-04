from decimal import Decimal
from sources.spend_guard import SpendGuard

def test_blocks_over_cap(audit):
    g = SpendGuard(audit, Decimal("100.00"), run_id="r")
    assert g.authorize("doc", "150.00", per_doc_limit=Decimal("200"), auto_approve=True) is False

def test_cumulative_enforced(audit):
    g = SpendGuard(audit, Decimal("100.00"), run_id="r")
    for _ in range(10):
        g.authorize("doc", "10.00", per_doc_limit=Decimal("10.00"), auto_approve=True)
    assert g.cumulative() == Decimal("100.00")
    # 11th $10 would exceed -> blocked
    assert g.authorize("doc", "10.00", per_doc_limit=Decimal("10.00"), auto_approve=True) is False
    assert g.cumulative() == Decimal("100.00")

def test_per_doc_limit(audit):
    g = SpendGuard(audit, Decimal("100.00"), run_id="r")
    assert g.authorize("doc","20.00", per_doc_limit=Decimal("10.00"), auto_approve=True) is False

def test_manual_approval_required(audit):
    g = SpendGuard(audit, Decimal("100.00"), run_id="r")
    assert g.authorize("doc","5.00", per_doc_limit=Decimal("10.00"), auto_approve=False) is False
