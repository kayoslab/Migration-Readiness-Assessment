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

from mra.cases import (ARCHITECTURE_CASES as CASES, HIGH_DIFFUSE_NEED, HIGH_DIFFUSE_NEED_FACTS, LOW_NEED,
                       LOW_NEED_FACTS, STRONG_CAPABILITY, STRONG_CAPABILITY_FACTS)


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


def test_blank_engagement_from_init_is_insufficient_not_a_guess(tmp_path):
    from mra.scaffold import init
    folder = tmp_path / "acme"
    init(folder, INSTRUMENT)
    cfg = yaml.safe_load((folder / "engagement.yaml").read_text())
    cfg["instrument"] = str(INSTRUMENT)
    cfg["responses"] = {}
    (folder / "engagement.yaml").write_text(yaml.safe_dump(cfg))
    a = assess(folder / "engagement.yaml", draws=50)
    assert all(r.verdict == "insufficient_evidence" for r in a.results.values())
    assert any("teams_per_deployable" in p for p in a.problems)
    assert any("not named" in f.message for f in a.fact_checks)
