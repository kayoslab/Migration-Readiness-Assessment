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


# ---------------------------------------------------------------------------------------- fact-sheet discipline

def _assess_with(tmp_path, facts_patch=None, config_patch=None):
    import yaml as _yaml
    path = build(Scenario("checks", {}), tmp_path, INSTRUMENT)
    sheet = _yaml.safe_load((tmp_path / "facts.yaml").read_text())
    sheet.update(facts_patch or {})
    (tmp_path / "facts.yaml").write_text(_yaml.safe_dump(sheet))
    cfg = _yaml.safe_load(path.read_text())
    cfg.update(config_patch or {})
    path.write_text(_yaml.safe_dump(cfg))
    return assess(path, draws=100)


def test_clean_fact_sheet_has_no_findings(tmp_path):
    a = _assess_with(tmp_path, {"cloud_compute_baseline_annual": {"estimates": [
        {"estimator": "Platform", "low": 270000, "likely": 300000, "high": 360000, "grade": "calculator_export"},
        {"estimator": "Finance", "low": 280000, "likely": 310000, "high": 380000, "grade": "quote"}]}})
    assert not [f for f in a.fact_checks if f.severity == "problem"]


def test_sponsor_as_fact_sheet_owner_is_a_problem(tmp_path):
    a = _assess_with(tmp_path, config_patch={"people": {"sponsor": "Head of Platform", "fact_sheet_owner": "Head of Platform"}})
    assert any(f.severity == "problem" and "also the sponsor" in f.message for f in a.fact_checks)


def test_hand_entered_coupling_metric_and_wide_range_are_flagged(tmp_path):
    a = _assess_with(tmp_path, {"cross_team_change_pct": {"value": 40, "source": "estimate"},
                                "migration_cost": {"low": 100000, "likely": 300000, "high": 900000, "grade": "estimate"}})
    messages = " ".join(f.message for f in a.fact_checks)
    assert "should be produced by `mra coupling`" in messages
    assert "wider than 3x without a written justification" in messages


def test_two_estimators_use_union_and_flag_disagreement(tmp_path):
    a = _assess_with(tmp_path, {"cloud_compute_baseline_annual": {"estimates": [
        {"estimator": "Platform team", "low": 200000, "likely": 220000, "high": 260000, "grade": "calculator_export"},
        {"estimator": "Finance", "low": 300000, "likely": 340000, "high": 400000, "grade": "quote"}]}})
    fact = a.engagement.facts["cloud_compute_baseline_annual"]
    assert (fact.low, fact.high, fact.likely) == (200000, 400000, 280000)
    assert any("estimators differ" in f.message for f in a.fact_checks)


# ---------------------------------------------------------------------------------------- hybrid estates

def test_hybrid_estate_options_are_costed():
    s, problems = compute(_facts(current_cloud_share_pct=40, need_share_pct=40, sunk_commitment_cost=0), "hybrid")
    assert not problems
    assert {"tco.stay", "tco.improve_current", "tco.cloud", "tco.repatriate", "tco.hybrid"} <= set(s)
    # rebalancing to the share already in the cloud migrates nothing: it costs the same as optimising the mix
    assert s["tco_ratio.hybrid"][0] == pytest.approx(1.0, abs=0.03)


def test_hybrid_estate_with_cheap_cloud_moves_the_rest(tmp_path):
    scenario = Scenario("hybrid-cheap", {"hosting": "move_to_cloud"}, current_hosting="hybrid",
                        targets={**STEADY, **GOOD_OPS, "capability.hosting.cloud_skills": 3.5},
                        facts={"current_cloud_share_pct": 30, "ops_fte": 6, "infra_share_pct": 100,
                               "rightsized_share_pct": 95, "cloud_ops_fte": 1, "sunk_commitment_cost": 0,
                               "cloud_compute_baseline_annual": {"low": 50000, "likely": 60000, "high": 75000, "grade": "quote"},
                               "migration_months": {"low": 5, "likely": 6, "high": 8, "grade": "estimate"}})
    r = assess(build(scenario, tmp_path, INSTRUMENT), draws=DRAWS).results["hosting"]
    assert r.verdict == "move_to_cloud", (r.verdict, r.economics.get("ratio"))


def test_hybrid_estate_requires_current_share(tmp_path):
    a = assess(build(Scenario("hybrid-missing", {}, current_hosting="hybrid"), tmp_path, INSTRUMENT), draws=50)
    assert any("current_cloud_share_pct" in p for p in a.problems)
