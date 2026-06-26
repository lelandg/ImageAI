"""Phase 5b — FillPlan sequencing (pure)."""
from core.layout.fill_plan import FillPlan


def _p(rid):
    return {"region_id": rid, "prompt": f"p-{rid}", "width": 100, "height": 100}


def test_empty_plan():
    plan = FillPlan([])
    assert plan.current() is None
    assert plan.current_region_id() is None
    assert plan.done() is True
    assert plan.progress() == (0, 0)


def test_single_region_plan():
    plan = FillPlan([_p("a")])
    assert plan.current_region_id() == "a"
    assert plan.progress() == (1, 1)
    assert plan.done() is False
    assert plan.advance() is None      # nothing after the single region
    assert plan.done() is True


def test_multi_region_sequence_and_progress():
    plan = FillPlan([_p("a"), _p("b"), _p("c")])
    assert plan.current_region_id() == "a"
    assert plan.progress() == (1, 3)
    assert plan.advance()["region_id"] == "b"
    assert plan.progress() == (2, 3)
    assert plan.advance()["region_id"] == "c"
    assert plan.progress() == (3, 3)
    assert plan.done() is False
    assert plan.advance() is None
    assert plan.done() is True
    assert plan.progress() == (3, 3)   # clamps at total
