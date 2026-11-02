"""Gate inputs rest on facts, not on a group rating itself; small groups cannot trigger the track-record rule alone."""

from pathlib import Path

import numpy as np

from mra.axes import build_evidence
from mra.engagement import load_engagement
from mra.scenario import Scenario, build

ROOT = Path(__file__).resolve().parents[1]


def _evidence(tmp_path, scenario, seed=1):
    return build_evidence(load_engagement(build(scenario, tmp_path / "e", ROOT / "instrument", seed=seed)), draws=50)


def test_a_self_rating_cannot_open_the_hardware_gate(tmp_path):
    # Operations rate their own hardware skills top marks; the tickets show nobody has replaced hardware
    ev = _evidence(tmp_path, Scenario("t", {}, current_hosting="cloud",
                                      targets={"capability.hosting.onprem_ops": 5.0},
                                      facts={"onprem_hw_ops_people": 0}))
    assert ev.signals["capability.hosting.onprem_ops"][0] == 1.0
    assert any(d["sub_area"] == "capability.hosting.onprem_ops" for d in ev.divergences)   # the gap is reported


def test_without_the_fact_the_survey_does_not_fill_in(tmp_path):
    ev = _evidence(tmp_path, Scenario("t", {}, targets={"capability.hosting.cloud_skills": 4.5},
                                      facts={"cloud_oncall_experienced_people": None}))
    assert np.isnan(ev.signals["capability.hosting.cloud_skills"][0])
    assert "cloud_oncall_experienced_people" in ev.missing_required


def test_scenario_targets_set_the_deciding_fact(tmp_path):
    ev = _evidence(tmp_path, Scenario("t", {}, targets={"capability.hosting.cloud_skills": 3.6}))
    assert ev.signals["capability.hosting.cloud_skills"][0] == 4.0


def _g14(yes_by_role):
    def fn(role, index, rng, labels):
        return {"G14": "Yes" if index < yes_by_role.get(role, 0) else "No"}
    return fn


def test_a_small_group_alone_does_not_make_stop_criteria_mandatory(tmp_path):
    ev = _evidence(tmp_path, Scenario("t", {}, sizes={"FIN": 2}, respondent_fn=_g14({"FIN": 2})))
    assert not ev.flags["track_record_concern"]


def test_a_reportable_group_at_the_threshold_does(tmp_path):
    ev = _evidence(tmp_path, Scenario("t", {}, sizes={"FIN": 5}, respondent_fn=_g14({"FIN": 2})))   # 40% >= 30%
    assert ev.flags["track_record_concern"]
