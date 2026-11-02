"""Items that are reported, never scored: the cost of staying, the cost of changing, and the context leadership and
the business set — and the few places where they are read against the recommendation."""

import dataclasses
import sys
from pathlib import Path

import pytest

from mra.assess import assess
from mra.instrument import load_instrument
from mra.integrity import run as integrity
from mra.scenario import build

ROOT = Path(__file__).resolve().parents[1]
INSTRUMENT = ROOT / "instrument"
sys.path.insert(0, str(ROOT / "examples"))
from build_techco import TECHCO  # noqa: E402


def _techco(tmp_path, **labels):
    scenario = dataclasses.replace(TECHCO, labels={**TECHCO.labels, **labels})
    return assess(build(scenario, tmp_path, INSTRUMENT, seed=11), draws=200)


@pytest.fixture(scope="module")
def techco(tmp_path_factory):
    return _techco(tmp_path_factory.mktemp("techco"))


def test_business_answers_what_it_knows_instead_of_technical_preferences():
    ins = load_instrument(INSTRUMENT)
    current = {"architecture": "single_deployable", "hosting": "own_infrastructure", "_candidates": ["Billing"]}
    ids = {q["item_id"] for q in ins.form_spec("BUS", "X", current)}
    assert not ids & {"S01", "S02", "S03", "S08"}
    assert {"BP01", "BP02", "ABS", "BI01", "BI02"} <= ids


def test_the_report_shows_both_sides_with_the_measurement_beside_the_perception(techco):
    from mra.reported import build as reported
    sides = {s["id"]: s for s in reported(techco)["sides"]}
    assert {"staying", "changing", "context"} <= set(sides)
    tests = next(r for r in sides["staying"]["rows"] if r["item"] == "OPD")
    assert tests["fact"] and "disaster-recovery" in tests["fact"]["label"]
    assert all(a["n"] >= 5 for s in sides.values() for r in s["rows"] for a in r["answers"])


def test_a_path_longer_than_the_business_can_absorb_is_a_risk(tmp_path, techco):
    from mra.risks import register
    assert not any("can absorb" in r["title"] for r in register(techco)["risks"])
    a = _techco(tmp_path, ABS="Up to 1 month")
    risk = next(r for r in register(a)["risks"] if "can absorb" in r["title"])
    assert risk["decision"] == "architecture" and "about 1 months" not in risk["cause"]


def test_a_commitment_the_intent_sheet_leaves_out_is_flagged(tmp_path, techco):
    assert not any(i.id == "prior_commitment" for i in integrity(techco))
    a = _techco(tmp_path, PC01="Yes, for hosting")
    assert any(i.id == "prior_commitment" for i in integrity(a))


def test_lobbying_before_the_assessment_is_a_stakeholder_finding(tmp_path):
    a = _techco(tmp_path, BP02="Yes, towards a change")
    assert any("already been told" in f for f in a.stakes.findings)
