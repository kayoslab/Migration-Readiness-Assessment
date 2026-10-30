import datetime as dt
from pathlib import Path

import pytest

from mra import benchmark
from mra.benchmark import category, compare, score

ROOT = Path(__file__).resolve().parents[1]


def test_score_matches_dora_quick_check():
    # expectations from DORA's own data-service.test.ts (commit 4ced7e4)
    assert score("percentage", 0) == 10 and score("percentage", 100) == 0 and score("percentage", 50) == 5
    assert score("duration", 0.5) == 10                 # less than one hour -> category 6
    assert score("duration", 10_000) == 0               # more than six months -> category 1


@pytest.mark.parametrize("hours, cat", [(0.5, 6), (1, 5), (23.9, 5), (24, 4), (167, 4), (168, 3), (729, 3), (730, 2),
                                        (4379, 2), (4380, 1)])
def test_duration_categories_follow_dora_boundaries(hours, cat):
    assert category("duration", hours) == cat


@pytest.mark.parametrize("per_week, cat", [(20, 6), (10, 6), (5, 5), (3, 4), (1, 4), (0.25, 3), (0.1, 2), (0.01, 1)])
def test_frequency_categories(per_week, cat):
    assert category("frequency", per_week) == cat


def test_table_is_complete_and_inverted_like_quick_check():
    bench = benchmark.load(ROOT / "instrument")
    allind = bench["segments"]["industry"]["all"]["metrics"]
    assert set(allind) == set(benchmark.METRICS)
    assert 10 - allind["changefailure"]["mean"] == pytest.approx(8.1)    # DORA test: inverted mean 8.1
    assert 10 - allind["rework"]["mean"] == pytest.approx(7.8)
    assert len(bench["levels_2024"]["clusters"]) == 4
    assert bench["source"]["commit"] and bench["source"]["licence"].startswith("Apache")


def test_staleness_warning():
    bench = benchmark.load(ROOT / "instrument")
    edition = bench["source"]["edition"]
    assert benchmark.age_warning(bench, dt.date(edition + 2, 12, 31)) is None
    assert "more than 2 years old" in benchmark.age_warning(bench, dt.date(edition + 3, 1, 1))


class _Fact:
    def __init__(self, v):
        self.point = v


class _Eng:
    def __init__(self, facts, cfg):
        from mra.instrument import load_instrument
        self.instrument = load_instrument(ROOT / "instrument")
        self.facts = {k: _Fact(v) for k, v in facts.items()}
        self.config = cfg


def test_positions_and_missing_measures():
    eng = _Eng({"lead_time_hours": 2000, "deploys_per_week": 20, "change_failure_pct": 19},
               {"benchmark": {"industry": "technology", "organisation_size": "fewer_than_1000"}})
    rows = {r["metric"]: r for r in compare(eng)["rows"]}
    assert rows["leadtime"]["position"] == "below" and rows["leadtime"]["level_2024"] == "low"
    assert rows["deployfreq"]["position"] == "above" and rows["deployfreq"]["level_2024"] == "elite"
    assert rows["changefailure"]["position"] == "around" and rows["changefailure"]["level_2024"] is None
    assert rows["failurerecovery"]["score"] is None and rows["failurerecovery"]["position"] == "not measured"
    assert rows["leadtime"]["size_position"] in ("above", "around", "below")


def test_unknown_segment_is_an_error():
    eng = _Eng({}, {"benchmark": {"industry": "banking"}})
    with pytest.raises(ValueError, match="unknown industry"):
        compare(eng)


def test_interpretation_links_to_architecture_verdict():
    from mra import interpret
    eng = _Eng({"lead_time_hours": 2000, "deploys_per_week": 0.1}, {})
    bm = compare(eng)
    out = interpret.benchmark(bm, "modular_monolith")
    assert out["title"].startswith("Behind the industry average")
    assert any("consistent with the need for change" in p for p in out["points"])
    assert any("Not measured" in p for p in out["points"])
