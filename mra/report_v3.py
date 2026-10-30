"""v3 report: recommended path per decision, preconditions, economics, stakeholder perspectives, next steps."""

from __future__ import annotations

import datetime as dt
import json
import shutil
from pathlib import Path

import numpy as np

from . import charts
from .decision import Context, evaluate
from .explain import (OPS, STATUS_WORDS, condition_label, flip_sentence, fmt, inputs_of, outcome_label,
                      signal_label, uncertainty_sentence)
from .recommend import next_steps

TEMPLATE = Path(__file__).resolve().parents[1] / "report" / "templates" / "default"
TONE = {"go": "positive", "prepare_first": "caution", "insufficient": "neutral"}
TITLES = {"architecture": "Architecture", "hosting": "Hosting"}
CURRENT = {"single_deployable": "one main deployable (monolith)", "distributed": "several independently deployed services",
           "own_infrastructure": "own infrastructure", "cloud": "public cloud", "hybrid": "hybrid"}


def _met_leaves(cond, ctx: Context) -> list[dict]:
    """The leaf conditions that make `cond` true (the satisfied branch of an any)."""
    if cond is None:
        return []
    if isinstance(cond, list):
        cond = {"all": cond}
    if "all" in cond:
        return [leaf for c in cond["all"] for leaf in _met_leaves(c, ctx)]
    if "any" in cond:
        branch = next((c for c in cond["any"] if evaluate(c, ctx) is True), None)
        return _met_leaves(branch, ctx) if branch else []
    if "not" in cond:
        return []
    spec = ctx.rules.get("signals", {}).get(cond.get("signal", ""), {})
    if isinstance(ctx.get(cond["signal"]), bool) and any(k in spec for k in ("all", "any")):
        return _met_leaves({k: v for k, v in spec.items() if k in ("all", "any")}, ctx)
    return [cond] if evaluate(cond, ctx) is True else []


def _why(decision: str, outcome: str | None, assessment, limit: int = 4) -> list[str]:
    if not outcome or outcome == "insufficient_evidence":
        return []
    ins, ev = assessment.engagement.instrument, assessment.evidence
    spec = next((o for o in ins.rules["decisions"][decision]["outcomes"] if o["id"] == outcome), None)
    if not spec:
        return []
    ctx = Context(ev.at(0), ins.rules, ev.current_state, decision)
    out = []
    for c in _met_leaves(spec.get("when"), ctx)[:limit]:
        value = ctx.get(c["signal"])
        threshold = ctx.get(c["ref"]) if "ref" in c else c.get("value")
        if value is None or isinstance(value, bool):
            continue
        out.append(f"{signal_label(c['signal'], ins)}: {fmt(value)} (threshold: {OPS[c['op']] or 'equal to'} {fmt(threshold)}).")
    return out


def _summary_text(ins, decision: str, outcome: str | None, need: float | None) -> str:
    spec = ins.outcomes.get(decision, {}).get(outcome or "", {}) or ins.outcomes["common"].get(outcome or "", {})
    summary = spec.get("summary", "")
    if isinstance(summary, dict):
        summary = summary["low_need"] if need is not None and need < 2.5 else summary["problems_would_follow"]
    return " ".join(str(summary).split())


def _evidence_strength(assessment) -> str:
    """Based on the groups that are scored (smaller groups do not count towards the verdict at all)."""
    sizes = assessment.engagement.respondents["role"].value_counts()
    ev = assessment.engagement.instrument.rules.get("evidence", {})
    scored = sizes[sizes >= ev.get("min_role_n", 5)]
    if len(scored) < 3:
        return "limited"
    return "strong" if scored.min() >= ev.get("strong_evidence_role_n", 15) else "indicative"


def _rel(path: Path, root: Path) -> str:
    """Typst paths are relative to the project root; outside it (context only, no compile) keep the absolute path."""
    try:
        return "/" + str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path.resolve())


def build_context(assessment, out: Path, root: Path) -> dict:
    eng, ins, ev = assessment.engagement, assessment.engagement.instrument, assessment.evidence
    cfg = eng.config.get("report", {}) or {}
    cdir = out / "charts"
    point = ev.at(0)
    decisions = []
    for d, r in assessment.results.items():
        order = [o["id"] for o in ins.rules["decisions"][d]["outcomes"]]
        labels = {o: outcome_label(ins, d, o) for o in order + ["insufficient_evidence", "unresolved"]}
        target = r.verdict if r.verdict != "insufficient_evidence" else r.leaning
        block = {
            "id": d, "title": TITLES.get(d, d.title()),
            "current": CURRENT.get(r.current_state, r.current_state),
            "verdict": r.verdict, "verdict_label": labels.get(r.verdict, r.verdict),
            "status": r.status, "status_label": STATUS_WORDS[r.status], "tone": TONE[r.status],
            "probability": r.probability,
            "leaning_label": labels.get(r.leaning) if r.leaning else None,
            "summary": _summary_text(ins, d, target, point.get("need.architecture")),
            "why": _why(d, target, assessment),
            "hard_stops": [ins.rules["hard_stops"][h]["label"] for h in r.hard_stops],
            "capabilities": [condition_label(c, ins) for c in r.unmet_capabilities],
            "gates": [{"id": g, "label": info["label"], "status": info["status"], "corroboration": info["corroboration"]}
                      for g, info in r.gates.get("required", {}).items()],
            "conditions": [{"label": info["label"], "status": info["status"]}
                           for info in r.gates.get("conditions", {}).values()],
            "interim_label": labels.get(r.interim) if r.interim else None,
            "flips": [flip_sentence(f, d, ins) for f in r.what_would_change],
            "excluded": [labels.get(e.split(" (")[0], e) for e in r.excluded],
            "notes": r.notes,
            "shadow_label": labels.get(r.shadow["verdict"]) if r.shadow and r.shadow["verdict"] != r.verdict else None,
            "unresolved_share": r.unresolved_share,
            "uncertain": [{"text": uncertainty_sentence(x, ins),
                           "facts": [ins.facts.at[f, "label"] for f in inputs_of(x["signal"], ins)["facts"]][:4],
                           "items": len(inputs_of(x["signal"], ins)["items"])} for x in r.uncertain_inputs],
            "charts": {"probabilities": _rel(charts.outcome_probability_chart(
                r.distribution, labels, r.verdict if r.verdict != "insufficient_evidence" else r.leaning,
                ins.rules.get("evidence", {}).get("confidence", 0.8), cdir / f"{d}_probabilities.svg"), root)},
        }
        if d == "architecture" and "need.architecture" in ev.signals:
            floor = np.nanmin(np.stack([ev.signals.get(f"capability.architecture.{a}", np.full(ev.draws, np.nan))
                                        for a in ("delivery_pipeline", "platform_basics", "operations")]), axis=0)
            block["charts"]["map"] = _rel(charts.need_capability_map(ev.signals["need.architecture"], floor,
                                                                     cdir / "architecture_map.svg"), root)
            block["fit"] = [{"outcome": labels.get(k.split(".", 1)[1]), "requirement": signal_label(c["signal"], ins),
                             "threshold": c["threshold"], "current": c["current"], "met": c["met"]}
                            for k, conds in (assessment.stakes.fit if assessment.stakes else {}).items()
                            if k.startswith("architecture.") for c in conds]
        if d == "hosting" and r.economics:
            words = {"stay": "Keep as is", "improve_current": "Improve / right-size", "cloud": "Move to cloud",
                     "hybrid": "Hybrid", "repatriate": "Move back from cloud"}
            ranges = {}
            for o in r.economics["ratio"]:
                v = ev.signals[f"tco_ratio.{o}"]
                ranges[o] = (float(np.nanpercentile(v, 5)), float(v[0]), float(np.nanpercentile(v, 95)))
            block["charts"]["tco"] = _rel(charts.tco_chart(ranges, words, cdir / "hosting_tco.svg"), root)
            if len(r.economics.get("tornado", [])) > 1:
                block["charts"]["tornado"] = _rel(charts.tornado_chart(
                    r.economics["tornado"], lambda f: signal_label(f"fact.{f}", ins), cdir / "hosting_tornado.svg"), root)
            block["economics"] = [{"option": words.get(o, o), "ratio": round(ranges[o][1], 2),
                                   "range": f"{ranges[o][0]:.2f}–{ranges[o][2]:.2f}",
                                   "payback": (None if point.get(f"payback_after_cutover.{o}") in (None, float("inf"))
                                               else round(point[f"payback_after_cutover.{o}"])),
                                   "saving_fte": round(point.get(f"tco_saving_fte.{o}") or 0, 1)}
                                  for o in sorted(ranges, key=lambda o: ranges[o][1])]
            block["tornado_option"] = words.get(r.economics.get("tornado_option"), "")
        decisions.append(block)

    # ---------------------------------------------------------------- stakeholders
    st = assessment.stakes
    stakes = {"findings": st.findings if st else [], "suppressed": st.suppressed if st else [], "charts": []}
    if st:
        for d, prefs in st.preferences.items():
            order = [o["id"] for o in ins.rules["decisions"][d]["outcomes"]]
            labels = {o: outcome_label(ins, d, o) for o in order}
            if prefs["by_group"]:
                stakes["charts"].append({"title": f"Preferred {d} direction by group",
                                         "path": _rel(charts.preference_chart(prefs["by_group"], order, labels,
                                                                              cdir / f"{d}_preferences.svg"), root)})
            if st.stakes_by_option.get(d):
                stakes["charts"].append({"title": f"Expected effect of each {d} option on respondents' own roles and skills",
                                         "path": _rel(charts.stakes_heatmap(st.stakes_by_option[d], order, labels,
                                                                            cdir / f"{d}_stakes.svg"), root)})
    divergence = [{"label": signal_label(d["sub_area"], ins), "fact": d["fact_band"], "survey": d["survey"]}
                  for d in ev.divergences]
    if divergence:
        stakes["divergence_chart"] = _rel(charts.divergence_chart(divergence, cdir / "divergence.svg"), root)

    # ---------------------------------------------------------------- organisational readiness by group
    from .readiness import analyse as analyse_readiness
    min_n = ins.rules.get("evidence", {}).get("min_role_n", 5)
    rd = analyse_readiness(eng, min_n)
    readiness = {"differences": [], "weakest": rd.weakest, "charts": {}}
    if not rd.matrix.empty:
        readiness["charts"]["matrix"] = _rel(charts.group_matrix_heatmap(rd.matrix, rd.counts, min_n,
                                                                         cdir / "readiness_matrix.svg"), root)
    if rd.weakest:
        readiness["charts"]["weakest"] = _rel(charts.score_distribution_chart(rd.weakest, cdir / "readiness_weakest.svg"), root)
    readiness["differences"] = [{"sub_area": d["sub_area"], "high": f"{d['high'][0]} ({d['high'][1]})",
                                 "low": f"{d['low'][0]} ({d['low'][1]})", "spread": d["spread"], "effect": d["effect"],
                                 "significant": d["significant"]} for d in rd.differences[:8]]

    # ---------------------------------------------------------------- evidence appendix
    rows = []
    for name, values in sorted(ev.signals.items()):
        head = name.split(".")[0]
        if head in ("need", "capability", "fit", "requirement", "locality") and name.count(".") >= 1 or name == "locality":
            v = values[0]
            if not np.isnan(v):
                lo, hi = np.nanpercentile(values, [2.5, 97.5])
                rows.append({"signal": signal_label(name, ins), "group": head, "value": round(float(v), 2),
                             "range": f"{lo:.1f}–{hi:.1f}"})
    sizes = eng.respondents["role"].value_counts().to_dict() if len(eng.respondents) else {}

    key = []
    for b in decisions:
        p = f"{b['probability']:.0%}"
        if b["status"] == "insufficient":
            key.append(f"{b['title']}: the evidence does not yet support a single path"
                       + (f"; it leans towards “{b['leaning_label']}” ({p})." if b["leaning_label"] else "."))
        else:
            sentence = f"{b['title']}: “{b['verdict_label']}” is supported by the evidence ({p} of draws)"
            if b["status"] == "prepare_first":
                sentence += ", but preconditions must be met before committing"
                if b["interim_label"]:
                    sentence += f"; meanwhile, “{b['interim_label']}”"
            key.append(sentence + ".")
    if not rd.matrix.empty:
        counted = rd.matrix.where(rd.counts >= min_n)
        area_scores = counted.mean(axis=1).dropna().sort_values()
        weak = [f"{name.split(': ', 1)[-1]} ({v:.1f})" for name, v in area_scores.head(2).items()]
        if weak:
            key.append(f"The weakest areas of readiness are {' and '.join(weak)}.")
    strong_diff = [d for d in rd.differences if d["significant"] and d["effect"] == "large"]
    if strong_diff:
        d = strong_diff[0]
        key.append(f"Groups see \u201c{d['sub_area'].split(': ', 1)[-1]}\u201d very differently "
                   f"({d['high'][0]} {d['high'][1]:.1f} vs {d['low'][0]} {d['low'][1]:.1f}).")
    if st and st.findings:
        key.append(f"{len(st.findings)} findings on stakeholder perspectives should inform how the decision is communicated.")

    rules = ins.rules
    return {
        "engagement": {
            "organisation": cfg.get("organisation", eng.system), "title": cfg.get("title", "Architecture and Hosting Assessment"),
            "subtitle": cfg.get("subtitle", f"Recommended direction for {eng.system}"),
            "prepared_for": cfg.get("prepared_for", ""), "prepared_by": cfg.get("prepared_by", ""),
            "date": cfg.get("date") or f"{dt.date.today().day} {dt.date.today():%B %Y}",
            "classification": cfg.get("classification", "Strictly confidential"), "sample_data": cfg.get("sample_data", False),
        },
        "system": eng.system,
        "key_messages": key,
        "decisions": decisions,
        "stakes": stakes,
        "readiness": readiness,
        "steps": next_steps(assessment),
        "evidence": rows,
        "participation": [{"group": g, "n": int(n)} for g, n in sizes.items()],
        "evidence_strength": _evidence_strength(assessment),
        "problems": assessment.problems,
        "fact_checks": [{"severity": f.severity, "message": f.message} for f in assessment.fact_checks],
        "rules": {"version": rules.get("version"), "signed_off_by": rules.get("signed_off_by"),
                  "confidence": rules.get("evidence", {}).get("confidence", 0.8),
                  "draws": ev.draws, "min_role_n": rules.get("evidence", {}).get("min_role_n", 5)},
        "text": None if assessment.text is None else {
            "model": assessment.text.model, "answers": int(len(assessment.text.coded)),
            "key_messages": assessment.text.synthesis.get("key_messages", [])},
    }


def build_report(assessment, output: Path, template: Path = TEMPLATE) -> Path:
    import typst
    root = Path(__file__).resolve().parents[1]
    out = root / "Output" / "build-v3" / output.stem
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    context = build_context(assessment, out, root)
    data = out / "report.json"
    data.write_text(json.dumps(context, indent=1, ensure_ascii=False, default=str))
    output.parent.mkdir(parents=True, exist_ok=True)
    fonts = [str(p) for p in [template / "fonts"] if p.exists()]
    typst.compile(str(template / "decision.typ"), output=str(output), root=str(root), font_paths=fonts,
                  sys_inputs={"data": _rel(data, root)})
    return output
