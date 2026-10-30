"""Roadmap with review points, success measures, and cost scenarios with break-even values.

- roadmap: the next steps placed in phases — now (0–3 months), next (3–6), later (6–12+) — with review points at the
  end of each phase; for hosting moves the cut-over window from the fact sheet (likely and high duration).
  Indicative sequencing, never earlier than the open preconditions allow.
- measures: per decision, the outcome's success measures with today's value as baseline; targets agreed in
  engagement.yaml (targets:) take precedence, otherwise the next performance band is proposed.
- scenarios: conservative / base / favourable five-year cost per hosting option relative to today, and for each
  rejected option the break-even value of the input that could make it pass the cost test.
"""

from __future__ import annotations

import numpy as np

from .explain import outcome_label, signal_label, with_unit
from .tco import compute

PHASES = [("now", "Now", 0, 3), ("next", "Next", 3, 6), ("later", "Later", 6, 12)]
PHASE_OF = {"before_commitment": "now", "evidence": "now", "people": "now", "capability": "now", "first_steps": "next"}
MOVES = {"move_to_cloud": "cloud", "hybrid": "hybrid", "repatriate": "repatriate"}
WORDS = {"stay": "Keep as is", "improve_current": "Improve / right-size", "cloud": "Move to cloud", "hybrid": "Hybrid",
         "repatriate": "Move back from cloud"}


# ---------------------------------------------------------------------------------------- roadmap

def roadmap(assessment, steps: list[dict]) -> dict:
    eng = assessment.engagement
    ins = eng.instrument
    bars, gates = [], []
    prepare = any(r.status == "prepare_first" for r in assessment.results.values())
    for s in steps:
        phase = PHASE_OF.get(s["phase"], "next")
        if s["phase"] == "first_steps" and not prepare:
            phase = "now"
        start, end = next((a, b) for k, _, a, b in PHASES if k == phase)
        bars.append({"workstream": s["phase_label"], "label": s["action"], "start": start, "end": end, "end_high": None,
                     "decision": s["decision"]})
    horizon = 12
    hosting = assessment.results.get("hosting")
    if hosting and hosting.verdict in MOVES:
        fact = eng.facts.get("migration_months")
        if fact and fact.point is not None:
            start = 3 if hosting.status == "prepare_first" else 0
            likely = float(fact.likely if fact.is_range else fact.value)
            high = float(fact.high) if fact.is_range else None
            bars.append({"workstream": "Hosting migration", "label": f"Migration and cut-over: "
                         f"{outcome_label(ins, 'hosting', hosting.verdict).lower()}", "start": start,
                         "end": start + likely, "end_high": (start + high) if high else None, "decision": "hosting"})
            horizon = max(horizon, int(np.ceil(start + (high or likely))))
    gates = [{"month": 3, "label": "Review: preconditions in place, stop criteria agreed — commit, re-scope or stop"},
             {"month": 6, "label": "Review: success measures against baseline"},
             {"month": 12, "label": "Review: success measures; continue, adjust or stop"}]
    return {"bars": bars, "gates": gates, "horizon": horizon}


# ---------------------------------------------------------------------------------------- success measures

def _proposed_target(fid: str, value: float, ins) -> tuple[str, float | None]:
    f = ins.facts.loc[fid]
    if not f["cuts"] or f["direction"] == "none":
        return "to be agreed", None
    cuts = [float(c) for c in f["cuts"].split("|")]
    # "up" means a higher value raises the axis; on need-type axes that is the problem, elsewhere the strength
    if f["axis"] in ("need", "distribution", "locality"):
        lower_is_better = f["direction"] == "up"
    else:
        lower_is_better = f["direction"] == "down"
    if lower_is_better:
        below = [c for c in cuts if c < value]
        if not below:
            return "maintain", value
        return "below", max(below)
    above = [c for c in cuts if c > value]
    if not above:
        return "maintain", value
    return "at least", min(above)


def measures(assessment) -> list[dict]:
    eng = assessment.engagement
    ins = eng.instrument
    agreed = eng.config.get("targets") or {}
    out = []
    for d, r in assessment.results.items():
        target_outcome = r.verdict if r.verdict != "insufficient_evidence" else r.leaning
        if not target_outcome:
            continue
        for fid in ins.outcomes[d][target_outcome].get("measures", []):
            fact = eng.facts.get(fid)
            if fact is None or fact.point is None or fid not in ins.facts.index:
                out.append({"decision": d.title(), "measure": ins.facts.at[fid, "label"] if fid in ins.facts.index else fid,
                            "baseline": "not measured", "target": "measure first", "basis": "missing baseline"})
                continue
            value = float(fact.point)
            if fid in agreed:
                target, basis = with_unit(f"fact.{fid}", float(agreed[fid]), ins), "agreed"
            else:
                word, cut = _proposed_target(fid, value, ins)
                target = word if cut is None or word == "maintain" else f"{word} {with_unit(f'fact.{fid}', cut, ins)}"
                if word == "maintain":
                    target = f"maintain ({with_unit(f'fact.{fid}', value, ins)})"
                basis = "proposed: next performance band"
            out.append({"decision": d.title(), "measure": ins.facts.at[fid, "label"],
                        "baseline": with_unit(f"fact.{fid}", value, ins), "target": target, "basis": basis})
    return out


# ---------------------------------------------------------------------------------------- scenarios

def _ratio(values: dict, current: str, option: str, vs: str = "stay") -> float:
    signals, problems = compute({k: np.array([float(v)]) for k, v in values.items()}, current)
    if problems or f"tco.{option}" not in signals:
        return float("nan")
    return float(signals[f"tco.{option}"][0] / signals[f"tco.{vs}"][0])


def scenarios(assessment) -> dict:
    eng, ev = assessment.engagement, assessment.evidence
    ins = eng.instrument
    hosting = assessment.results.get("hosting")
    if not hosting or not ev.fact_point or "tco.stay" not in ev.signals:
        return {}
    current = eng.config.get("current_hosting", "own_infrastructure")
    options = [k.split(".", 1)[1] for k in ev.signals if k.startswith("tco.") and k != "tco.stay"]
    ranged = {k: v for k, v in ev.fact_ranges.items() if ins.facts.at[k, "decision"] == "hosting"}
    base = dict(ev.fact_point)
    rows, breakeven = [], []
    verdict_option = MOVES.get(hosting.verdict, "improve_current" if hosting.verdict == "improve_current" else "stay")
    for opt in options:
        worst, best = dict(base), dict(base)
        swings = []
        for k, (lo, hi) in ranged.items():
            r_lo, r_hi = _ratio({**base, k: lo}, current, opt), _ratio({**base, k: hi}, current, opt)
            worst[k], best[k] = (hi, lo) if r_hi >= r_lo else (lo, hi)
            swings.append((abs(r_hi - r_lo), k, lo, hi))
        row = {"option": WORDS.get(opt, opt), "conservative": round(_ratio(worst, current, opt), 2),
               "base": round(_ratio(base, current, opt), 2), "favourable": round(_ratio(best, current, opt), 2)}
        rows.append(row)
        if opt != verdict_option and opt != "improve_current" and swings:
            # the strongest driver that alone could make the option pass; otherwise say none could
            found = None
            for _, key, lo, hi in sorted(swings, reverse=True)[:5]:
                found = _break_even(opt, key, lo, hi, base, current, ins)
                if found["value"] is not None:
                    break
            if found["value"] is None:
                found["sentence"] = (f"{WORDS.get(opt, opt)}: none of its five largest cost drivers alone, at any realistic "
                                     "value, would make it pass the cost test.")
            breakeven.append(found)
    return {"rows": sorted(rows, key=lambda r: r["base"]), "breakeven": breakeven}


def _break_even(opt: str, key: str, lo: float, hi: float, base: dict, current: str, ins) -> dict:
    """Value of `key` at which `opt` would pass the cost-motivated test (at most 1 − switching margin of an improved
    current setup), all other inputs at their likely values."""
    limit = 1 - ins.rules["decisions"]["hosting"].get("switching_margin", 0.15)

    def f(x):
        return _ratio({**base, key: x}, current, opt, vs="improve_current") - limit
    a, b = max(0.0, lo / 4), hi * 4
    fa, fb = f(a), f(b)
    label = signal_label(f"fact.{key}", ins).split(",")[0]
    if np.isnan(fa) or np.isnan(fb) or fa * fb > 0:
        return {"option": WORDS.get(opt, opt), "input": label, "value": None,
                "sentence": f"{WORDS.get(opt, opt)}: no realistic value of {label.lower()} alone would make it pass the "
                            "cost test."}
    for _ in range(60):
        m = (a + b) / 2
        if f(a) * f(m) <= 0:
            b = m
        else:
            a = m
    value = float(f"{(a + b) / 2:.3g}")              # three significant figures; it is an estimate
    likely = base[key]
    unit = ins.facts.at[key, "unit"]
    shown = f"{value:,.0f}" + (f" {unit}" if unit not in ("EUR",) else " €") if abs(value) >= 10 else f"{value:.1f} {unit}"
    now = f"{likely:,.0f}" + (f" {unit}" if unit not in ("EUR",) else " €") if abs(likely) >= 10 else f"{likely:.1f} {unit}"
    return {"option": WORDS.get(opt, opt), "input": label, "value": value,
            "sentence": f"{WORDS.get(opt, opt)} would be cheap enough to justify a move only if {label.lower()} were "
                        f"{'below' if value < likely else 'above'} {shown} (estimate: {now})."}
