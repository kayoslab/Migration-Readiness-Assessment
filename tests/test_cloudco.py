"""CloudCo: services in the public cloud — the paths TechCo and MidCorp do not take."""

import json
import sys
from pathlib import Path

import pytest

from mra.assess import assess
from mra.report_v3 import build_context
from mra.rubric import failures, run
from mra.scenario import build

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "examples"))
from build_cloudco import CLOUDCO  # noqa: E402


@pytest.fixture(scope="module")
def ctx(tmp_path_factory):
    a = assess(build(CLOUDCO, tmp_path_factory.mktemp("c"), ROOT / "instrument", seed=31), draws=300)
    assert (a.results["architecture"].verdict, a.results["hosting"].verdict) == ("consolidate", "improve_current")
    return build_context(a, tmp_path_factory.mktemp("o"), ROOT)


def test_board_ready(ctx):
    assert failures(run(ctx)) == []


def test_no_hardware_talk_for_a_cloud_estate(ctx):
    hosting = next(d for d in ctx["decisions"] if d["id"] == "hosting")
    text = json.dumps([hosting["calendar"], hosting["inaction"], ctx["brief"]], ensure_ascii=False).lower()
    assert "hardware refresh" not in text and "colocation" not in text
    assert not any(m["measure"].startswith("Share of platform engineering hours") for m in ctx["measures"])


def test_money_follows_the_recommended_path(ctx):
    money = " ".join(ctx["brief"]["money"])
    assert "Improve / right-size costs" in money and "Move back from cloud costs" not in money
    assert money.startswith("Today's run cost")


def test_unestimated_path_is_approved_in_principle(ctx):
    arch = next(r for r in ctx["brief"]["requests"] if r["decision"] == "Architecture")
    assert "in principle" in arch["ask"] and "checkpoint C1" in arch["ask"]


def test_services_measures_and_wording(ctx):
    targets = {m["measure"]: m for m in ctx["measures"] if m["decision"] == "Architecture"}
    lockstep = next(m for k, m in targets.items() if k.startswith("Releases requiring several services"))
    assert lockstep["target"] == "below 30%" and lockstep["basis"].startswith("proposed: past the threshold")
    assert "edits in more than one service" in ctx["brief"]["scr"]["complication"]
    title = next(e for e in ctx["exhibits"] if e["insight"]["id"] == "architecture.map")["insight"]["title"]
    assert "restructure within the system" not in title


def test_switching_spend_starts_after_the_proof_of_concept(ctx):
    row = next(r for r in ctx["budget"]["rows"] if r["item"].startswith("Build or buy"))
    assert row["cells"][0] == 0
