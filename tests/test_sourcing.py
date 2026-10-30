from pathlib import Path

import pytest

from mra.assess import assess
from mra.cases import SOURCING_CASES
from mra.scenario import build

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("name", sorted(SOURCING_CASES))
def test_sourcing_case(name, tmp_path):
    scenario, verdict, status = SOURCING_CASES[name]
    a = assess(build(scenario, tmp_path / "e", ROOT / "instrument", seed=5), draws=400)
    (part,) = a.sourcing
    assert (part["verdict"], part["status"]) == (verdict, status), part


@pytest.mark.parametrize("name", sorted(SOURCING_CASES))
def test_sourcing_report_is_board_ready(name, tmp_path):
    from mra.report_v3 import build_context
    from mra.rubric import failures, run
    scenario, verdict, _ = SOURCING_CASES[name]
    a = assess(build(scenario, tmp_path / "e", ROOT / "instrument", seed=5), draws=200)
    ctx = build_context(a, tmp_path / "o", ROOT)
    assert failures(run(ctx)) == []
    part = ctx["sourcing"]["parts"][0]
    request = next(r for r in ctx["brief"]["requests"] if r["decision"].startswith("Build or buy"))
    if verdict == "replace_with_product":
        assert request["ask"].startswith("Approve") and "proof of concept" in " ".join(s["action"] for s in ctx["steps"])
        assert any(r["item"].startswith("Build or buy: replacing") for r in ctx["budget"]["rows"])
        assert any(t["decision"] == "sourcing:part" and t["alternative"] == "Keep building it" for t in ctx["triggers"])
    elif verdict == "keep_building":
        assert request["ask"].startswith("Keep building")
    else:
        assert request["ask"].startswith("Do not decide yet")
    assert part["label"] and part["status_label"]


def test_techco_billing_waits_for_its_data_to_be_separated(tmp_path):
    import sys
    sys.path.insert(0, str(ROOT / "examples"))
    from build_techco import TECHCO

    from mra.report_v3 import build_context
    from mra.storyline import plain
    a = assess(build(TECHCO, tmp_path / "t", ROOT / "instrument", seed=11), draws=200)
    parts = {p["id"]: p for p in a.sourcing}
    assert (parts["billing"]["verdict"], parts["billing"]["status"]) == ("replace_with_product", "prepare_first")
    assert parts["pricing"]["verdict"] == "keep_building"
    ctx = build_context(a, tmp_path / "o", ROOT)
    text = plain(next(e for e in ctx["exhibits"] if e["insight"]["id"] == "sourcing.map")["insight"]["so_what"])
    assert "restructuring's step on data ownership" in text and "FTE" in text


def test_no_candidates_no_question(tmp_path):
    from mra.cases import HOSTING_CASES
    a = assess(build(HOSTING_CASES["a_steady_load_one_machine"], tmp_path / "e", ROOT / "instrument", seed=3), draws=60)
    assert a.sourcing == [] and not (a.engagement.answers["item_id"] == "SO01").any()
