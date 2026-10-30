"""v3 decision engine: unit tests and the expert panel's walk-through cases with known correct outcomes."""

from pathlib import Path

import pytest
import yaml

from mra.assess import assess
from mra.decision import Context, evaluate, within_reach
from mra.instrument import load_instrument, validate
from mra.scenario import Scenario, build

ROOT = Path(__file__).resolve().parents[1]
INSTRUMENT = ROOT / "instrument"
DRAWS = 300

# ---------------------------------------------------------------------------------------- shared scenario parts
STRONG_CAPABILITY = {
    "capability.architecture.delivery_pipeline": 4.3, "capability.architecture.platform_basics": 4.5,
    "capability.architecture.platform_distribution": 4.5, "capability.architecture.operations": 4.5,
    "capability.architecture.data": 4.0, "fit.domain_ownership": 4.5, "fit.distributed_operations": 4.4,
    "requirement.consistency_tolerance": 4.0,
}
STRONG_CAPABILITY_FACTS = {
    "deploy_automation": "automatic_on_merge", "test_automation_pct": 88, "change_failure_pct": 6, "rollback_minutes": 5,
    "platform_basics_count": 4, "provision_days": 0.5, "oncall_model": "owning_team", "module_single_owner_pct": 90,
    "domain_map": "current", "degraded_mode_features": "yes", "acceptable_run_cost_increase_pct": 35,
}
HIGH_DIFFUSE_NEED = {"need.architecture.coupling": 4.5, "need.architecture.business_impact": 4.0,
                     "need.architecture.cognitive_load": 4.0, "locality.concentration": 2.0}
HIGH_DIFFUSE_NEED_FACTS = {"teams_per_deployable": 15, "cross_team_change_pct": 40, "blast_radius_pct": 30,
                           "friction_concentration_index": 1.2}
LOW_NEED = {"need.architecture.coupling": 1.5, "need.architecture.business_impact": 1.6,
            "need.architecture.cognitive_load": 1.5, "locality.concentration": 2.0}
LOW_NEED_FACTS = {"teams_per_deployable": 2, "cross_team_change_pct": 5, "blast_radius_pct": 8}

CASES = {
    # (a) 25 engineers, 3 teams, CAB approvals, manual QA, little contention
    "a_small_team_process_waits": Scenario(
        "a", {"architecture": "stay_and_improve"},
        targets={**LOW_NEED, "capability.architecture.delivery_pipeline": 1.8},
        labels={"AN01": "Approvals (e.g. change advisory board)"},
        facts={**LOW_NEED_FACTS, "teams_per_deployable": 3, "deploy_automation": "manual_steps",
               "rollback_minutes": 180, "test_automation_pct": 20, "change_failure_pct": 28}),
    # (b) 15 teams on one deployable, strong platform, but 45% shared tables
    "b_coupled_shared_data": Scenario(
        "b", {"architecture": "modular_monolith"},
        targets={**HIGH_DIFFUSE_NEED, **STRONG_CAPABILITY, "capability.architecture.data": 2.0},
        labels={"AN01": "Waiting for a release window or release train"},
        facts={**HIGH_DIFFUSE_NEED_FACTS, **STRONG_CAPABILITY_FACTS, "shared_tables_pct": 45,
               "cross_module_transactions": 15}),
    # (c) as (b) with separable data, self-service platform, team-owned on-call, cost within tolerance
    "c_ready_to_decompose": Scenario(
        "c", {"architecture": "broad_decomposition"},
        targets={**HIGH_DIFFUSE_NEED, **STRONG_CAPABILITY},
        labels={"AN01": "Coordinating with other teams' changes"},
        facts={**HIGH_DIFFUSE_NEED_FACTS, **STRONG_CAPABILITY_FACTS, "shared_tables_pct": 12,
               "cross_module_transactions": 2}),
    # (d) payment component in PCI scope causing incidents; otherwise healthy
    "d_pci_component": Scenario(
        "d", {"architecture": "targeted_extraction"},
        targets={"need.architecture.coupling": 2.6, "need.architecture.business_impact": 2.5,
                 "capability.architecture.delivery_pipeline": 3.8, "capability.architecture.platform_basics": 4.0,
                 "fit.distributed_operations": 3.6},
        facts={"teams_per_deployable": 6, "cross_team_change_pct": 14, "components_distinct_compliance": 1,
               "components_distinct_load": 1, "candidate_scope_in_main_deployable": "yes",
               "candidate_incident_share_pct": 45, "candidate_scaling_cost_share_pct": 30,
               "candidate_shared_tables_pct": 4, "rollback_minutes": 8, "platform_basics_count": 4}),
    # (e) 8 engineers running 35 services that are mostly released together
    "e_over_split": Scenario(
        "e", {"architecture": "consolidate"},
        targets={"need.architecture.coupling": 4.0},
        facts={"deployables_in_scope": 35, "core_code_share_pct": 8, "services_per_team": 17,
               "lockstep_deploy_pct": 60, "cross_service_change_pct": 45, "teams_per_deployable": 2},
        sizes={"ENG": 8}),
    # (g) head of platform wants change; the platform fits on one machine; an SLO tier exists but causes no pain
    "g_enthusiasm_without_need": Scenario(
        "g", {"architecture": "stay_and_improve"},
        targets={**LOW_NEED, "need.architecture.business_impact": 4.2,           # leadership enthusiasm
                 "capability.architecture.delivery_pipeline": 3.5},
        facts={**LOW_NEED_FACTS, "single_node_sufficient": "yes", "components_distinct_load": 1,
               "components_distinct_availability": 1, "candidate_incident_share_pct": 3,
               "candidate_scope_in_main_deployable": "not_applicable", "candidate_scaling_cost_share_pct": 2,
               "candidate_shared_tables_pct": 30}),
}


@pytest.fixture(scope="module")
def results(tmp_path_factory):
    out = {}
    for key, scenario in CASES.items():
        path = build(scenario, tmp_path_factory.mktemp(key), INSTRUMENT)
        out[key] = (scenario, assess(path, draws=DRAWS))
    return out


@pytest.mark.parametrize("case", list(CASES))
def test_walkthrough_case(results, case):
    scenario, assessment = results[case]
    r = assessment.results["architecture"]
    assert not assessment.engagement.problems, assessment.engagement.problems
    assert r.verdict == scenario.expected["architecture"], (r.verdict, r.distribution, r.unresolved_at)
    assert r.status == "go"


def test_f_missing_funding_and_leaving_sponsor_prepare_first(tmp_path):
    # (f) as (c), but funding is not committed and the sponsor leaves in six months
    case = CASES["c_ready_to_decompose"]
    scenario = Scenario("f", {"architecture": "broad_decomposition"}, case.targets, case.labels, case.facts,
                        governance={"GV02": {"answer": "No", "evidence": "", "attested_by": "CTO"},
                                    "GV03": {"answer": "No", "evidence": "", "attested_by": "CFO"}})
    r = assess(build(scenario, tmp_path, INSTRUMENT), draws=DRAWS).results["architecture"]
    assert r.verdict == "broad_decomposition"
    assert r.status == "prepare_first"
    assert r.gates["required"]["sponsor"]["status"] == "fail"       # min(GV01 yes, GV02 no)
    assert r.gates["required"]["funding"]["status"] == "fail"


def test_hard_stop_blocks_extraction_with_interim(tmp_path):
    case = CASES["d_pci_component"]
    scenario = Scenario("d-blocked", case.expected, case.targets, case.labels,
                        {**case.facts, "rollback_minutes": 240})
    r = assess(build(scenario, tmp_path, INSTRUMENT), draws=DRAWS).results["architecture"]
    assert r.verdict == "targeted_extraction" and r.status == "prepare_first"
    assert "hs_rollback" in r.hard_stops
    assert r.interim is not None


def test_economics_is_never_preparable_and_is_explained(tmp_path):
    case = CASES["c_ready_to_decompose"]
    scenario = Scenario("c-expensive", case.expected, case.targets, case.labels,
                        {**case.facts, "acceptable_run_cost_increase_pct": 10})
    r = assess(build(scenario, tmp_path, INSTRUMENT), draws=DRAWS).results["architecture"]
    assert r.verdict == "modular_monolith"
    assert any(f["outcome"] == "broad_decomposition" and f["signal"] == "fact.target_run_cost_increase_pct"
               for f in r.what_would_change)


def test_missing_key_fact_gives_insufficient_evidence_not_status_quo(tmp_path):
    case = CASES["b_coupled_shared_data"]
    facts = {**case.facts, "cross_team_change_pct": None, "teams_per_deployable": None, "blast_radius_pct": None}
    scenario = Scenario("b-missing", case.expected, {}, {}, facts, sizes={"ENG": 3, "PRD": 3, "TEC": 3})
    a = assess(build(scenario, tmp_path, INSTRUMENT), draws=DRAWS)
    r = a.results["architecture"]
    assert r.verdict == "insufficient_evidence"
    assert r.unresolved_share > 0.5
    assert any("teams_per_deployable" in p for p in a.problems)


def test_shadow_verdict_when_rules_were_adjusted(tmp_path):
    case = CASES["c_ready_to_decompose"]
    path = build(case, tmp_path, INSTRUMENT)
    rules = yaml.safe_load((INSTRUMENT / "decision_rules.yaml").read_text())
    broad = next(o for o in rules["decisions"]["architecture"]["outcomes"] if o["id"] == "broad_decomposition")
    broad["when"]["all"][1]["value"] = 20            # engagement demands ≥ 20 teams
    (tmp_path / "rules.yaml").write_text(yaml.safe_dump(rules))
    cfg = yaml.safe_load(path.read_text()); cfg["rules"] = "rules.yaml"; path.write_text(yaml.safe_dump(cfg))
    r = assess(path, draws=DRAWS).results["architecture"]
    assert r.verdict == "modular_monolith"
    assert r.shadow["verdict"] == "broad_decomposition"


def test_survey_export_round_trip(tmp_path):
    case = CASES["a_small_team_process_waits"]
    a = assess(build(case, tmp_path, INSTRUMENT), draws=50)
    answers = a.engagement.answers
    assert set(answers["role"]) == {"ENG", "PRD", "BUS", "TEC", "EXE", "OPS", "SEC", "FIN"}
    assert not a.engagement.problems
    assert answers[answers["item_id"] == "AN01"]["label"].eq("Approvals (e.g. change advisory board)").all()


# ---------------------------------------------------------------------------------------- engine units

def test_instrument_is_consistent():
    assert validate(load_instrument(INSTRUMENT)) == []


def test_validation_catches_rule_on_non_core_item():
    ins = load_instrument(INSTRUMENT)
    ins.items.loc["AC12", "core"] = "false"
    ins.rules["hard_stops"]["hs_test"] = {"label": "x", "when": {"signal": "item.AC12", "op": "<", "value": 3}}
    assert any("non-core item AC12" in e for e in validate(ins))


def test_three_valued_logic():
    ctx = Context({"a": 1.0, "b": None}, {"signals": {}})
    t, f, u = {"signal": "a", "op": "==", "value": 1.0}, {"signal": "a", "op": ">", "value": 2}, {"signal": "b", "op": ">", "value": 0}
    assert evaluate({"all": [t, u]}, ctx) is None
    assert evaluate({"all": [f, u]}, ctx) is False
    assert evaluate({"any": [t, u]}, ctx) is True
    assert evaluate({"any": [f, u]}, ctx) is None
    assert evaluate({"not": u}, ctx) is None


def test_reach():
    ctx = Context({"fit.x": 3.1, "fact.shared": 25.0, "fact.days": 9.0}, {"signals": {}})
    assert within_reach({"signal": "fit.x", "op": ">=", "value": 3.5}, ctx)                 # default 0.5 on scores
    assert not within_reach({"signal": "fit.x", "op": ">=", "value": 4.0}, ctx)
    assert within_reach({"signal": "fact.shared", "op": "<", "value": 20, "reach": 30}, ctx)
    assert not within_reach({"signal": "fact.days", "op": "<=", "value": 2}, ctx)          # facts need explicit reach


def test_premium_and_ref():
    ctx = Context({"r": 1.08, "p": 10.0, "x": 3.0, "y": 4.0}, {"signals": {}})
    assert evaluate({"signal": "r", "op": "<=", "value": 1.0, "premium": "p"}, ctx) is True
    assert evaluate({"signal": "x", "op": "<", "ref": "y"}, ctx) is True
