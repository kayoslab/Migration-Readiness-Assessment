"""Assemble analysis results into a report context and compile it with Typst."""

from __future__ import annotations

import json
import math
import shutil
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from . import charts
from .config import Config
from .data import Survey, load_survey
from .scoring import (CONDITIONAL, INSUFFICIENT, NOT_READY, PROCEED, GroupResult, Verdict, item_statistics,
                      reliability, reliability_summary, role_differences, score_groups, verdict)

VERDICT_TONE = {PROCEED: "positive", CONDITIONAL: "caution", NOT_READY: "negative", INSUFFICIENT: "neutral"}


@dataclass
class Analysis:
    survey: Survey
    domains: GroupResult
    themes: GroupResult
    items: pd.DataFrame
    reliability: pd.DataFrame
    role_diff: pd.DataFrame
    verdict: Verdict
    text: object | None = None   # llm.TextAnalysis


def run_analysis(cfg: Config, with_llm: bool = False) -> Analysis:
    survey = load_survey(cfg)
    domains = score_groups(survey, cfg, "Category")
    themes = score_groups(survey, cfg, "Theme")
    rel = reliability(survey, cfg, "Category")
    analysis = Analysis(survey, domains, themes, item_statistics(survey, cfg), rel,
                        role_differences(domains, cfg.rules), verdict(domains, survey, cfg))
    if with_llm and len(survey.text):
        from .llm import analyse_text
        analysis.text = analyse_text(survey, cfg)
    return analysis


# --------------------------------------------------------------------------- helpers

def _num(x, digits=2):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return None
    return round(float(x), digits)


def _join(items: list[str]) -> str:
    items = list(items)
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def effect_label(eps: float) -> str:
    """Epsilon-squared magnitude (Tomczak & Tomczak, 2014)."""
    if eps is None or np.isnan(eps):
        return "n/a"
    return "large" if eps >= 0.26 else "moderate" if eps >= 0.08 else "small" if eps >= 0.01 else "negligible"


def _fmt_date(d) -> str:
    return f"{d.day} {d.strftime('%B %Y')}"


# --------------------------------------------------------------------------- narrative

def key_messages(a: Analysis, cfg: Config) -> list[str]:
    r, s, v = cfg.rules, a.domains.summary, a.verdict
    msgs = []
    org = cfg.engagement.get("organisation", "The organisation")
    if v.decision == INSUFFICIENT:
        msgs.append(f"The evidence gathered is not sufficient to form a view: {v.reasons[0]}")
    elif v.decision == NOT_READY:
        msgs.append(f"On the basis of the evidence gathered, {org} is not yet ready to commit to the programme. "
                    f"{_join(v.blocking)} {'presents' if len(v.blocking) == 1 else 'present'} a material constraint "
                    "that should be resolved before a delivery timeline is agreed.")
    elif v.decision == CONDITIONAL:
        msgs.append(f"{org} demonstrates a workable foundation, but readiness is not yet consistent across "
                    f"domains. Progress should be conditional on addressing {_join(v.blocking[:3])}.")
    else:
        msgs.append(f"{org} demonstrates readiness across all six domains, and no stakeholder group reports a "
                    "material constraint. Planning may proceed, with the residual gaps monitored.")

    ranked = s.dropna(subset=["index"]).sort_values("index")
    weakest = ranked.head(2)
    strongest = ranked.tail(1)
    msgs.append("The principal constraints are " + _join([f"{g} ({row['index']:.1f})" for g, row in weakest.iterrows()])
                + f"; the relative strength is {strongest.index[0]} ({strongest['index'].iat[0]:.1f}).")

    if len(a.role_diff):
        top = a.role_diff.sort_values("epsilon_sq", ascending=False).iloc[0]
        g = top.name
        if top["q"] < 0.05 and top["epsilon_sq"] >= 0.08:
            hi, lo = s.at[g, "max_role"], s.at[g, "min_role"]
            msgs.append(f"Stakeholder perceptions diverge most on {g}: {hi} rates it "
                        f"{s.at[g, 'max_role_score']:.1f}, {lo} {s.at[g, 'min_role_score']:.1f}. This difference is "
                        f"{effect_label(top['epsilon_sq'])} and unlikely to be due to chance; it warrants a facilitated "
                        "alignment discussion.")

    single = [g for g in s.index if len(s.at[g, "roles_scored"]) == 1]
    if single:
        msgs.append(f"{_join(single)} {'is' if len(single) == 1 else 'are'} assessed by a single stakeholder group "
                    f"({_join(sorted({s.at[g, 'roles_scored'][0] for g in single}))}); these findings should be "
                    "corroborated before they inform investment decisions.")

    if v.evidence == "indicative":
        small = [r for r in (r.essential_roles or a.survey.roles)
                 if (a.survey.respondents["role"] == r).sum() < cfg.rules.strong_evidence_role_n]
        msgs.append(f"Findings are indicative rather than conclusive: {_join(small)} "
                    f"{'is' if len(small) == 1 else 'are'} represented by fewer than "
                    f"{cfg.rules.strong_evidence_role_n} respondents.")
    return msgs


def next_steps(a: Analysis, cfg: Config) -> list[dict]:
    s, steps = a.domains.summary, []
    items = a.items
    for g in s.index:
        if s.at[g, "status"] == "RED" or g in a.verdict.blocking:
            low = items[items["domain"] == g].dropna(subset=["score"]).nsmallest(3, "score")
            steps.append({"title": f"Remediate {g}",
                          "body": "Agree an owner and a time-boxed plan for the lowest-scoring statements: "
                                  + "; ".join(f"“{q}” ({sc:.1f})" for q, sc in zip(low["question"], low["score"]))
                                  + "."})
    for g in a.role_diff.index if len(a.role_diff) else []:
        row = a.role_diff.loc[g]
        if row["q"] < 0.05 and row["epsilon_sq"] >= 0.26:
            steps.append({"title": f"Align perspectives on {g}",
                          "body": f"Convene {s.at[g, 'max_role']} and {s.at[g, 'min_role']} to reconcile their "
                                  f"assessments ({s.at[g, 'max_role_score']:.1f} vs {s.at[g, 'min_role_score']:.1f}) "
                                  "and agree a shared fact base."})
    single = [g for g in s.index if len(s.at[g, "roles_scored"]) == 1]
    if single:
        steps.append({"title": "Corroborate single-perspective domains",
                      "body": f"Validate {_join(single)} with additional evidence (delivery metrics, architecture "
                              "review) or additional stakeholder groups before relying on the score."})
    if a.verdict.evidence != "strong":
        steps.append({"title": "Strengthen the evidence base",
                      "body": f"Increase participation to at least {cfg.rules.strong_evidence_role_n} respondents per "
                              "essential stakeholder group and repeat the assessment."})
    steps.append({"title": "Confirm the case for change",
                  "body": "This assessment measures readiness to execute. It does not by itself establish that the "
                          "proposed migration is the right course; the underlying need, alternatives considered and "
                          "total cost of ownership should be reviewed alongside it."})
    return steps


# --------------------------------------------------------------------------- context

def build_context(a: Analysis, cfg: Config, chart_paths: dict[str, str]) -> dict:
    rules, s = cfg.rules, a.domains.summary
    rel = reliability_summary(a.reliability, rules)
    n_by_role = a.survey.respondents["role"].value_counts()

    def evidence(n):
        return "not scored" if n < rules.min_role_n else "indicative" if n < rules.strong_evidence_role_n else "strong"

    domains = []
    for g, row in s.iterrows():
        domains.append({
            "name": g, "index": _num(row["index"]), "ci_low": _num(row["ci_low"]), "ci_high": _num(row["ci_high"]),
            "status": row["status"], "probability": _num(row["status_probability"]),
            "uncertain": bool(row["uncertain"]), "roles_scored": row["roles_scored"],
            "roles_not_scored": row["roles_not_scored"],
            "min_role": row["min_role"], "min_role_score": _num(row["min_role_score"]),
            "alpha": _num(rel.at[g, "median_alpha"]) if g in rel.index else None,
            "reliable": bool(rel.at[g, "reliable"]) if g in rel.index else None,
        })

    diffs = []
    for g, row in (a.role_diff.iterrows() if len(a.role_diff) else []):
        diffs.append({"domain": g, "high_role": s.at[g, "max_role"], "high": _num(s.at[g, "max_role_score"]),
                      "low_role": s.at[g, "min_role"], "low": _num(s.at[g, "min_role_score"]),
                      "spread": _num(row["spread"]), "effect": effect_label(row["epsilon_sq"]),
                      "epsilon_sq": _num(row["epsilon_sq"]), "q": _num(row["q"], 3),
                      "significant": bool(row["q"] < 0.05)})

    it = a.items.dropna(subset=["score"])
    weakest = it.nsmallest(10, "score")
    gaps = a.items[a.items["gap_q"] < 0.05].sort_values("gap", ascending=False)

    themes = [{"name": g, "index": _num(row["index"]), "status": row["status"], "uncertain": bool(row["uncertain"]),
               "roles_scored": row["roles_scored"]}
              for g, row in a.themes.summary.sort_values("index").iterrows() if not np.isnan(row["index"])]

    text = None
    if a.text is not None:
        quotes = {q["id"]: q for q in a.text.quotes}
        text = {
            "model": a.text.model,
            "answers": int(len(a.text.coded)),
            "key_messages": a.text.synthesis.get("key_messages", []),
            "themes": [{"theme": t["theme"], "finding": t["finding"],
                        "quotes": [{"role": quotes[i]["role"], "text": quotes[i]["text"]}
                                   for i in t.get("quote_ids", []) if i in quotes][:2]}
                       for t in a.text.synthesis.get("themes", [])],
        }

    v = a.verdict
    return {
        "engagement": {**{k: v for k, v in cfg.engagement.items() if k != "date"},
                       "date": _fmt_date(cfg.report_date)},
        "verdict": {"decision": v.decision, "tone": VERDICT_TONE[v.decision], "evidence": v.evidence,
                    "reasons": v.reasons},
        "key_messages": key_messages(a, cfg),
        "respondents": [{"role": r, "n": int(n_by_role.get(r, 0)), "weight": rules.weight(r),
                         "evidence": evidence(int(n_by_role.get(r, 0))),
                         "essential": r in (rules.essential_roles or a.survey.roles)} for r in a.survey.roles],
        "respondents_total": int(len(a.survey.respondents)),
        "items_scored": int(a.survey.questionnaire["Type"].eq("Quantitative").sum()),
        "answers": int(a.survey.likert["value"].notna().sum()),
        "missing_rate": _num(a.survey.likert["value"].isna().mean(), 3),
        "dont_know_rate": _num(a.survey.likert["dont_know"].mean(), 3),
        "domains": domains,
        "role_differences": diffs,
        "weakest_items": [{"id": int(i), "question": r["question"], "domain": r["domain"], "score": _num(r["score"]),
                           "n": int(r["n"]), "agree": _num(r["pct_agree"]), "disagree": _num(r["pct_disagree"]),
                           "critical": bool(r["critical"])} for i, r in weakest.iterrows()],
        "critical_red": [{"id": int(i), "question": r["question"], "domain": r["domain"], "score": _num(r["score"])}
                         for i, r in it[(it["critical"]) & (it["score"] < rules.red_below)].sort_values("score").iterrows()],
        "gaps": [{"id": int(i), "question": r["question"], "gap": _num(r["gap"]), "high_role": r["gap_high_role"],
                  "low_role": r["gap_low_role"], "q": _num(r["gap_q"], 3)} for i, r in gaps.head(10).iterrows()],
        "gaps_tested": int(a.items["gap_p"].notna().sum()),
        "themes": themes,
        "text": text,
        "next_steps": next_steps(a, cfg),
        "rules": {"signed_off_by": rules.signed_off_by, "red_below": rules.red_below, "green_from": rules.green_from,
                  "proceed_from": rules.proceed_from, "confidence": rules.confidence, "min_role_n": rules.min_role_n,
                  "min_role_items": rules.min_role_items, "strong_evidence_role_n": rules.strong_evidence_role_n,
                  "min_item_coverage": rules.min_item_coverage, "min_reliability": rules.min_reliability,
                  "essential_roles": rules.essential_roles or a.survey.roles,
                  "role_veto_domains": rules.role_veto_domains,
                  "bootstrap_iterations": cfg.stats.bootstrap_iterations},
        "charts": chart_paths,
    }


def render_charts(a: Analysis, cfg: Config, out_dir: Path) -> dict[str, str]:
    paths = {
        "domain_index": charts.domain_index_chart(a.domains.summary, cfg.rules, out_dir / "domain_index.svg"),
        "role_heatmap": charts.role_heatmap(a.domains, cfg.rules, out_dir / "role_heatmap.svg"),
        "likert": charts.likert_chart(a.items.dropna(subset=["score"]).nsmallest(10, "score"), out_dir / "likert.svg"),
    }
    if a.text is not None:
        paths["stance"] = charts.stance_chart(a.text.by_role, out_dir / "stance.svg")
        paths["themes"] = charts.theme_heatmap(a.text.theme_share, out_dir / "text_themes.svg")
    return {k: "/" + str(p.resolve().relative_to(cfg.root)) for k, p in paths.items()}


def build_report(cfg: Config, a: Analysis, output: Path | None = None, build_dir: Path | None = None) -> Path:
    """Render charts and report.json into `build_dir` (must be inside cfg.root for Typst) and compile."""
    import typst

    output = Path(output or cfg.report_output)
    build = Path(build_dir or cfg.root / "Output" / "build")
    if build.exists():
        shutil.rmtree(build)
    build.mkdir(parents=True)
    context = build_context(a, cfg, render_charts(a, cfg, build / "charts"))
    data_path = build / "report.json"
    data_path.write_text(json.dumps(context, indent=1, ensure_ascii=False, default=str))

    main = cfg.report_template / "main.typ"
    output.parent.mkdir(parents=True, exist_ok=True)
    font_dirs = [str(p) for p in [cfg.report_template / "fonts"] if p.exists()]
    typst.compile(str(main), output=str(output), root=str(cfg.root), font_paths=font_dirs,
                  sys_inputs={"data": "/" + str(data_path.relative_to(cfg.root))})
    return output
