"""v3 report: recommended path per decision, preconditions, economics, stakeholder perspectives, next steps."""

from __future__ import annotations

import datetime as dt
import json
import shutil
from pathlib import Path

import numpy as np

from . import charts
from . import interpret
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


def _why(decision: str, outcome: str | None, assessment, limit: int = 8) -> list[str]:
    if not outcome or outcome == "insufficient_evidence":
        return []
    ins, ev = assessment.engagement.instrument, assessment.evidence
    spec = next((o for o in ins.rules["decisions"][decision]["outcomes"] if o["id"] == outcome), None)
    if not spec:
        return []
    ctx = Context(ev.at(0), ins.rules, ev.current_state, decision)
    out = []
    from .appraisal import _shown
    for c in _met_leaves(spec.get("when"), ctx)[:limit]:
        value = ctx.get(c["signal"])
        threshold = ctx.get(c["ref"]) if "ref" in c else c.get("value")
        if value is None:
            continue
        if isinstance(value, bool):                    # derived yes/no conditions, e.g. a distinct component
            out.append(f"{signal_label(c['signal'], ins)}: {'yes' if value else 'no'}.")
            continue
        out.append(f"{signal_label(c['signal'], ins)}: {_shown(c['signal'], value, ins)} "
                   f"(threshold: {OPS[c['op']] or 'equal to'} {_shown(c['signal'], threshold, ins)}).")
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


def _lead_time_split(eng, ins) -> dict:
    """Shares of the lead-time answers per bucket, by group, using the answer groupings of the decision rules."""
    from .charts import LEAD_TIME_BUCKETS
    sig = ins.rules.get("signals", {})
    if "coordination_share" not in sig or "wait_state_share" not in sig:
        return {}
    coord, wait = set(sig["coordination_share"]["share_of"]), set(sig["wait_state_share"]["share_of"])
    ans = eng.answers[(eng.answers["item_id"] == sig["coordination_share"]["item"]) & eng.answers["row"].isna()
                      & (eng.answers["label"].fillna("") != "") & ~eng.answers["dont_know"].fillna(False).astype(bool)]
    if ans.empty:
        return {}

    def bucket(label):
        return (LEAD_TIME_BUCKETS[0] if label in coord else LEAD_TIME_BUCKETS[1] if label in wait else
                LEAD_TIME_BUCKETS[3] if label == "No single main cause" else LEAD_TIME_BUCKETS[2])
    ans = ans.assign(bucket=ans["label"].map(bucket))
    min_n = ins.rules.get("evidence", {}).get("min_role_n", 5)
    sizes = ans["role"].value_counts()
    small = sizes[sizes < min_n].index
    ans = ans.assign(group=ans["role"].where(~ans["role"].isin(small), "Other groups"))
    if (ans["group"] == "Other groups").sum() and (ans["group"] == "Other groups").sum() < min_n:
        ans = ans[ans["group"] != "Other groups"]                    # too few to show even when pooled
    out = {g: (sub["bucket"].value_counts(normalize=True)).round(3).to_dict() for g, sub in ans.groupby("group")}
    out["All respondents asked"] = ans["bucket"].value_counts(normalize=True).round(3).to_dict()
    return out


def _eur(x: float, signed: bool = False) -> str:
    sign = ("+" if x > 0 else "−" if x < 0 else "") if signed else ("−" if x < 0 else "")
    x = abs(x)
    return f"{sign}€{x / 1e6:.2f}M" if x >= 1e6 else f"{sign}€{x / 1e3:,.0f}k"


SOURCING_STATUS = {"go": "Proceed", "prepare_first": "Prepare first", "insufficient": "Insufficient evidence",
                   "excluded": "Keep — replacing is ruled out"}


def _sourcing_context(assessment, cdir: Path, root: Path, register) -> dict | None:
    """Build or buy per candidate part: verdict, why, what would change it, cost in euros, seam and gates."""
    parts = assessment.sourcing
    if not parts:
        return None
    eng, ins = assessment.engagement, assessment.engagement.instrument
    spec = ins.rules["sourcing"]
    labels = {k: v["label"] for k, v in ins.outcomes.get("sourcing", {}).items()}
    labels["insufficient_evidence"] = "Not yet decided: the evidence is insufficient"
    show = (eng.config.get("report") or {}).get("show_amounts", True)
    arch = assessment.results.get("architecture")
    blocks = []
    for p in parts:
        seam_note = None
        if p.get("seam") is not None and p["seam"] > spec["seam"]["at_most"]:
            seam_note = (f"{p['seam']:.0f}% of the part's tables are also written by other parts (at most "
                         f"{spec['seam']['at_most']}% for a clean switch): its data must be separated first")
            if arch and arch.verdict in ("modular_monolith", "broad_decomposition", "targeted_extraction"):
                seam_note += ", which the architecture restructuring's step on data ownership delivers."
            else:
                seam_note += "."
        blocks.append({**{k: v for k, v in p.items() if k not in ("missing",)},
                       "label": labels.get(p["verdict"], p["verdict"]),
                       "summary": ins.outcomes.get("sourcing", {}).get(p["verdict"], {}).get("summary", ""),
                       "status_label": ("No change" if p["verdict"] == "keep_building" and p["status"] == "go"
                                        else SOURCING_STATUS.get(p["status"], p["status"])),
                       "tone": TONE.get(p["status"], "neutral"),
                       "missing": p.get("missing", []), "seam_note": seam_note, "show_amounts": show,
                       "costs": None if p.get("build_eur") is None else {
                           "build": _eur(p["build_eur"]), "build_range": f"{_eur(p['build_range'][0])}–{_eur(p['build_range'][1])}",
                           "buy": _eur(p["buy_eur"]), "buy_range": f"{_eur(p['buy_range'][0])}–{_eur(p['buy_range'][1])}",
                           "ratio": f"{p['ratio']:.2f}", "ratio_range": f"{p['ratio_range'][0]:.2f}–{p['ratio_range'][1]:.2f}",
                           "payback": p["payback_months"], "integration": _eur(p["integration_cost"]),
                           "switch_months": round(p["switch_months"])}})
    rated = [b for b in blocks if b.get("differentiation") is not None]
    chart = insight = None
    if rated:
        chart = _rel(charts.sourcing_map(rated, spec["differentiation"]["commodity_below"],
                                         spec["replace_when"]["coverage_at_least"], cdir / "sourcing_map.svg"), root)
        insight = register("sourcing.map", interpret.sourcing(rated), [
            {k: b[k] for k in ("name", "verdict", "differentiation", "coverage", "ratio")} for b in rated])
    return {"parts": blocks, "chart": chart, "insight": insight,
            "rules": {"commodity_below": spec["differentiation"]["commodity_below"],
                      "coverage": spec["replace_when"]["coverage_at_least"],
                      "ratio": spec["replace_when"]["cost_ratio_at_most"]}}


def _readable_problem(problem: str, ins) -> str:
    """Data gaps for the report reader: labels, not field names (the CLI keeps the technical form)."""
    import re as _re

    def label(fid):
        return ins.facts.at[fid, "label"].split(" (")[0] if fid in ins.facts.index else fid.replace("_", " ")
    if problem.startswith("required fact missing: "):
        return f"Missing from the fact sheet: {label(problem.split(': ', 1)[1]).lower()}."
    if problem.startswith("hosting TCO not computed: missing "):
        return f"The hosting cost comparison could not be computed: {label(problem.rsplit(' ', 1)[1]).lower()} is missing."
    m = _re.match(r"fact (\w+): not in facts.csv", problem)
    if m:
        return f"The fact sheet contains an entry the instrument does not know ({m.group(1).replace('_', ' ')})."
    m = _re.match(r"(\w+): (\d+) column\(s\) do not match the form", problem)
    if m:
        return f"{m.group(2)} survey column(s) from {m.group(1)} could not be matched to the questionnaire."
    return problem


def _evidence_note(assessment) -> str:
    sizes = assessment.engagement.respondents["role"].value_counts()
    ev = assessment.engagement.instrument.rules.get("evidence", {})
    min_n, strong = ev.get("min_role_n", 5), ev.get("strong_evidence_role_n", 15)
    scored = sizes[sizes >= min_n]
    strength = _evidence_strength(assessment)
    return (f"Share of draws: how often the path applies when respondents and estimates are resampled. "
            f"Evidence {strength}: " + {
                "strong": f"every group counted has at least {strong} respondents.",
                "indicative": f"the smallest group counted has {int(scored.min()) if len(scored) else 0} respondents; "
                              f"{strong} or more per group would make it strong.",
                "limited": f"fewer than three groups reach {min_n} respondents."}[strength])


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
    from .integrity import run as run_integrity
    issues = run_integrity(assessment)                 # contradictions between the sources, applied throughout
    unverified = any(i.id == "baseline_unverified" for i in issues)
    decisions = []
    exhibits = []                       # every exhibit's insight, with the data behind it (used by the narrative)

    def register(eid: str, insight: dict, data) -> dict:
        insight = {"id": eid, **insight, "interpretation": None}
        exhibits.append({"insight": insight, "data": data})
        return insight
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
            # a single bar at 100% says nothing a sentence cannot: the exhibit then carries only its title and so-what
            "charts": {"probabilities": None if max(r.distribution.values(), default=0) >= 0.995 else
                       _rel(charts.outcome_probability_chart(
                           r.distribution, labels, r.verdict if r.verdict != "insufficient_evidence" else r.leaning,
                           ins.rules.get("evidence", {}).get("confidence", 0.8), cdir / f"{d}_probabilities.svg"), root)},
        }
        block["insights"] = {"probabilities": register(f"{d}.probabilities", interpret.outcome_probabilities(
            r.distribution, labels, r.verdict, r.leaning, ins.rules.get("evidence", {}).get("confidence", 0.8),
            r.status, r.unresolved_share), {"distribution": {labels.get(k, k): round(v, 3) for k, v in r.distribution.items()}})}
        if d == "architecture" and "need.architecture" in ev.signals:
            floor = np.nanmin(np.stack([ev.signals.get(f"capability.architecture.{a}", np.full(ev.draws, np.nan))
                                        for a in ("delivery_pipeline", "platform_basics", "operations")]), axis=0)
            block["charts"]["map"] = _rel(charts.need_capability_map(ev.signals["need.architecture"], floor,
                                                                     cdir / "architecture_map.svg"), root)
            need = ev.signals["need.architecture"]
            block["insights"]["map"] = register("architecture.map", interpret.need_capability(need, floor), {
                "need_point": round(float(need[0]), 2), "need_90pct": [round(float(x), 2) for x in np.nanpercentile(need, [5, 95])],
                "weakest_capability_point": round(float(floor[0]), 2), "thresholds": {"need": [2.5, 3.5], "capability": 3.5}})
            split = _lead_time_split(eng, ins)
            if split:
                cross = eng.facts.get("cross_team_change_pct")
                cross = None if cross is None or cross.point is None else float(cross.point)
                block["charts"]["leadtime"] = _rel(charts.lead_time_chart(split, cdir / "lead_time.svg"), root)
                block["insights"]["leadtime"] = register("architecture.leadtime", interpret.lead_time(split, cross),
                                                         {"by_group": split, "cross_team_change_pct": cross})
            block["fit"] = [{"outcome": labels.get(k.split(".", 1)[1]), "requirement": signal_label(c["signal"], ins),
                             "threshold": c["threshold"], "current": c["current"], "met": c["met"]}
                            for k, conds in (assessment.stakes.fit if assessment.stakes else {}).items()
                            if k.startswith("architecture.") for c in conds]
        if d == "hosting" and r.economics:
            words = {"stay": "Keep as is", "improve_current": "Improve / right-size", "cloud": "Move to cloud",
                     "hybrid": "Hybrid", "repatriate": "Move back from cloud"}
            ranges = {}                                  # every option relative to today's setup as it is
            stay = ev.signals["tco.stay"]
            for o in r.economics["ratio"]:
                v = ev.signals[f"tco.{o}"] / stay
                ranges[o] = (float(np.nanpercentile(v, 5)), float(v[0]), float(np.nanpercentile(v, 95)))
            block["charts"]["tco"] = _rel(charts.tco_chart(ranges, words, cdir / "hosting_tco.svg"), root)
            paybacks = {o: point.get(f"payback_after_cutover.{o}") for o in ranges
                        if point.get(f"payback_after_cutover.{o}") not in (None, float("inf"))}
            block["insights"]["tco"] = register("hosting.tco", interpret.tco(ranges, words, paybacks), {
                words.get(o, o): {"cost_ratio": round(v[1], 2), "range_90pct": [round(v[0], 2), round(v[2], 2)],
                                  "payback_months_after_cutover": paybacks.get(o)} for o, v in ranges.items()})
            if len(r.economics.get("tornado", [])) > 1:
                block["charts"]["tornado"] = _rel(charts.tornado_chart(
                    r.economics["tornado"], lambda f: signal_label(f"fact.{f}", ins), cdir / "hosting_tornado.svg"), root)
                option_word = words.get(r.economics.get("tornado_option"), "")
                block["insights"]["tornado"] = register("hosting.tornado", interpret.tornado(
                    r.economics["tornado"], lambda f: signal_label(f"fact.{f}", ins), option_word), {
                    "option": option_word, "base_ratio": round(r.economics["tornado"][0]["base"], 2),
                    "inputs": [{"input": signal_label(f"fact.{t['input']}", ins), "low": round(t["low"], 2),
                                "high": round(t["high"], 2)} for t in r.economics["tornado"][1:6]]})
            show = (eng.config.get("report") or {}).get("show_amounts", True)
            horizon = ins.rules["decisions"]["hosting"].get("horizon_years", 5)
            fte = float(point.get("fact.fte_cost_annual") or 0)

            def eur_row(o):
                v = ev.signals[f"tco.{o}"]
                saving = (float(stay[0]) - float(v[0])) / horizon if o != "stay" else 0.0
                return {"option": words.get(o, o), "ratio": 1.0 if o == "stay" else round(ranges[o][1], 2),
                        "range": "—" if o == "stay" and float(np.nanpercentile(stay / stay, 95)) == 1 else
                        (f"{ranges[o][0]:.2f}–{ranges[o][2]:.2f}" if o != "stay" else "—"),
                        "eur": _eur(float(v[0])) if show else None,
                        "eur_range": f"{_eur(float(np.nanpercentile(v, 5)))}–{_eur(float(np.nanpercentile(v, 95)))}"
                        if show else None,
                        "payback": (None if o == "stay" or point.get(f"payback_after_cutover.{o}") in (None, float("inf"))
                                    else round(point[f"payback_after_cutover.{o}"])),
                        "payback_from": "from the start" if o == "improve_current" else "after cut-over",
                        "saving_eur": (_eur(saving, signed=True) if show and o != "stay" else None),
                        "saving_fte": round(saving / fte, 1) if fte and o != "stay" else 0.0}
            block["economics"] = [eur_row("stay")] + [eur_row(o) for o in sorted(ranges, key=lambda o: ranges[o][1])]
            block["show_amounts"] = show
            from . import plan
            block["calendar"] = plan.calendar(assessment, show)
            block["inaction"] = plan.inaction(assessment, show)
            block["tornado_option"] = words.get(r.economics.get("tornado_option"), "")
        decisions.append(block)

    # ---------------------------------------------------------------- build or buy
    sourcing = _sourcing_context(assessment, cdir, root, register)

    # ---------------------------------------------------------------- stakeholders
    st = assessment.stakes
    stakes = {"findings": st.findings if st else [], "suppressed": st.suppressed if st else [], "charts": []}
    if st:
        for d, prefs in st.preferences.items():
            order = [o["id"] for o in ins.rules["decisions"][d]["outcomes"]]
            labels = {o: outcome_label(ins, d, o) for o in order}
            verdict = assessment.results[d].verdict if d in assessment.results else None
            if prefs["by_group"]:
                stakes["charts"].append({"source": f"Preferred {d} direction, share of each group's respondents.",
                                         "path": _rel(charts.preference_chart(prefs["by_group"], order, labels,
                                                                              cdir / f"{d}_preferences.svg"), root),
                                         "insight": register(f"{d}.preferences", interpret.preferences(
                                             prefs["by_group"], labels, verdict),
                                             {g: {labels.get(o, o): v for o, v in sh.items()} for g, sh in prefs["by_group"].items()})})
            if st.stakes_by_option.get(d):
                stakes["charts"].append({"source": f"Expected effect of each {d} option on respondents' own roles and "
                                                   "skills (\u22121 harms \u2026 +1 helps).",
                                         "path": _rel(charts.stakes_heatmap(st.stakes_by_option[d], order, labels,
                                                                            cdir / f"{d}_stakes.svg"), root),
                                         "insight": register(f"{d}.stakes", interpret.stakes(st.stakes_by_option[d], labels),
                                             {g: {labels.get(o, o): v for o, v in row.items()} for g, row in st.stakes_by_option[d].items()})})
    from .integrity import GROUP_NAMES
    sizes_all = eng.respondents["role"].value_counts()
    min_group = ins.rules.get("evidence", {}).get("min_role_n", 5)
    small = [(g, int(n)) for g, n in sizes_all.items() if 0 < n < min_group]
    if small:
        listed = [f"{GROUP_NAMES.get(g, g)} ({n})" for g, n in sorted(small, key=lambda x: -x[1])]
        listed = listed[0] if len(listed) == 1 else ", ".join(listed[:-1]) + " and " + listed[-1]
        stakes["pooled_note"] = (f"{listed} {'has' if len(small) == 1 else 'have'} fewer than {min_group} respondents. "
                                 "To protect anonymity, their answers appear together as “Other groups” and are not "
                                 "shown separately in the stakeholder map.")
    from .stakeholders import stakeholder_map
    smap = stakeholder_map(assessment)
    if smap:
        stakes["map"] = smap
        stakes["map_chart"] = _rel(charts.stakeholder_chart(smap, cdir / "stakeholder_map.svg"), root)
        stakes["map_insight"] = register("people.map", interpret.stakeholder_map(smap), smap)
    divergence = [{"label": signal_label(d["sub_area"], ins), "fact": d["fact_band"], "survey": d["survey"]}
                  for d in ev.divergences]
    if divergence:
        stakes["divergence_chart"] = _rel(charts.divergence_chart(divergence, cdir / "divergence.svg"), root)
        stakes["divergence_insight"] = register("people.divergence", interpret.divergence(divergence), divergence)

    # ---------------------------------------------------------------- organisational readiness by group
    from .readiness import analyse as analyse_readiness
    min_n = ins.rules.get("evidence", {}).get("min_role_n", 5)
    rd = analyse_readiness(eng, min_n)
    readiness = {"differences": [], "weakest": rd.weakest, "charts": {}}
    readiness["insights"] = {}
    if not rd.matrix.empty:
        readiness["charts"]["matrix"] = _rel(charts.group_matrix_heatmap(rd.matrix, rd.counts, min_n,
                                                                         cdir / "readiness_matrix.svg"), root)
        counted = rd.matrix.where(rd.counts >= min_n)
        readiness["insights"]["matrix"] = register("readiness.matrix", interpret.readiness_matrix(rd.matrix, rd.counts, min_n), {
            "area_means": counted.mean(axis=1).dropna().round(2).to_dict(),
            "spread_between_groups": (counted.max(axis=1) - counted.min(axis=1)).dropna().round(2).to_dict()})
    if rd.weakest:
        readiness["charts"]["weakest"] = _rel(charts.score_distribution_chart(rd.weakest, cdir / "readiness_weakest.svg"), root)
        readiness["insights"]["weakest"] = register("readiness.weakest", interpret.weakest(rd.weakest), [
            {"statement": w["text"], "score": w["score"], "share_low": round(w["low"], 2), "share_high": round(w["high"], 2)}
            for w in rd.weakest[:6]])
    from .benchmark import compare as compare_benchmarks
    try:
        bm = compare_benchmarks(eng)
    except ValueError as exc:
        bm, benchmark_problem = None, str(exc)
    else:
        benchmark_problem = None
    if bm:
        arch = assessment.results.get("architecture")
        readiness["benchmark"] = {
            **bm, "chart": _rel(charts.benchmark_chart(bm["rows"], cdir / "benchmark.svg"), root),
            "insight": register("readiness.benchmark", interpret.benchmark(bm, arch.verdict if arch else None), {
                "segment": [bm["industry"], bm["organisation_size"]],
                "measures": [{k: r[k] for k in ("label", "shown", "score", "industry_mean", "industry_sd",
                                                "industry_typical", "position")} for r in bm["rows"]]})}
    readiness["differences"] = [{"sub_area": d["sub_area"], "high": f"{d['high'][0]} ({d['high'][1]})",
                                 "low": f"{d['low'][0]} ({d['low'][1]})", "spread": d["spread"], "effect": d["effect"],
                                 "significant": d["significant"]} for d in rd.differences[:8]]

    # ---------------------------------------------------------------- evidence appendix
    rows, seen = [], set()
    composite = {"capability.architecture": "Capability (architecture, overall)",
                 "capability.hosting": "Capability (hosting, overall)"}
    for name, values in sorted(ev.signals.items()):
        head = name.split(".")[0]
        if head in ("need", "capability", "fit", "requirement", "locality") and name.count(".") >= 1 or name == "locality":
            v = values[0]
            label = composite.get(name) or signal_label(name, ins)
            if not np.isnan(v) and label not in seen:      # an axis and its only sub-area can share a label
                seen.add(label)
                lo, hi = np.nanpercentile(values, [2.5, 97.5])
                rows.append({"signal": label, "group": head, "value": round(float(v), 2),
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
    arch_block = next((b for b in decisions if b["id"] == "architecture"), {})
    lead = (arch_block.get("insights", {}).get("leadtime") or {})
    lead_split = next((e["data"]["by_group"] for e in exhibits if e["insight"]["id"] == "architecture.leadtime"), None)
    bm_rows = (readiness.get("benchmark") or {}).get("rows", [])
    speed = [r for r in bm_rows if r["metric"] in ("leadtime", "deployfreq") and r["score"] is not None]
    if lead and lead_split and speed and not any(r["position"] == "below" for r in speed):
        coord = lead_split["All respondents asked"].get("Coordination between teams", 0)
        cross = eng.facts.get("cross_team_change_pct")
        if coord >= 0.5:
            key.append("Pipeline speed is around or above the industry average"
                       + (" on measures still to be verified" if unverified else "")
                       + f"; the delay the business experiences lies in coordination between teams: {coord:.0%} of "
                         "the answers on lead time name it"
                       + (f", and {float(cross.point):g}% of changes need more than one team" if cross and
                          cross.point is not None else "") + ".")
    if not rd.matrix.empty:
        counted = rd.matrix.where(rd.counts >= min_n)
        area_scores = counted.mean(axis=1).dropna().sort_values()
        weak = [f"{name.split(': ', 1)[-1]} ({v:.1f})" for name, v in area_scores.head(2).items()]
        if weak:
            key.append(f"In the survey, the weakest areas of readiness are {' and '.join(weak)}.")
    strong_diff = [d for d in rd.differences if d["significant"] and d["effect"] == "large"]
    if strong_diff:
        d = strong_diff[0]
        from .integrity import GROUP_NAMES as _names
        key.append(f"Groups see \u201c{d['sub_area'].split(': ', 1)[-1]}\u201d very differently: the most positive "
                   f"group, {_names.get(d['high'][0], d['high'][0])}, rates it {d['high'][1]:.1f}, the most negative, "
                   f"{_names.get(d['low'][0], d['low'][0])}, {d['low'][1]:.1f}.")
    if st and st.findings:
        key.append(f"{len(st.findings)} findings on stakeholder perspectives should inform how the decision is communicated.")

    # ---------------------------------------------------------------- roadmap, success measures, scenarios
    from . import plan
    steps = next_steps(assessment)
    for i, s in enumerate(steps, 1):
        s["no"] = i                                     # one numbering across phases, for cross-references
    people = {k: v for k, v in (eng.config.get("people") or {}).items() if v}
    for s in steps:                                     # "Technology lead (CTO)" where the engagement names the role
        role = s["owner"].lower().split(" with ")[0].replace(" ", "_")
        if people.get(role) and people[role].lower() != s["owner"].lower():
            s["owner"] = f"{s['owner']} ({people[role]})"
    for issue in issues:                                # perspectives a decision depends on but did not count
        if issue.id.startswith("critical_groups."):
            d_id = issue.id.split(".", 1)[1]
            names = issue.groups[0] if len(issue.groups) == 1 else ", ".join(issue.groups[:-1]) + " and " + issue.groups[-1]
            sponsor = people.get("sponsor")
            steps.append({"phase": "people", "phase_label": "People and alignment", "decision": d_id,
                          "action": f"Hear {names} directly before committing to the {d_id} path: their answers were "
                                    "too few to count separately.",
                          "owner": f"Sponsor ({sponsor})" if sponsor and sponsor != "Sponsor" else "Sponsor",
                          "reason": "", "no": len(steps) + 1})
    for issue in issues:                                # a step that rests on a contradicted input is rewritten
        if issue.step_rewrite:
            for s in steps:
                if s["action"].startswith(issue.step_rewrite["starts_with"]):
                    s["action"] = issue.step_rewrite["action"]
    rm = plan.roadmap(assessment, steps)
    roadmap_block = {"gates": rm["gates"],
                     "chart": _rel(charts.roadmap_chart(rm, cdir / "roadmap.svg"), root) if rm["bars"] else None,
                     "insight": register("plan.roadmap", interpret.roadmap(rm), rm) if rm["bars"] else None}
    success = plan.measures(assessment)
    for block in decisions:
        if block["id"] == "hosting":
            block["scenarios"] = plan.scenarios(assessment)

    # ---------------------------------------------------------------- options, risks, basis of preparation
    from .appraisal import appraise
    from .risks import register as risk_register
    for block in decisions:
        block["options"] = appraise(assessment, block["id"])
    calendar_rows = next((b.get("calendar", []) for b in decisions if b["id"] == "hosting"), [])
    reopen = plan.triggers(assessment, {b["id"]: b["options"] for b in decisions}, success, calendar_rows)
    roadmap_block["load"] = plan.load(steps)
    from .investment import budget as phase_budget
    show_amounts = (eng.config.get("report") or {}).get("show_amounts", True)
    programme_budget = phase_budget(assessment, show_amounts)
    for block in decisions:
        if block["id"] == "architecture" and programme_budget and programme_budget.get("architecture"):
            block["investment"] = {**programme_budget["architecture"], "show_amounts": show_amounts,
                                   "estimators": sorted({e for k in ("arch_effort_person_months", "arch_external_cost",
                                                                     "arch_duration_months")
                                                         for e in (eng.facts[k].estimators if k in eng.facts else [])})}
    reg = risk_register(assessment)
    invited = eng.config.get("invited") or {}
    participation = [{"group": g, "n": int(n), "invited": invited.get(g),
                      "rate": (round(n / invited[g], 2) if invited.get(g) else None)} for g, n in sizes.items()]
    import yaml as _yaml
    glossary_path = ins.root / "glossary.yaml"
    glossary = [{"term": k, "definition": v} for k, v in (_yaml.safe_load(glossary_path.read_text()) or {}).items()] \
        if glossary_path.exists() else []
    report_cfg = eng.config.get("report", {}) or {}
    org = report_cfg.get("organisation") or eng.system
    prepared_by = report_cfg.get("prepared_by") or "the assessment team"
    notice = report_cfg.get("notice") or [
        f"This report was prepared by {prepared_by} for {report_cfg.get('prepared_for') or 'the management of ' + org} "
        f"to support decisions about the future of {eng.system}. It should not be relied upon by any other party or "
        "for any other purpose.",
        "The findings are based on a survey of the stakeholder groups listed in the appendix and on a fact sheet "
        "completed and attested by named owners within the organisation. Survey answers reflect respondents' "
        "perceptions. Facts were taken as provided and were not audited; checks of the fact sheet's independence "
        "and completeness are reported in the appendix.",
        "The recommendations follow decision rules agreed before results were seen. They indicate the path the "
        "evidence supports and the conditions attached to it; they are not a guarantee of outcomes. Cost figures are "
        "estimates with stated ranges and should be confirmed before budgets are committed.",
    ]
    if eng.config.get("report", {}).get("sample_data"):
        notice.append("This report was produced from synthetic data for illustration only.")

    rules = ins.rules
    ctx = {
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
        "exhibits": exhibits,
        "steps": steps,
        "roadmap": roadmap_block,
        "measures": success,
        "triggers": reopen,
        "sourcing": sourcing,
        "budget": programme_budget,
        "evidence": rows,
        "participation": participation,
        "risks": reg,
        "notice": notice,
        "glossary": glossary + [{"term": "Stakeholder groups", "definition": "; ".join(
            f"{g} — {GROUP_NAMES.get(g, g)}" for g in sizes) + "."}],
        "group_names": {g: GROUP_NAMES.get(g, "") for g in sizes},
        "evidence_strength": _evidence_strength(assessment),
        "evidence_note": _evidence_note(assessment),
        "problems": [_readable_problem(p, ins) for p in assessment.problems]
                    + ([benchmark_problem] if benchmark_problem else []) + ([bm["warning"]] if bm and bm.get("warning") else []),
        "fact_checks": [{"severity": f.severity, "message": f.message} for f in assessment.fact_checks],
        "rules": {"version": rules.get("version"), "signed_off_by": rules.get("signed_off_by"),
                  "confidence": rules.get("evidence", {}).get("confidence", 0.8),
                  "draws": ev.draws, "min_role_n": rules.get("evidence", {}).get("min_role_n", 5)},
        "text": None if assessment.text is None else _text_context(assessment.text),
    }
    _apply_integrity(ctx, issues)
    from .storyline import compose
    compose(assessment, ctx)
    from .brief import build as build_brief
    ctx["brief"] = build_brief(assessment, ctx)
    return ctx


def _apply_integrity(ctx: dict, issues) -> None:
    """Put every caveat beside what it qualifies; blocks make the report a draft."""
    caveats = [i for i in issues if i.severity == "caveat"]
    blocks = [i for i in issues if i.severity == "block"]
    ctx["integrity"] = {"draft": bool(blocks), "issues": [i.as_dict() for i in issues],
                        "blocks": [i.as_dict() for i in blocks], "caveats": [i.as_dict() for i in caveats]}
    ctx["engagement"]["draft"] = bool(blocks)

    def short(i):
        return {"title": i.title, "message": i.message}

    for dec in ctx["decisions"]:
        dec["caveats"] = [short(i) for i in caveats if dec["id"] in i.decisions]
    for e in ctx["exhibits"]:
        e["insight"]["caveats"] = [short(i) for i in caveats if e["insight"]["id"] in i.exhibits]
    affected = {f: i.title for i in caveats for f in i.facts}
    for m in ctx["measures"]:
        if m.get("fact") in affected:
            m["basis"] = f"provisional — {affected[m['fact']].lower()}"
    if ctx.get("text"):
        ctx["text"]["key_message_caveats"] = [[i.message for i in caveats if n in i.key_messages]
                                              for n in range(len(ctx["text"]["key_messages"]))]
        for n, th in enumerate(ctx["text"]["themes"]):
            th["caveats"] = [i.message for i in caveats if n in i.themes]


class NotFinal(Exception):
    """Raised by build_report(final=True) while a blocking integrity issue remains."""


def build_report(assessment, output: Path, template: Path = TEMPLATE, narrative: bool = False,
                 final: bool = False) -> Path:
    import typst
    root = Path(__file__).resolve().parents[1]
    out = root / "Output" / "build-v3" / output.stem
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    context = build_context(assessment, out, root)
    if final and context["integrity"]["draft"]:
        raise NotFinal("; ".join(b["message"] for b in context["integrity"]["blocks"]))
    reviewed = (assessment.engagement.config.get("report") or {}).get("reviewed_by")
    context["review"] = {"by": reviewed, "on": str((assessment.engagement.config.get("report") or {}).get("reviewed_on") or "")}
    context["narrative"] = None
    if narrative:
        from .narrative import write as write_narrative
        n = write_narrative(context, assessment.engagement)
        assessment.narrative = n
        if not n.rejected:
            context["narrative"] = {"executive": n.executive, "chapters": n.chapters}
        from .storyline import check, polish_ok, replace_means
        for e in context["exhibits"]:                  # only the "means" sentence is polished; links stay computed
            sentence = n.exhibits.get(e["insight"]["id"])
            if sentence and polish_ok(e["insight"]["so_what"], sentence):
                e["insight"]["so_what"] = replace_means(e["insight"]["so_what"], sentence)
        context["so_what_issues"] = check(context)
    from .rubric import failures, run as run_rubric
    context["rubric"] = run_rubric(context)
    if final:
        problems = failures(context["rubric"]) + ([] if reviewed else ["no quality review recorded (report.reviewed_by)"])
        if problems:
            raise NotFinal("; ".join(problems))
    data = out / "report.json"
    data.write_text(json.dumps(context, indent=1, ensure_ascii=False, default=str))
    output.parent.mkdir(parents=True, exist_ok=True)
    fonts = [str(p) for p in [template / "fonts"] if p.exists()]
    typst.compile(str(template / "decision.typ"), output=str(output), root=str(root), font_paths=fonts,
                  sys_inputs={"data": _rel(data, root)})
    return output


def _text_context(text) -> dict:
    quotes = {q["id"]: q for q in text.quotes}
    themes = [{"theme": th["theme"], "finding": th["finding"],
               "quotes": [{"role": quotes[i]["role"], "text": quotes[i]["text"]} for i in th.get("quote_ids", []) if i in quotes][:2]}
              for th in text.synthesis.get("themes", [])]
    models = {}
    for role, row in text.by_role.iterrows():
        shares = {c.replace("model_", ""): float(row[c]) for c in text.by_role.columns if c.startswith("model_")}
        if shares:
            models[role] = shares
    return {"model": text.model, "answers": int(len(text.coded)), "key_messages": text.synthesis.get("key_messages", []),
            "themes": themes, "mental_models": models}
