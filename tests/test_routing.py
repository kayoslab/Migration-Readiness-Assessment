"""Each group is asked what it can answer: per-group wording, per-row routing, items shown only when relevant."""

from pathlib import Path

import pytest

from mra.axes import count_band
from mra.instrument import load_instrument, validate

ROOT = Path(__file__).resolve().parents[1]
CURRENT = {"architecture": "single_deployable", "hosting": "own_infrastructure", "_candidates": ["Billing"]}


@pytest.fixture(scope="module")
def ins():
    return load_instrument(ROOT / "instrument")


def spec(ins, role, current=CURRENT):
    return ins.form_spec(role, "the Order Platform", current)


def test_the_instrument_is_consistent(ins):
    assert validate(ins) == []


def test_a_group_sees_its_own_wording(ins):
    fin = next(q for q in spec(ins, "FIN") if q["item_id"] == "G16")
    tec = next(q for q in spec(ins, "TEC") if q["item_id"] == "G16")
    assert "holds both the budget" in fin["text"] and "holds both the budget" not in tec["text"]


def test_grid_rows_go_to_the_groups_who_see_them(ins):
    rows = {role: [q["row"] for q in spec(ins, role) if q["item_id"] == "HN04"] for role in ("PRD", "OPS", "TEC", "ENG")}
    assert rows["OPS"] == ["Databases or messaging at a scale we could not reasonably run ourselves"]
    assert len(rows["PRD"]) == 2 and len(rows["TEC"]) == 3 and rows["ENG"] == []


def test_platform_questions_for_decomposition_appear_only_when_it_is_on_offer(ins):
    assert any(q["item_id"] == "AC14" for q in spec(ins, "ENG"))                 # one deployable: a split is an option
    distributed = {**CURRENT, "architecture": "distributed"}                      # already split: it is not
    assert not any(q["item_id"] == "AC14" for q in spec(ins, "ENG", distributed))


def test_business_groups_are_not_asked_technical_preferences_they_cannot_judge(ins):
    assert not any(q["item_id"] == "S01" for q in spec(ins, "FIN"))
    assert [q["row"] for q in spec(ins, "FIN") if q["item_id"] == "S03"] == ["Hosting"]
    assert not any(q["item_id"] in ("AN06", "RQ01") for q in spec(ins, "EXE"))


def test_a_partial_grid_is_scored_on_the_full_scale():
    # two of three rows shown, both "Yes": the same score as three of three
    assert count_band("count:0=1|1=3|2=4|3=5", 2, 2, 2, 3) == count_band("count:0=1|1=3|2=4|3=5", 3, 3, 3) == 5.0
    assert count_band("count:0=1|1=3|2=4|3=5", 0, 1, 1, 3) == 1.0
