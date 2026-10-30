import copy
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from mra.assess import assess
from mra.engagement import Fact
from mra.integrity import run
from mra.scenario import build

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "examples"))
from build_techco import TECHCO  # noqa: E402


@pytest.fixture(scope="module")
def base(tmp_path_factory):
    return assess(build(TECHCO, tmp_path_factory.mktemp("techco"), ROOT / "instrument", seed=11), draws=60)


@pytest.fixture
def a(base):
    clone = copy.copy(base)
    clone.engagement = copy.copy(base.engagement)
    clone.engagement.facts = dict(base.engagement.facts)
    clone.engagement.governance = copy.deepcopy(base.engagement.governance)
    clone.engagement.config = copy.deepcopy(base.engagement.config)
    clone.engagement.instrument = copy.copy(base.engagement.instrument)
    clone.engagement.instrument.rules = copy.deepcopy(base.engagement.instrument.rules)
    clone.evidence = copy.copy(base.evidence)
    clone.evidence.signals = dict(base.evidence.signals)
    clone.text = None
    return clone


def ids(a):
    return {i.id: i for i in run(a)}


def sign(a, on="2026-09-15"):
    a.engagement.instrument.rules.update(signed_off_by="Leadership team", signed_off_on=on)


def text(a, messages, themes=()):
    a.text = SimpleNamespace(quotes=[], synthesis={"key_messages": list(messages),
                                                   "themes": [{"theme": "t", "finding": t, "quote_ids": []} for t in themes]})


def test_unsigned_rules_block(a):
    assert ids(a)["rules_signed_off"].severity == "block"
    sign(a)
    assert "rules_signed_off" not in ids(a)


def test_rules_signed_after_freeze_block(a):
    sign(a, on="2026-10-20")                                   # fact sheet frozen 2026-10-01
    assert "after the fact sheet was frozen" in ids(a)["rules_signed_off"].message


def test_unverified_baseline_is_caveated_and_rewrites_step(a):
    issue = ids(a)["baseline_unverified"]
    assert "readiness.benchmark" in issue.exhibits and issue.step_rewrite["starts_with"] == "Measure lead time"
    a.engagement.governance["GV06"] = {"answer": "Yes", "evidence": "Dashboard"}
    assert "baseline_unverified" not in ids(a)


def test_run_cost_reconciliation(a):
    assert "2.0×" in ids(a)["run_cost_reconciliation"].message
    a.engagement.facts["run_cost_annual"] = Fact(low=450000, likely=500000, high=560000, grade="invoice", attester="x")
    assert "run_cost_reconciliation" not in ids(a)


def test_urgency_against_dates(a):
    text(a, ["Finance says the hardware refresh is due and a decision is needed now."])
    issue = ids(a)["urgency_vs_dates"]
    assert issue.key_messages == [0] and "30 months away" in issue.message
    a.engagement.facts["hw_refresh_due_months"] = Fact(value=6, attester="x")
    assert "urgency_vs_dates" not in ids(a)


def test_critical_groups(a):
    issue = ids(a)["critical_groups.hosting"]
    assert "Security (4 respondents) and Finance (3)" in issue.message
    assert "critical_groups.architecture" not in ids(a)


def test_disputed_claim_against_survey(a):
    text(a, ["Release approval is the real bottleneck, not the platform."])
    issue = ids(a)["disputed_claims.process_not_coupling"]
    assert issue.key_messages == [0] and "100% of respondents" in issue.message
    n = len(a.evidence.signals["wait_state_share"])
    a.evidence.signals["wait_state_share"] = np.full(n, 0.6)
    assert "disputed_claims.process_not_coupling" not in ids(a)


def test_final_report_refused_while_blocked(base, tmp_path):
    from mra.report_v3 import NotFinal, build_report
    with pytest.raises(NotFinal, match="not recorded as signed off"):
        build_report(base, tmp_path / "r.pdf", final=True)
