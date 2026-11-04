"""Voices not heard on their own: small groups are named, and whether they lean a different way is said in words."""

import copy
import dataclasses
import sys
from pathlib import Path

import pytest

from mra.assess import assess
from mra.integrity import run as integrity
from mra.scenario import build
from mra.stakes import CHANGE_OUTCOMES
from mra.voices import build as voices

ROOT = Path(__file__).resolve().parents[1]
INSTRUMENT = ROOT / "instrument"
sys.path.insert(0, str(ROOT / "examples"))
from build_techco import TECHCO  # noqa: E402


@pytest.fixture(scope="module")
def techco(tmp_path_factory):
    return assess(build(TECHCO, tmp_path_factory.mktemp("techco"), INSTRUMENT, seed=11), draws=200)


def _rows(a):
    return {r["role"]: r for r in voices(a)["rows"]}


def _lean(a, role, toward_change: bool):
    """Make one group prefer, and see a need for, the opposite of what it said."""
    a = copy.copy(a)
    eng = a.engagement = copy.copy(a.engagement)
    ans = eng.answers = eng.answers.copy()
    ins = eng.instrument
    mine = set(eng.respondents.loc[eng.respondents["role"] == role, "respondent_id"])
    who = ans["respondent_id"].isin(mine) & ans["row"].isna()
    for item, d in (("S01", "architecture"), ("S02", "hosting")):
        options = ins.preference_options(d, a.evidence.current_state[d])
        label = next(l for o, l in options if (o in CHANGE_OUTCOMES) == toward_change)
        ans.loc[who & (ans["item_id"] == item), "label"] = label
    need = ins.items.index[(ins.items["block"] == "need") & (ins.items["scored"] == "true")]
    ans.loc[who & ans["item_id"].isin(need), "score"] = 5.0 if toward_change else 1.0
    return a


def test_small_groups_are_named_with_how_they_are_counted(techco):
    rows = _rows(techco)
    assert set(rows) == {"SEC", "FIN"}                      # 4 and 3 respondents; everyone else has five or more
    assert all(r["counted"].startswith("Counted only within") for r in rows.values())
    assert all(r["described"] for r in rows.values())


def test_only_words_are_shown_never_figures(techco):
    for r in _rows(techco).values():
        assert not any(ch.isdigit() for d in r["decisions"] for ch in d["text"])


def test_a_group_below_the_describing_minimum_is_named_but_not_described(tmp_path):
    sizes = {**TECHCO.sizes, "FIN": 2}
    a = assess(build(dataclasses.replace(TECHCO, sizes=sizes), tmp_path, INSTRUMENT, seed=11), draws=100)
    fin = _rows(a)["FIN"]
    assert fin["n"] == 2 and not fin["described"] and fin["decisions"] == []


def test_a_group_pointing_the_other_way_is_a_finding_and_reaches_the_caveat(techco):
    stays = techco.results["hosting"].verdict not in ("move_to_cloud", "hybrid", "repatriate")
    a = _lean(techco, "SEC", toward_change=stays)            # against whatever the evidence supports
    sec = _rows(a)["SEC"]
    hosting = next(d for d in sec["decisions"] if d["decision"] == "hosting")
    assert hosting["level"] == 2 and hosting["against_path"]
    assert any(f.startswith("Security (4 respondents)") for f in voices(a)["findings"])
    caveat = next(i for i in integrity(a) if i.id == "critical_groups.hosting")
    assert "Security points the other way" in caveat.message


def test_a_needed_group_with_no_respondents_is_listed(techco):
    a = copy.copy(techco)
    eng = a.engagement = copy.copy(techco.engagement)
    gone = set(eng.respondents.loc[eng.respondents["role"] == "SEC", "respondent_id"])
    eng.respondents = eng.respondents[~eng.respondents["respondent_id"].isin(gone)]
    eng.answers = eng.answers[~eng.answers["respondent_id"].isin(gone)]
    sec = _rows(a)["SEC"]
    assert sec["n"] == 0 and sec["counted"] == "No respondents" and sec["critical"] == ["hosting"]


def test_a_group_in_no_combination_is_shown_as_not_counted(tmp_path):
    sizes = {**TECHCO.sizes, "OPS": 4}                     # small delivery groups together are still under five
    a = assess(build(dataclasses.replace(TECHCO, sizes=sizes), tmp_path, INSTRUMENT, seed=11), draws=100)
    assert _rows(a)["OPS"]["counted"] == "Not counted"
