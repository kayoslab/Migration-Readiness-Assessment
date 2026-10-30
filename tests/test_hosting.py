"""Hosting decision and TCO model: the hosting reviewer's walk-through cases plus model mechanics."""

from pathlib import Path

import numpy as np
import pytest

from mra.assess import assess
from mra.scenario import HOSTING_FACTS, Scenario, build
from mra.tco import compute

ROOT = Path(__file__).resolve().parents[1]
INSTRUMENT = ROOT / "instrument"
DRAWS = 300

from mra.cases import GOOD_OPS, HOSTING_CASES as CASES, HOSTING_STATUS as EXPECTED_STATUS, STEADY


@pytest.fixture(scope="module")
def results(tmp_path_factory):
    return {k: (s, assess(build(s, tmp_path_factory.mktemp(k), INSTRUMENT), draws=DRAWS)) for k, s in CASES.items()}


@pytest.mark.parametrize("case", list(CASES))
def test_hosting_case(results, case):
    scenario, a = results[case]
    r = a.results["hosting"]
    assert not a.problems, a.problems
    assert r.verdict == scenario.expected["hosting"], (r.verdict, r.distribution, r.economics.get("ratio"))
    assert r.status == EXPECTED_STATUS.get(case, "go"), (r.status, r.unmet_capabilities, r.hard_stops)


def test_b_capability_gap_has_improve_interim(results):
    r = results["b_peaks_eol_low_iac"][1].results["hosting"]
    assert any("automation" in u for u in r.unmet_capabilities)
    assert r.interim == "improve_current"


def test_c_cloud_optimisation_is_interim_step(results):
    r = results["c_saas_cloud_overpaying"][1].results["hosting"]
    assert r.interim == "improve_current"
    assert r.economics["ratio"]["repatriate"] < 0.85


def test_a_reports_right_sizing_saving(results):
    r = results["a_steady_load_one_machine"][1].results["hosting"]
    assert r.economics["ratio"]["improve_current"] < 0.85
    assert r.economics["ratio"]["cloud"] > 2


def test_legal_prohibition_excludes_cloud_and_reports_it(tmp_path):
    s = CASES["b_peaks_eol_low_iac"]
    blocked = Scenario("b-own-premises", {"hosting": "improve_current"}, s.targets, s.labels,
                       {**s.facts, "hosting_constraint": "own_premises_only"})
    r = assess(build(blocked, tmp_path, INSTRUMENT), draws=DRAWS).results["hosting"]
    assert r.verdict == "improve_current"
    assert any(e.startswith("move_to_cloud") for e in r.excluded)
    assert any("specific hosting need" in n for n in r.notes)     # the unmet need is reported, with its cost


# ---------------------------------------------------------------------------------------- model mechanics

def _facts(**overrides):
    point = {k: (v["likely"] if isinstance(v, dict) else v) for k, v in HOSTING_FACTS.items()
             if not isinstance(v, str)}
    point.update(overrides)
    return {k: np.array([float(v)]) for k, v in point.items()}


def test_cloud_costs_drive_the_ratio():
    base, _ = compute(_facts(), "own_infrastructure")
    dearer, _ = compute(_facts(cloud_compute_baseline_annual=600000), "own_infrastructure")
    assert dearer["tco_ratio.cloud"][0] > base["tco_ratio.cloud"][0]


def test_commitment_discount_applies_to_baseline_only():
    def peak_increment(discount):
        lo, _ = compute(_facts(cloud_peak_cost_annual=0, cloud_commit_discount_pct=discount), "own_infrastructure")
        hi, _ = compute(_facts(cloud_peak_cost_annual=200000, cloud_commit_discount_pct=discount), "own_infrastructure")
        return hi["tco.cloud"][0] - lo["tco.cloud"][0]
    # peak usage is paid on demand whatever the commitment discount
    assert peak_increment(35) > 0
    assert peak_increment(60) == pytest.approx(peak_increment(35), rel=1e-9)


def test_bridge_cost_only_when_hardware_ends_before_cut_over():
    early, _ = compute(_facts(hw_refresh_due_months=6, migration_months=12), "own_infrastructure")
    late, _ = compute(_facts(hw_refresh_due_months=24, migration_months=12), "own_infrastructure")
    none, _ = compute(_facts(hw_refresh_due_months=6, migration_months=12, bridge_cost=0), "own_infrastructure")
    assert early["tco.cloud"][0] > none["tco.cloud"][0]
    assert late["tco.cloud"][0] == pytest.approx(compute(_facts(hw_refresh_due_months=24, migration_months=12,
                                                                bridge_cost=0), "own_infrastructure")[0]["tco.cloud"][0])


def test_payback_never_when_option_is_dearer():
    s, _ = compute(_facts(cloud_compute_baseline_annual=2000000), "own_infrastructure")
    assert np.isinf(s["payback_months.cloud"][0])
    assert s["tco_saving_fte.cloud"][0] < 0


def test_missing_input_is_reported_not_guessed():
    facts = _facts()
    del facts["cloud_ops_fte"]
    signals, problems = compute(facts, "own_infrastructure")
    assert signals == {} and "cloud_ops_fte" in problems[0]


def test_correlated_overruns(tmp_path):
    a = assess(build(Scenario("corr", {}), tmp_path, INSTRUMENT), draws=2000)
    cost, months = a.evidence.signals["fact.migration_cost"], a.evidence.signals["fact.migration_months"]
    assert np.corrcoef(cost, months)[0, 1] > 0.9
