from pathlib import Path

import pytest

from mra.assess import assess
from mra.cases import ARCHITECTURE_CASES, HOSTING_CASES
from mra.report_v3 import build_context
from mra.scenario import build
from mra.storyline import S, T, plain, replace_means

ROOT = Path(__file__).resolve().parents[1]
CASES = {**{f"architecture/{k}": v for k, v in ARCHITECTURE_CASES.items()},
         **{f"hosting/{k}": v for k, v in HOSTING_CASES.items()}}


@pytest.fixture(scope="module")
def techco_ctx(tmp_path_factory):
    import sys
    sys.path.insert(0, str(ROOT / "examples"))
    from build_techco import TECHCO
    a = assess(build(TECHCO, tmp_path_factory.mktemp("techco"), ROOT / "instrument", seed=11), draws=300)
    a.engagement.config.setdefault("report", {})["stakeholder_map"] = True
    a.engagement.config["benchmark"] = {"industry": "technology", "organisation_size": "fewer_than_1000"}
    return build_context(a, tmp_path_factory.mktemp("out"), ROOT)


def _so_what(ctx, eid):
    return next(e["insight"] for e in ctx["exhibits"] if e["insight"]["id"] == eid)


def test_every_so_what_links_and_passes_checks(techco_ctx):
    assert techco_ctx["so_what_issues"] == []
    for e in techco_ctx["exhibits"]:
        assert e["insight"]["role"], e["insight"]["id"]
        assert any("ref" in s for s in e["insight"]["so_what"]), e["insight"]["id"]


def test_so_whats_read_across_findings(techco_ctx):
    people = _so_what(techco_ctx, "people.map")["so_what"]
    assert {"ref": "section", "id": "options-architecture", "name": "“what you would need to believe”"} in people
    assert any(s.get("ref") == "step" for s in people) and any(s.get("ref") == "risk" for s in people)
    assert "not open today" in plain(_so_what(techco_ctx, "readiness.matrix")["so_what"])     # cloud skills -> cloud move
    assert "also the cheapest" in plain(_so_what(techco_ctx, "hosting.tco")["so_what"])
    assert "not recommended" in plain(_so_what(techco_ctx, "architecture.stakes")["so_what"])
    arch = plain(_so_what(techco_ctx, "architecture.probabilities")["so_what"])
    assert "readiness, not direction" in arch and "step 1" in arch


def test_references_point_at_existing_targets(techco_ctx):
    steps = {s["no"] for s in techco_ctx["steps"]}
    risks = {r["id"] for r in techco_ctx["risks"]["risks"]}
    exhibits = {e["insight"]["id"] for e in techco_ctx["exhibits"]}
    for e in techco_ctx["exhibits"]:
        for s in e["insight"]["so_what"]:
            if s.get("ref") == "step":
                assert s["no"] in steps
            elif s.get("ref") == "risk":
                assert s["id"] in risks
            elif s.get("ref") == "exhibit":
                assert s["id"] in exhibits


@pytest.mark.parametrize("name", sorted(CASES))
def test_expert_cases_have_no_so_what_issues(name, tmp_path):
    a = assess(build(CASES[name], tmp_path / "eng", ROOT / "instrument", seed=3), draws=120)
    ctx = build_context(a, tmp_path / "out", ROOT)
    assert ctx["so_what_issues"] == []
    assert ctx["coverage_issues"] == []                     # every driver of the verdict is visible


def test_replace_means_keeps_references():
    seg = [T("First. Second ("), S(3), T(").")]
    assert plain(replace_means(seg, "Polished.")) == "Polished. Second (step 3)."
    assert replace_means([T("Runs into ("), S(3), T(").")], "Polished.")[0]["t"] == "Runs into ("


def test_polish_must_not_repeat_the_next_sentence():
    from mra.storyline import polish_ok
    seg = [T("Draft. What remains open is readiness, not direction: baseline measures and targets ("), S(1), T(").")]
    assert not polish_ok(seg, "The direction is clear, so what remains open is readiness: baseline measures and targets.")
    assert polish_ok(seg, "The evidence leaves no real alternative to restructuring within the current system.")
    assert not polish_ok(seg, " ".join(["word"] * 41) + ".")


def test_lead_time_exhibit_answers_the_process_question(techco_ctx):
    lead = _so_what(techco_ctx, "architecture.leadtime")
    assert lead["title"].startswith("Lead time goes mainly to coordination between teams (100%")
    text = plain(lead["so_what"])
    assert "faster approvals alone would not shorten lead time" in text and "OPS" in text
    assert any("delay the business experiences lies in coordination" in m for m in techco_ctx["key_messages"])
    assert techco_ctx["coverage_issues"] == []


def test_alternatives_show_every_route(techco_ctx):
    keep = next(o for d in techco_ctx["decisions"] for o in d["options"] if o["id"] == "stay_and_improve")
    assert any(b.startswith("Or, all of: share saying lead time is mostly waiting on process") for b in keep["beliefs"])
