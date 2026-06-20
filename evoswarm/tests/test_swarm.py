"""Eval/unit suite — also the fixture set the EvoLoop scores candidates against."""

from __future__ import annotations

from decimal import Decimal

import pytest

from evoswarm.agents.registry import load_registry
from evoswarm.graph import build_graph
from evoswarm.oklahoma.royalty import compute_royalty, division_order_decimal
from evoswarm.schemas import Money, RoyaltyInput, SwarmState, Task, TaskStatus


def test_twelve_agents_load_and_validate():
    reg = load_registry()
    assert len(reg) == 12
    assert {a.spec.role.value for a in reg.values()} >= {"royalty_analyst", "critic"}


def test_graph_runs_to_completion():
    app = build_graph()
    state = SwarmState(task=Task(county="Oklahoma", legal="14-12N-3W", objective="t"))
    out = app.invoke(state)
    assert out.task.status in (TaskStatus.DONE, TaskStatus.NEEDS_REVIEW)
    assert len(out.history) == 10


def test_doi_decimal_known_value():
    # 20 NMA in a 640-ac section at 3/16 royalty.
    d = division_order_decimal(Decimal("20"), Decimal("640"), Decimal("0.1875"))
    assert d == Decimal("0.00585938")


def test_royalty_end_to_end():
    r = compute_royalty(RoyaltyInput(
        net_mineral_acres=Decimal("20"), spacing_unit_acres=Decimal("640"),
        royalty_rate=Decimal("0.1875"), monthly_production_bbl=Decimal("3000"),
        price_per_bbl=Money(amount=Decimal("72.50")),
    ))
    assert r.gross_monthly.amount == Decimal("217500.00")
    assert r.net_monthly.amount == Decimal("1274.42")


def test_strict_schema_rejects_unknown_field():
    with pytest.raises(Exception):
        Task.model_validate({"county": "OK", "legal": "14-12N-3W",
                             "objective": "x", "bogus": 1})


def test_strict_schema_rejects_bad_legal():
    with pytest.raises(Exception):
        Task(county="Oklahoma", legal="not-a-legal", objective="x")
