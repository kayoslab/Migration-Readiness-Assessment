"""The leadership intent sheet, the risk and compliance sheet, and what they change: a risk of staying, steps
required on every path, the savings gate, citations for values that rule options out."""

import dataclasses
from pathlib import Path

import yaml

from mra.assess import assess
from mra.cases import HOSTING_CASES
from mra.integrity import run as integrity
from mra.scenario import build

ROOT = Path(__file__).resolve().parents[1]
INSTRUMENT = ROOT / "instrument"
STAY = HOSTING_CASES["d_regulated_strong_ops"]          # a regulated organisation whose own estate is in good order


def _assess(tmp_path, scenario, **changes):
    scenario = dataclasses.replace(scenario, **changes)
    return assess(build(scenario, tmp_path / "e", INSTRUMENT, seed=2), draws=200)


def test_a_failed_recovery_test_means_staying_as_it_is_is_not_enough(tmp_path):
    assert _assess(tmp_path / "a", STAY).results["hosting"].verdict == "stay_as_is"
    a = _assess(tmp_path / "b", STAY, facts={**STAY.facts, "dr_test_result": "failed"})
    assert a.results["hosting"].verdict == "improve_current"
    from mra.recommend import next_steps
    first = next_steps(a)[0]
    assert first["phase"] == "whichever_path" and "disaster-recovery test" in first["action"]


def test_risk_facts_are_read_from_the_risk_sheet(tmp_path):
    a = _assess(tmp_path, STAY, facts={**STAY.facts, "status_quo_compliance_findings": 3})
    assert a.engagement.facts["status_quo_compliance_findings"].sheet == "risk"
    assert a.engagement.facts["status_quo_compliance_findings"].attester == "Risk lead"
    assert not [i for i in integrity(a) if i.id in ("risk_sheet", "sheets")]


def test_an_uncited_hosting_constraint_keeps_the_report_a_draft(tmp_path):
    a = _assess(tmp_path / "a", STAY, facts={**STAY.facts, "hosting_constraint": "own_premises_only"})
    assert any(i.id == "citations.hosting_constraint" and i.severity == "block" for i in integrity(a))
    cited = {"value": "own_premises_only", "citation": "National banking act §12 (legal opinion 2026-08)"}
    a = _assess(tmp_path / "b", STAY, facts={**STAY.facts, "hosting_constraint": cited})
    assert not any(i.id.startswith("citations") for i in integrity(a))


def test_intent_set_after_the_evidence_was_in_keeps_the_report_a_draft(tmp_path):
    a = _assess(tmp_path, STAY, intent={"signed_on": "2026-10-20"})            # fact sheet frozen on 2026-10-01
    assert any(i.id == "intent_locked" and i.severity == "block" for i in integrity(a))


def test_without_an_intent_sheet_the_report_says_what_it_cannot_show(tmp_path):
    path = build(STAY, tmp_path, INSTRUMENT, seed=2)
    cfg = yaml.safe_load(path.read_text())
    del cfg["intent"]
    path.write_text(yaml.safe_dump(cfg))
    issues = integrity(assess(path, draws=100))
    assert any(i.id == "intent_locked" and i.severity == "caveat" for i in issues)


def test_leadership_thresholds_come_from_the_intent_sheet(tmp_path):
    a = _assess(tmp_path, STAY, intent={"accepted_premium_pct": 12})
    fact = a.engagement.facts["accepted_premium_pct"]
    assert fact.sheet == "intent" and fact.value == 12


def test_savings_never_checked_make_the_savings_gate_mandatory(tmp_path):
    from mra.gates import check_gates
    a = _assess(tmp_path, STAY, facts={**STAY.facts, "past_savings_verified": "never_checked"})
    rules = a.engagement.instrument.rules
    spec = {"requires_gates": ["sponsor"]}
    assert "savings" in check_gates(spec, rules, a.engagement.governance, a.evidence)["required"]
    assert "savings" not in check_gates({"requires_gates": []}, rules, a.engagement.governance, a.evidence)["required"]
