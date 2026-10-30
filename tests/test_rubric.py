import copy
import sys
from pathlib import Path

import pytest
import yaml

from mra.assess import assess
from mra.report_v3 import build_context
from mra.rubric import failures, run
from mra.scenario import build

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "examples"))
from build_techco import TECHCO  # noqa: E402


@pytest.fixture(scope="module")
def ctx(tmp_path_factory):
    a = assess(build(TECHCO, tmp_path_factory.mktemp("t"), ROOT / "instrument", seed=11), draws=200)
    return build_context(a, tmp_path_factory.mktemp("o"), ROOT)


def failed(c) -> set[str]:
    return {r["check"] for r in run(c) if not r["ok"]}


def test_techco_is_board_ready(ctx):
    assert failures(run(ctx)) == []


@pytest.mark.parametrize("plant, check", [
    (lambda c: c["steps"][0].update(action="Name the owner in engagement.yaml → people."), "Plain language"),
    (lambda c: c["steps"][0].update(action="Fill in arch_effort_person_months."), "Plain language"),
    (lambda c: c["steps"][0].update(action="See GV06 in the checklist."), "Plain language"),
    (lambda c: c["brief"]["requests"].pop(), "Decision requested"),
    (lambda c: c.__setitem__("triggers", []), "Reopen criteria"),
    (lambda c: c["engagement"].__setitem__("draft", not c["engagement"]["draft"]), "Draft status"),
    (lambda c: c.__setitem__("coverage_issues", ["architecture: something decides but is hidden"]), "Every deciding"),
    (lambda c: [d.__setitem__("caveats", []) for d in c["decisions"]]
     + [e["insight"].__setitem__("caveats", []) for e in c["exhibits"]], "Every caveat placed"),
])
def test_planted_defects_are_caught(ctx, plant, check):
    c = copy.deepcopy(ctx)
    plant(c)
    assert any(f.startswith(check) for f in failed(c)), failed(c)


def test_missing_fact_reads_plainly_and_blocks_final(tmp_path):
    from mra.report_v3 import NotFinal, build_report
    root = build(TECHCO, tmp_path / "t", ROOT / "instrument", seed=11)
    facts_path = root.parent / "facts.yaml" if root.is_file() else root / "facts.yaml"
    facts = yaml.safe_load(facts_path.read_text())
    facts.pop("dc_cost_annual")
    facts_path.write_text(yaml.safe_dump(facts))
    a = assess(root, draws=60)
    c = build_context(a, tmp_path / "o", ROOT)
    assert any(p.startswith("The hosting cost comparison could not be computed") or p.startswith("Missing from the fact")
               for p in c["problems"])
    assert not any(f.startswith("Plain language") for f in failed(c))
    with pytest.raises(NotFinal):                       # unsigned rules and no quality review
        build_report(a, tmp_path / "r.pdf", final=True)


def test_review_refuses_client_engagements(tmp_path):
    from mra.review import review
    root = build(TECHCO, tmp_path / "t", ROOT / "instrument", seed=11)
    path = root if root.is_file() else root / "engagement.yaml"
    cfg = yaml.safe_load(path.read_text())
    cfg.setdefault("report", {})["client_engagement"] = True
    path.write_text(yaml.safe_dump(cfg))
    with pytest.raises(PermissionError, match="not run on client engagements"):
        review(path, draws=30)


def test_pretest_sheets(tmp_path):
    import csv

    from mra.pretest import sheets
    root = build(TECHCO, tmp_path / "t", ROOT / "instrument", seed=11)
    minutes = sheets(root if root.is_file() else root / "engagement.yaml", tmp_path / "sheets")
    assert minutes["ENG"] > minutes["SEC"] > 0
    rows = list(csv.DictReader((tmp_path / "sheets" / "BUS.csv").open()))
    assert rows[0]["item"] == "CX01" and "seconds_measured" in rows[0]
