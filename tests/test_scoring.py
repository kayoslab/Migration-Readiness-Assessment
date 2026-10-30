"""Regression tests for the issues found in the statistical review of the original notebook."""

import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from mra import scoring
from mra.config import load_config
from mra.data import load_survey

ROOT = Path(__file__).resolve().parents[1]
ROLES = ["Engineering", "Product", "Business", "Leadership"]
LABELS = {1: "Strongly Disagree", 2: "Disagree", 3: "Neutral", 4: "Agree", 5: "Strongly Agree"}


def make_project(tmp_path, answer, n=6, items_per_role=4):
    """Tiny questionnaire: two domains, every role asked `items_per_role` items per domain."""
    rows, item_id = [], 1
    for domain in ["Alpha", "Beta"]:
        for _ in range(items_per_role):
            rows.append({"ID": item_id, "Question": f"Statement {item_id}", "Category": domain,
                         "Critical": "FALSE", **{r: "TRUE" for r in ROLES}, "Type": "Quantitative",
                         "Question Type": "Multiple choice", "Theme": "", "Weight": 1})
            item_id += 1
    rows.append({"ID": item_id, "Question": "Comments?", "Category": "Alpha", "Critical": "FALSE",
                 **{r: "TRUE" for r in ROLES}, "Type": "Qualitative", "Question Type": "Paragraph",
                 "Theme": "", "Weight": 1})
    q = pd.DataFrame(rows)
    (tmp_path / "Questions").mkdir()
    q.to_csv(tmp_path / "Questions/export.csv", index=False)
    (tmp_path / "Responses").mkdir()
    for role in ROLES:
        data = []
        for p in range(n):
            row = {"Timestamp": "x"}
            for _, item in q.iterrows():
                if item["Type"] == "Quantitative":
                    row[item["Question"]] = answer(role, item["Category"], p, item["ID"])
                else:
                    row[item["Question"]] = f"{role} comment {p}"
            data.append(row)
        pd.DataFrame(data).to_csv(tmp_path / f"Responses/{role}.csv", index=False)
    cfg_text = (ROOT / "assessment.yaml").read_text().replace("questionnaire: Questions/export.csv",
                                                              "questionnaire: Questions/export.csv")
    (tmp_path / "assessment.yaml").write_text(cfg_text.replace("bootstrap_iterations: 2000",
                                                               "bootstrap_iterations: 300")
                                              .replace("permutation_iterations: 2000",
                                                       "permutation_iterations: 300"))
    return load_config(tmp_path / "assessment.yaml")


def test_role_scores_use_only_that_roles_respondents(tmp_path):
    # Business answers 1 to everything, everyone else 5. The original notebook reported ~4 for every role.
    cfg = make_project(tmp_path, lambda role, d, p, i: LABELS[1 if role == "Business" else 5])
    res = scoring.score_groups(load_survey(cfg), cfg)
    assert res.role_mean.loc["Business"].tolist() == [1.0, 1.0]
    assert res.role_mean.loc["Engineering"].tolist() == [5.0, 5.0]


def test_index_weights_roles_equally_not_by_headcount(tmp_path):
    cfg = make_project(tmp_path, lambda role, d, p, i: LABELS[1 if role == "Business" else 5])
    res = scoring.score_groups(load_survey(cfg), cfg)
    assert res.summary.loc["Alpha", "index"] == pytest.approx((5 + 5 + 1 + 5) / 4)


def test_missing_answers_are_not_zero(tmp_path):
    # One item in four skipped: still above the 60% coverage rule, and the skips do not drag scores down.
    cfg = make_project(tmp_path, lambda role, d, p, i: "" if i % 4 == 0 else LABELS[4])
    survey = load_survey(cfg)
    assert (survey.likert["value"].dropna() == 4).all()
    assert survey.likert["value"].isna().mean() == pytest.approx(0.25)
    assert np.allclose(scoring.score_groups(survey, cfg).summary["index"], 4.0)


def test_too_few_answers_give_no_person_score(tmp_path):
    cfg = make_project(tmp_path, lambda role, d, p, i: "" if i % 2 else LABELS[4])
    assert scoring.score_groups(load_survey(cfg), cfg).summary["index"].isna().all()


def test_numeric_and_label_answers_are_equivalent(tmp_path):
    cfg = make_project(tmp_path, lambda role, d, p, i: 4 if p % 2 else LABELS[4])
    assert (load_survey(cfg).likert["value"] == 4).all()


def test_dont_know_is_flagged_not_scored(tmp_path):
    cfg = make_project(tmp_path, lambda role, d, p, i: "Don't know" if p == 0 else LABELS[3])
    survey = load_survey(cfg)
    assert survey.likert["dont_know"].sum() == 4 * 8  # one person per role, 8 items
    assert (survey.likert["value"].dropna() == 3).all()


def test_one_dissenting_role_blocks_proceed(tmp_path):
    # The original GO rule returned CONDITIONAL GO even when a whole group answered "strongly disagree".
    cfg = make_project(tmp_path, lambda role, d, p, i: LABELS[1 if role == "Business" else 5])
    survey = load_survey(cfg)
    v = scoring.verdict(scoring.score_groups(survey, cfg), survey, cfg)
    assert v.decision != scoring.PROCEED


def test_neutral_everywhere_is_not_ready(tmp_path):
    # All-neutral used to score 60% "readiness" = CONDITIONAL GO.
    cfg = make_project(tmp_path, lambda role, d, p, i: LABELS[3])
    survey = load_survey(cfg)
    v = scoring.verdict(scoring.score_groups(survey, cfg), survey, cfg)
    assert v.decision == scoring.CONDITIONAL
    assert all("does not clear" in r for r in v.reasons)


def test_uniformly_positive_proceeds(tmp_path):
    cfg = make_project(tmp_path, lambda role, d, p, i: LABELS[4 + (p + i) % 2])
    survey = load_survey(cfg)
    v = scoring.verdict(scoring.score_groups(survey, cfg), survey, cfg)
    assert v.decision == scoring.PROCEED


def test_small_role_gives_insufficient_evidence(tmp_path):
    cfg = make_project(tmp_path, lambda role, d, p, i: LABELS[4], n=3)
    survey = load_survey(cfg)
    v = scoring.verdict(scoring.score_groups(survey, cfg), survey, cfg)
    assert v.decision == scoring.INSUFFICIENT


def test_cronbach_alpha_known_values():
    rng = np.random.default_rng(0)
    trait = rng.normal(size=200)
    consistent = pd.DataFrame({i: trait + rng.normal(scale=0.3, size=200) for i in range(5)})
    noise = pd.DataFrame({i: rng.normal(size=200) for i in range(5)})
    assert scoring.cronbach_alpha(consistent) > 0.9
    assert abs(scoring.cronbach_alpha(noise)) < 0.3


def test_item_gap_permutation_detects_real_difference(tmp_path):
    cfg = make_project(tmp_path, lambda role, d, p, i: LABELS[(1 + p % 2) if role == "Business" else (4 + p % 2)],
                       n=10)
    items = scoring.item_statistics(load_survey(cfg), cfg)
    assert (items["gap_q"] < 0.05).all()
    assert (items["gap_low_role"] == "Business").all()


def test_llm_coding_with_fake_client(tmp_path, monkeypatch):
    from mra import llm

    cfg = make_project(tmp_path, lambda role, d, p, i: LABELS[4])
    survey = load_survey(cfg)
    calls = []

    async def fake_complete(self, instructions, payload, output_type):
        calls.append(output_type.__name__)
        if output_type is llm.Coding:
            body = {"answers": [{"item_id": a["item_id"], "sentiment": -1 if payload["role"] == "Business" else 1,
                                 "stance": "supports_change", "themes": ["Delivery speed"],
                                 "reasons": ["Speed of delivery"]} for a in payload["answers"]]}
        else:
            body = {"key_messages": ["Business is more negative."],
                    "themes": [{"theme": "Delivery speed", "finding": "All groups mention it.", "quote_ids": [1]}]}
        return output_type.model_validate(body).model_dump()

    monkeypatch.setenv("AI_GATEWAY_API_KEY", "test")
    monkeypatch.setattr(llm.LLMClient, "complete", fake_complete)
    result = llm.analyse_text(survey, cfg)
    assert result.by_role.loc["Business", "mean"] == -1
    assert result.by_role.loc["Engineering", "mean"] == 1
    assert calls.count("Coding") == 4 * 6 and calls.count("Synthesis") == 1
    # second run is served from cache
    calls.clear()
    llm.analyse_text(survey, cfg)
    assert calls == []


def test_codebook_rejects_unknown_theme():
    from mra.llm import AnswerCode
    with pytest.raises(Exception):
        AnswerCode(item_id=1, sentiment=0, stance="neutral", themes=["Made up"], reasons=[])


def test_redaction():
    from mra.llm import redact
    text = redact("Mail jane.doe@corp.com or call +49 170 1234567, see https://wiki/x — ask Jane", ["Jane"])
    assert "@" not in text and "1234567" not in text and "https" not in text and "Jane" not in text


def test_gateway_settings(monkeypatch):
    from mra.config import LLMSettings
    from mra.llm import LLMClient
    monkeypatch.setenv("AI_GATEWAY_API_KEY", "k")
    monkeypatch.delenv("MRA_LLM_MODEL", raising=False)
    assert LLMClient.from_settings(LLMSettings()).model == "anthropic/claude-opus-5.5"
    monkeypatch.setenv("MRA_LLM_MODEL", "anthropic/claude-haiku-5.5")
    c = LLMClient.from_settings(LLMSettings())
    assert (c.model, c.api_key) == ("anthropic/claude-haiku-5.5", "k")
    monkeypatch.delenv("AI_GATEWAY_API_KEY")
    with pytest.raises(RuntimeError, match="AI_GATEWAY_API_KEY"):
        LLMClient.from_settings(LLMSettings()).require_key()


def test_sample_report_builds(tmp_path):
    from mra.report import build_report, run_analysis
    cfg = load_config(ROOT / "assessment.yaml")
    cfg.stats.bootstrap_iterations = 200
    cfg.stats.permutation_iterations = 200
    build = ROOT / "Output" / "build-test"
    try:
        pdf = build_report(cfg, run_analysis(cfg), tmp_path / "report.pdf", build_dir=build)
        assert pdf.stat().st_size > 50_000
    finally:
        shutil.rmtree(build, ignore_errors=True)
