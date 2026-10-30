"""MidCorp: the messy example — insufficient evidence, a blocked hosting decision, small groups, undecided parts."""

import sys
from pathlib import Path

import pytest

from mra.assess import assess
from mra.report_v3 import build_context
from mra.rubric import failures, run
from mra.scenario import build

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "examples"))
from build_midcorp import MIDCORP  # noqa: E402


@pytest.fixture(scope="module")
def ctx(tmp_path_factory):
    a = assess(build(MIDCORP, tmp_path_factory.mktemp("m"), ROOT / "instrument", seed=23), draws=400)
    return build_context(a, tmp_path_factory.mktemp("o"), ROOT)


def test_board_ready_even_as_a_draft(ctx):
    assert ctx["integrity"]["draft"] and failures(run(ctx)) == []


def test_decision_page_does_not_ask_for_what_is_unsettled(ctx):
    asks = {r["decision"]: r for r in ctx["brief"]["requests"]}
    assert asks["Architecture"]["ask"].startswith("Do not choose a path yet")
    assert "checkpoint C1" in asks["Architecture"]["ask"]
    assert asks["Hosting"]["status"] == "On hold" and asks["Hosting"]["ask"].startswith("Do not approve")
    assert "not yet decided" in ctx["brief"]["scr"]["resolution"]


def test_blocks_become_risks_and_steps(ctx):
    assert any(r["title"].startswith("Basis of the decision") for r in ctx["risks"]["risks"][:2])
    assert any(s["action"].startswith("Allocate the difference") for s in ctx["steps"])
    assert [s["no"] for s in ctx["steps"]] == list(range(1, len(ctx["steps"]) + 1))


def test_calendar_reviews_before_the_refresh(ctx):
    cal = {c["event"].split(" (")[0]: c["month"] for c in next(d for d in ctx["decisions"] if d["id"] == "hosting")["calendar"]}
    assert cal["Hosting review"] < cal["Hardware refresh due"]


def test_undecided_parts_are_explained(ctx):
    parts = {p["id"]: p for p in ctx["sourcing"]["parts"]}
    assert parts["documents"]["status"] == "insufficient" and "too close to call" in parts["documents"]["why"][0]
    assert parts["claims"]["status"] == "excluded" and "ruled out" in parts["claims"]["summary"]
    title = next(e for e in ctx["exhibits"] if e["insight"]["id"] == "sourcing.map")["insight"]["title"]
    assert "not yet decided" in title
