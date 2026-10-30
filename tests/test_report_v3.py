"""v3 report: plain-language explanations, next steps from the action library, and the PDF build."""

import sys
from pathlib import Path

import pytest

from mra.assess import assess
from mra.recommend import next_steps
from mra.report_v3 import build_context, build_report

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "examples"))
from build_techco import TECHCO  # noqa: E402

from mra.scenario import build  # noqa: E402


@pytest.fixture(scope="module")
def techco(tmp_path_factory):
    return assess(build(TECHCO, tmp_path_factory.mktemp("techco"), ROOT / "instrument", seed=11), draws=300)


def test_example_verdicts(techco):
    arch, host = techco.results["architecture"], techco.results["hosting"]
    assert (arch.verdict, arch.status) == ("modular_monolith", "prepare_first")
    assert arch.gates["required"]["baseline"]["status"] == "fail"
    assert (host.verdict, host.status) == ("improve_current", "go")


def test_next_steps_come_from_the_library(techco):
    steps = next_steps(techco)
    phases = [s["phase"] for s in steps]
    assert phases == sorted(phases, key=["before_commitment", "capability", "first_steps", "people", "evidence"].index)
    baseline = next(s for s in steps if s["phase"] == "before_commitment")
    assert "lead time" in baseline["action"] and "not met" in baseline["reason"]
    assert all(s["owner"] for s in steps)


def test_plain_language_no_raw_signal_names(techco, tmp_path):
    ctx = build_context(techco, tmp_path, ROOT)
    text = " ".join(" ".join(d["why"] + d["flips"]) for d in ctx["decisions"])
    assert "need.architecture" not in text and "fact." not in text and ">=" not in text
    assert any("would apply if" in f for d in ctx["decisions"] for f in d["flips"])


def test_pdf_builds(techco, tmp_path):
    pdf = build_report(techco, tmp_path / "techco.pdf")
    assert pdf.stat().st_size > 100_000


def test_one_document_includes_readiness_by_group(techco, tmp_path):
    ctx = build_context(techco, ROOT / "Output" / "build-test-ctx", ROOT)
    assert ctx["readiness"]["differences"] and ctx["readiness"]["weakest"]
    assert any(m.startswith("The weakest areas of readiness are") for m in ctx["key_messages"])
    big = [d for d in ctx["readiness"]["differences"] if d["significant"]]
    assert big and big[0]["sub_area"] == "Alignment: reasons explained"
    import shutil
    shutil.rmtree(ROOT / "Output" / "build-test-ctx", ignore_errors=True)


def test_options_appraisal_and_beliefs(techco):
    from mra.appraisal import appraise
    rows = {r["id"]: r for r in appraise(techco, "architecture")}
    assert rows["modular_monolith"]["is_verdict"] and rows["modular_monolith"]["state"] == "applies after preparation"
    split = " ".join(rows["broad_decomposition"]["beliefs"])
    assert "at least 3.5" in split and "below 20%" in split          # need and capability conditions both listed
    hosting = {r["id"]: r for r in appraise(techco, "hosting")}
    assert hosting["improve_current"]["cost_vs_today"] < 1 < hosting["move_to_cloud"]["cost_vs_today"]
    assert hosting["stay_as_is"]["state"] == "pre-empted"


def test_risk_register_follows_findings(techco):
    from mra.risks import register
    reg = register(techco)
    top = reg["risks"][0]
    assert top["likelihood"] == "high" and "baseline" in top["title"].lower()
    assert any(r["kind"] == "people" for r in reg["risks"])
    assert any("80%" in a["assumption"] for a in reg["assumptions"])
    assert reg["dependencies"][0]["status"] == "fail"


def test_basis_of_preparation(techco, tmp_path):
    ctx = build_context(techco, ROOT / "Output" / "build-test-basis", ROOT)
    assert any("should not be relied upon" in p for p in ctx["notice"])
    assert any(t["term"] == "Hard stop" for t in ctx["glossary"])
    import shutil
    shutil.rmtree(ROOT / "Output" / "build-test-basis", ignore_errors=True)


def test_roadmap_measures_scenarios(techco):
    from mra import plan
    from mra.recommend import next_steps
    rm = plan.roadmap(techco, next_steps(techco))
    before = [b for b in rm["bars"] if b["workstream"].startswith("Before committing")]
    assert before and all(b["start"] == 0 and b["end"] == 3 for b in before)
    assert [g["month"] for g in rm["gates"]] == [3, 6, 12]
    m = plan.measures(techco)
    assert any(x["measure"].startswith("Merged changes") and x["target"] == "below 15%" for x in m)
    sc = plan.scenarios(techco)
    cloud = next(r for r in sc["rows"] if r["option"] == "Move to cloud")
    assert cloud["favourable"] <= cloud["base"] <= cloud["conservative"]
    assert all(b["value"] is None for b in sc["breakeven"])       # nothing alone makes a move pay off at TechCo


def test_break_even_found_when_reachable(techco):
    from mra import plan
    cur = techco.engagement.config.get("current_hosting", "own_infrastructure")
    base = {**techco.evidence.fact_point, "dc_cost_annual": 1_000_000, "ops_fte": 8}   # an expensive data centre
    found = plan._break_even("cloud", "cloud_compute_baseline_annual", 400_000, 900_000, base, cur,
                             techco.engagement.instrument)
    assert found["value"] is not None and found["value"] < base["cloud_compute_baseline_annual"]
    ratio = plan._ratio({**base, "cloud_compute_baseline_annual": found["value"]}, cur, "cloud", "improve_current")
    assert abs(ratio - 0.85) < 0.01
    assert "only if" in found["sentence"] and "below" in found["sentence"]


def test_stakeholder_map(techco):
    from mra.stakeholders import stakeholder_map
    report = techco.engagement.config.setdefault("report", {})
    before = report.get("stakeholder_map")
    report["stakeholder_map"] = True
    try:
        rows = {r["group"]: r for r in stakeholder_map(techco)}
    finally:
        report["stakeholder_map"] = before
    assert "Other groups" not in rows and "All respondents" not in rows
    assert rows["TEC"]["approach"] == "Engage closely" and rows["EXE"]["approach"] == "Involve as sponsors"
    assert all(0 <= r["support"] <= 1 for r in rows.values())


def test_stakeholder_map_off_by_default(techco):
    from mra.stakeholders import stakeholder_map
    report = techco.engagement.config.setdefault("report", {})
    before = report.get("stakeholder_map")
    report["stakeholder_map"] = False
    try:
        assert stakeholder_map(techco) == []
    finally:
        report["stakeholder_map"] = before


def test_ties_are_not_counted_as_agreement():
    from mra.interpret import preferences
    from mra.stakes import top_choice
    assert top_choice({"a": 0.3, "b": 0.3, "no_direction": 0.4})[0] is None
    out = preferences({"G1": {"a": 0.6, "b": 0.4}, "G2": {"a": 0.3, "b": 0.3}, "All respondents": {"a": 0.31, "b": 0.33}},
                      {"a": "A", "b": "B"}, "a")
    assert out["title"].startswith("1 of 2 groups") and "split evenly" in out["title"]
    assert "33% prefer “B”" in out["points"][0]


def test_pooled_groups_owners_and_appendix(techco, tmp_path):
    techco.engagement.config.setdefault("people", {})["technology_lead"] = "CTO"
    ctx = build_context(techco, tmp_path, ROOT)
    assert "Security (4) and Finance (3)" in ctx["stakes"]["pooled_note"]
    assert any(s["owner"] == "Technology lead (CTO)" for s in ctx["steps"])
    labels = [r["signal"] for r in ctx["evidence"]]
    assert len(labels) == len(set(labels)) and not any(l.startswith(("capability.", "need.")) for l in labels)
    assert ctx["decisions"][0]["charts"]["probabilities"] is None          # a single 100% bar is not drawn
    assert "Evidence indicative" in ctx["evidence_note"]


def test_costs_in_euros_with_ranges_and_calendar(techco, tmp_path):
    ctx = build_context(techco, tmp_path, ROOT)
    hosting = next(d for d in ctx["decisions"] if d["id"] == "hosting")
    keep = hosting["economics"][0]
    assert keep["option"] == "Keep as is" and keep["eur"].startswith("€")
    low, high = keep["eur_range"].split("–")
    assert low != high                                         # single values are ranges too
    events = [c["event"] for c in hosting["calendar"]]
    assert any(e.startswith("Hardware refresh due") for e in events) and "Colocation contract ends" in events
    assert "including the €400k hardware refresh in month 30" in hosting["inaction"]


def test_amounts_can_be_hidden(techco, tmp_path):
    techco.engagement.config.setdefault("report", {})["show_amounts"] = False
    try:
        ctx = build_context(techco, tmp_path, ROOT)
    finally:
        techco.engagement.config["report"]["show_amounts"] = True
    hosting = next(d for d in ctx["decisions"] if d["id"] == "hosting")
    assert all(r["eur"] is None for r in hosting["economics"]) and "€" not in (hosting["inaction"] or "")
