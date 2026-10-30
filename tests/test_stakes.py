"""Stakes, preferences, alignment diagnostics, operating-model fit and v3 free-text coding."""

import json
from pathlib import Path

import pandas as pd
import pytest

from mra.assess import assess
from mra.scenario import Scenario, build
from mra.stakes import reportable_groups

ROOT = Path(__file__).resolve().parents[1]
INSTRUMENT = ROOT / "instrument"
DRAWS = 200

LOW_NEED = {"need.architecture.coupling": 1.5, "need.architecture.business_impact": 1.6,
            "need.architecture.cognitive_load": 1.5, "capability.architecture.delivery_pipeline": 3.5}
LOW_NEED_FACTS = {"teams_per_deployable": 2, "cross_team_change_pct": 5, "blast_radius_pct": 8}


def head_of_platform(role, index, rng, labels):
    """Technology leadership prefers a split that grows its roles; operations prefers keeping what protects theirs."""
    arch = labels["architecture"]
    split, keep = arch["broad_decomposition"], arch["stay_and_improve"]
    modular, extract = arch["modular_monolith"], arch["targeted_extraction"]
    if role == "TEC":
        return {"S01": split, f"S04[{split}]": "Increases it", f"S04[{extract}]": "Increases it",
                f"S04[{modular}]": "No real change", f"S04[{keep}]": "Reduces it",
                f"S05[{split}]": "Helps", f"S05[{extract}]": "Helps", f"S05[{modular}]": "No real effect",
                f"S05[{keep}]": "No real effect",
                "AA01": "Strongly agree", "AA02": "Strongly agree", "AA03": "Strongly agree"}
    if role == "OPS":
        return {"S01": keep, f"S04[{split}]": "Reduces it", f"S04[{extract}]": "Reduces it",
                f"S04[{modular}]": "No real change", f"S04[{keep}]": "No real change",
                f"S05[{split}]": "Makes it harder", f"S05[{extract}]": "Makes it harder",
                f"S05[{modular}]": "No real effect", f"S05[{keep}]": "No real effect",
                "S06": "Very much", "AA01": "Strongly disagree", "AA02": "Strongly disagree", "AA03": "Disagree"}
    if role == "EXE":
        return {"S01": keep, "AA01": "Strongly agree", "AA02": "Agree", "AA03": "Strongly agree"}
    if role == "ENG":
        return {"AA01": "Disagree", "AA02": "Strongly disagree", "AA03": "Disagree"}
    return {}


@pytest.fixture(scope="module")
def platform_case(tmp_path_factory):
    scenario = Scenario("platform", {"architecture": "stay_and_improve"}, targets=LOW_NEED, facts=LOW_NEED_FACTS,
                        sizes={"TEC": 6, "OPS": 8, "EXE": 6}, respondent_fn=head_of_platform)
    return assess(build(scenario, tmp_path_factory.mktemp("platform"), INSTRUMENT), draws=DRAWS)


def test_verdict_follows_evidence_not_preferences(platform_case):
    assert platform_case.results["architecture"].verdict == "stay_and_improve"


def test_preference_vs_evidence(platform_case):
    rows = {(p["group"], p["decision"]): p for p in platform_case.stakes.preference_vs_evidence}
    assert rows[("TEC", "architecture")]["differs"] and rows[("TEC", "architecture")]["most_preferred"] == "broad_decomposition"
    assert not rows[("OPS", "architecture")]["differs"]


def test_stake_alignment_is_detected_symmetrically(platform_case):
    rows = {a["group"]: a for a in platform_case.stakes.stake_alignment if a["decision"] == "architecture"}
    assert rows["TEC"]["notable"] and rows["TEC"]["share_preferring_change"] == 1.0
    assert rows["OPS"]["notable"] and rows["OPS"]["share_preferring_change"] == 0.0
    findings = " ".join(platform_case.stakes.findings)
    assert "TEC (architecture): preferences, which lean towards change" in findings
    assert "OPS (architecture): preferences, which lean towards the current setup" in findings


def test_findings_are_neutral(platform_case):
    text = " ".join(platform_case.stakes.findings).lower()
    for word in ("bias", "self-interest", "motivated", "agenda", "resist"):
        assert word not in text


def test_watermelon_and_concern(platform_case):
    items = {w["item"] for w in platform_case.stakes.watermelon}
    assert {"AA01", "AA02"} <= items
    assert platform_case.stakes.concern["OPS"]["self"] >= 0.9


def test_leadership_disagreement(platform_case):
    assert any(d["decision"] == "architecture" for d in platform_case.stakes.leadership_disagreement)


def test_fit_profile_lists_requirements_per_outcome(platform_case):
    fit = platform_case.stakes.fit
    assert {c["signal"] for c in fit["architecture.broad_decomposition"]} >= {"fit.domain_ownership",
                                                                                "fit.distributed_operations",
                                                                                "requirement.consistency_tolerance"}
    assert all("met" in c for conds in fit.values() for c in conds)


# ---------------------------------------------------------------------------------------- disclosure control

def test_small_groups_pooled_when_safe():
    shown, pooled, total_ok = reportable_groups(pd.Series({"ENG": 15, "SEC": 3, "FIN": 3}), 5)
    assert shown == ["ENG"] and pooled == ["SEC", "FIN"] and total_ok


def test_total_withheld_when_a_small_group_could_be_differenced():
    shown, pooled, total_ok = reportable_groups(pd.Series({"ENG": 15, "PRD": 8, "SEC": 3}), 5)
    assert pooled == [] and not total_ok


def test_no_cell_below_minimum(tmp_path):
    scenario = Scenario("small", {}, targets=LOW_NEED, facts=LOW_NEED_FACTS,
                        sizes={"SEC": 3, "FIN": 0, "BUS": 0, "EXE": 0})
    a = assess(build(scenario, tmp_path, INSTRUMENT), draws=50)
    prefs = a.stakes.preferences["architecture"]["by_group"]
    assert "SEC" not in prefs and "All respondents" not in prefs
    assert a.stakes.suppressed


# ---------------------------------------------------------------------------------------- v3 free text

def test_engagement_text_coding_with_mental_model(tmp_path, monkeypatch):
    from mra import llm

    def answers(role, index, rng, labels):
        return {"S08": f"{role} would change their mind if costs were shown", "S09": "Delivery would slow further",
                "CX03": "secret-word"}

    scenario = Scenario("text", {}, targets=LOW_NEED, facts=LOW_NEED_FACTS, respondent_fn=answers)
    path = build(scenario, tmp_path, INSTRUMENT)
    sent = []

    async def fake_complete(self, instructions, payload, output_type):
        sent.append(json.dumps(payload))
        if output_type is llm.Coding:
            return {"answers": [{"item_id": a["item_id"], "sentiment": 0, "stance": "neutral", "themes": ["Cost"],
                                 "reasons": [], "mental_model": "centralised" if payload["role"] == "OPS" else "domain_owned"}
                                for a in payload["answers"]]}
        return {"key_messages": ["x"], "themes": []}

    monkeypatch.setenv("AI_GATEWAY_API_KEY", "test")
    monkeypatch.setattr(llm.LLMClient, "complete", fake_complete)
    a = assess(path, draws=50, with_llm=True)
    assert a.text.by_role.loc["OPS", "model_centralised"] == 1.0
    assert a.text.by_role.loc["ENG", "model_domain_owned"] == 1.0
    assert not any("secret-word" in s for s in sent)


def test_no_false_alarms_on_random_answers(tmp_path):
    """Random preferences and stakes must not be presented as stake-driven (several seeds)."""
    flagged = 0
    for seed in range(5):
        scenario = Scenario("random", {}, targets=LOW_NEED, facts=LOW_NEED_FACTS)
        a = assess(build(scenario, tmp_path / str(seed), INSTRUMENT, seed=seed), draws=50, seed=seed)
        flagged += sum(r["notable"] for r in a.stakes.stake_alignment)
        tests = len(a.stakes.stake_alignment)
    assert flagged <= 1, f"{flagged} false alarms in {5 * tests} group tests"


def test_changing_the_prompt_invalidates_the_cache(tmp_path, monkeypatch):
    from mra import llm
    calls = []

    async def fake_complete(self, instructions, payload, output_type):
        calls.append(instructions)
        return {"key_messages": [], "themes": []}

    monkeypatch.setattr(llm.LLMClient, "complete", fake_complete)
    client, cache = llm.LLMClient("m", "k"), llm.Cache(tmp_path)
    llm.run_sync(llm._cached(client, cache, "synthesis", "Prompt A", {"x": 1}, llm.Synthesis))
    llm.run_sync(llm._cached(client, cache, "synthesis", "Prompt A", {"x": 1}, llm.Synthesis))
    llm.run_sync(llm._cached(client, cache, "synthesis", "Prompt B", {"x": 1}, llm.Synthesis))
    assert calls == ["Prompt A", "Prompt B"]
