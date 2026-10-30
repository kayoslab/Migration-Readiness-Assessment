import sys
from dataclasses import replace
from pathlib import Path

import pytest

from mra.assess import assess
from mra.cases import HOSTING_CASES
from mra.investment import architecture, budget
from mra.scenario import build

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "examples"))
from build_techco import TECHCO  # noqa: E402


@pytest.fixture(scope="module")
def techco(tmp_path_factory):
    return assess(build(TECHCO, tmp_path_factory.mktemp("t"), ROOT / "instrument", seed=11), draws=300)


def test_architecture_investment_from_two_estimators(techco):
    inv = architecture(techco)
    assert inv["estimated"] and inv["start"] == 3.0                      # after the preconditions (prepare first)
    assert inv["cost"] == pytest.approx(44 * 100000 / 12 + 100000)       # mean of both likely values, salaried
    assert inv["cost_low"] < inv["cost"] < inv["cost_high"]
    assert inv["fte"] == pytest.approx(4.0) and inv["reference_class"] == 40


def test_budget_by_phase_adds_up(techco):
    b = budget(techco)
    arch = b["rows"][0]
    assert arch["cells"][0] == 0 and sum(arch["cells"]) == pytest.approx(arch["total"])
    refresh = next(r for r in b["rows"] if r["item"] == "Hosting: hardware refresh")
    assert refresh["cells"][-1] == pytest.approx(400000 * 0.55)          # right-sized, after month 12
    hidden = budget(techco, show_amounts=False)
    assert not any("€" in c for r in hidden["rows"] for c in r["cells_text"])


def test_reference_class_raises_the_high_estimate(tmp_path):
    facts = {**TECHCO.facts, "past_programme_overrun_pct": 100}
    a = assess(build(replace(TECHCO, facts=facts), tmp_path / "t", ROOT / "instrument", seed=11), draws=50)
    low, high = a.evidence.fact_ranges["arch_effort_person_months"]
    assert high >= 44 * 2


def test_missing_estimate_is_said_on_the_decision_page(tmp_path):
    from mra.report_v3 import build_context
    a = assess(build(HOSTING_CASES["a_steady_load_one_machine"], tmp_path / "e", ROOT / "instrument", seed=3), draws=60)
    assert a.results["architecture"].verdict == "modular_monolith"
    assert architecture(a)["estimated"] is False
    ctx = build_context(a, tmp_path / "o", ROOT)
    arch = next(r for r in ctx["brief"]["requests"] if r["decision"] == "Architecture")
    assert arch["budget"].startswith("Investment not yet estimated")
