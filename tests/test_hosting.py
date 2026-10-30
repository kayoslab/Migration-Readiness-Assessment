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

GOOD_OPS = {"capability.hosting.automation": 4.0, "capability.hosting.operations": 4.0,
            "capability.hosting.cost_discipline": 3.5, "need.hosting.ops_burden": 1.5}
STEADY = {"need.hosting.elasticity": 1.3, "need.hosting.capacity_lead_time": 1.5, "need.hosting.managed_services": 1.0}

CASES = {
    # (a) head of platform wants the cloud; load is steady, one machine would do, cloud ~3x, team against
    "a_steady_load_one_machine": Scenario(
        "a", {"hosting": "improve_current"},
        targets={**STEADY, **GOOD_OPS, "capability.hosting.cloud_skills": 2.0},
        facts={"peak_to_median_load": 1.3, "rightsized_share_pct": 30, "iac_pct": 70, "single_node_sufficient": "yes",
               "cloud_compute_baseline_annual": {"low": 800000, "likely": 900000, "high": 1100000, "grade": "calculator_export"}}),
    # (b) e-commerce with 15x seasonal peaks, hardware end of life in 9 months, little infrastructure as code
    "b_peaks_eol_low_iac": Scenario(
        "b", {"hosting": "move_to_cloud"},
        targets={"need.hosting.elasticity": 4.8, "need.hosting.capacity_lead_time": 4.5,
                 "capability.hosting.automation": 2.0, "capability.hosting.operations": 2.8,
                 "capability.hosting.cloud_skills": 2.0},
        facts={"peak_to_median_load": 15, "capacity_lead_time_weeks": 10, "iac_pct": 20, "need_share_pct": 75,
               "hw_refresh_due_months": 9, "rightsized_share_pct": 95,
               "hw_maintenance_annual": 180000, "dc_cost_annual": 240000, "dr_site_annual": 120000,
               "hw_refresh_capex": 1200000, "residual_value": 300000,
               "cloud_compute_baseline_annual": {"low": 220000, "likely": 250000, "high": 300000, "grade": "calculator_export"},
               "cloud_peak_cost_annual": 150000, "migration_months": {"low": 12, "likely": 14, "high": 20, "grade": "estimate"}}),
    # (c) SaaS already in the cloud, steady load, cloud bill several times colocation, three platform engineers
    "c_saas_cloud_overpaying": Scenario(
        "c", {"hosting": "repatriate"},
        targets={**STEADY, "capability.hosting.automation": 4.2, "capability.hosting.onprem_ops": 1.2},
        current_hosting="cloud",
        facts={"peak_to_median_load": 1.4, "need_share_pct": 10, "rightsized_share_pct": 70, "infra_oncall_people": 3,
               "target_model": "managed_dedicated", "ops_fte": 3, "infra_share_pct": 50,
               "cloud_compute_baseline_annual": {"low": 550000, "likely": 600000, "high": 680000, "grade": "invoice"},
               "cloud_committed_share_pct": 20, "cloud_ops_fte": 2,
               "hw_maintenance_annual": 30000, "dc_cost_annual": 60000, "network_transit_annual": 15000,
               "dr_site_annual": 25000, "licence_cost_annual": 10000, "hw_refresh_capex": 250000, "residual_value": 80000,
               "migration_cost": {"low": 120000, "likely": 150000, "high": 250000, "grade": "estimate"},
               "migration_months": {"low": 5, "likely": 6, "high": 9, "grade": "estimate"},
               "sunk_commitment_cost": 0, "cloud_commitment_end_months": 0}),
    # (d) regulated bank: in-country residency, mixed load, strong operations, cloud dearer
    "d_regulated_strong_ops": Scenario(
        "d", {"hosting": "stay_as_is"},
        targets={"need.hosting.elasticity": 2.5, "need.hosting.capacity_lead_time": 2.0, **GOOD_OPS,
                 "capability.hosting.onprem_ops": 4.5},
        facts={"hosting_constraint": "in_country", "peak_to_median_load": 2.5, "iac_pct": 85, "infra_bus_factor": 5,
               "rightsized_share_pct": 95}),
    # (e) media company: global low-latency delivery for a small part of the estate, steady core
    "e_global_reach_partial": Scenario(
        "e", {"hosting": "hybrid"},
        targets={**STEADY, **GOOD_OPS, "need.hosting.managed_services": 4.0},
        # global delivery is bought as CDN/edge capacity: no compute moves, so no interconnect, little migration
        facts={"regions_required": 4, "managed_services_required": 2, "need_share_pct": 10, "accepted_premium_pct": 15,
               "rightsized_share_pct": 95, "peak_to_median_load": 1.5, "hybrid_interconnect_annual": 0,
               "hybrid_overhead_fte": 0.2, "training_hiring_cost": 10000}),
    # symmetry: no specific need, but the cloud is clearly cheaper and pays back quickly → cost-motivated move
    "f_cloud_clearly_cheaper": Scenario(
        "f", {"hosting": "move_to_cloud"},
        targets={**STEADY, **GOOD_OPS, "capability.hosting.cloud_skills": 3.5},
        facts={"ops_fte": 6, "infra_share_pct": 100, "hw_maintenance_annual": 200000, "dc_cost_annual": 260000,
               "dr_site_annual": 140000, "hw_refresh_capex": 900000, "hw_refresh_due_months": 14, "rightsized_share_pct": 95,
               "cloud_compute_baseline_annual": {"low": 180000, "likely": 200000, "high": 240000, "grade": "quote"},
               "cloud_ops_fte": 2, "migration_cost": {"low": 150000, "likely": 180000, "high": 260000, "grade": "quote"},
               "migration_months": {"low": 5, "likely": 6, "high": 9, "grade": "estimate"}}),
}

EXPECTED_STATUS = {"b_peaks_eol_low_iac": "prepare_first", "c_saas_cloud_overpaying": "prepare_first"}


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
