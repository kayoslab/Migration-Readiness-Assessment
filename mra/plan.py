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

import re

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
    from .investment import architecture as arch_investment
    inv = arch_investment(assessment) or {}
    horizon = 12
    for s in steps:
        phase = PHASE_OF.get(s["phase"], "next")
        if s["phase"] == "first_steps" and not prepare:
            phase = "now"
        start, end = next((a, b) for k, _, a, b in PHASES if k == phase)
        end_high = None
        if s["phase"] == "first_steps" and s["decision"] == "architecture" and inv.get("estimated"):
            start = inv["start"]                         # the estimated duration, not a nominal phase
            end, end_high = start + inv["months"], start + inv["months_high"]
            horizon = max(horizon, int(np.ceil(end_high)))
        bars.append({"workstream": s["phase_label"], "label": s["action"], "start": start, "end": end,
                     "end_high": end_high, "decision": s["decision"]})
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
    gates = [{"month": 3, "label": "Preconditions in place, stop criteria agreed — commit, re-scope or stop"},
             {"month": 6, "label": "Success measures against baseline"},
             {"month": 12, "label": "Success measures; continue, adjust or stop"}]
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


def _rule_target(ins, decision: str, outcome: str, fid: str) -> tuple[str, float | None]:
    """The opposite of the condition on `fid` that made the outcome apply: the bar it should get past."""
    from .instrument import _conditions
    spec = next((o for o in ins.rules["decisions"][decision]["outcomes"] if o["id"] == outcome), {})
    flip = {">=": "below", ">": "at most", "<=": "above", "<": "at least"}
    for _, c in _conditions(spec.get("when"), ""):
        if c.get("signal") == f"fact.{fid}" and c.get("op") in flip and isinstance(c.get("value"), (int, float)):
            return flip[c["op"]], float(c["value"])
    return "to be agreed", None


def measures(assessment) -> list[dict]:
    eng = assessment.engagement
    ins = eng.instrument
    agreed = eng.config.get("targets") or {}
    out = []
    for d, r in assessment.results.items():
        target_outcome = r.verdict if r.verdict != "insufficient_evidence" else r.leaning
        if not target_outcome:
            continue
        listed = ins.outcomes[d][target_outcome].get("measures", [])
        if isinstance(listed, dict):                     # measures that depend on where the system runs today
            listed = listed.get(r.current_state, listed.get("default", []))
        for fid in listed:
            fact = eng.facts.get(fid)
            if fact is None or fact.point is None or fid not in ins.facts.index:
                out.append({"fact": fid, "decision": d.title(), "measure": ins.facts.at[fid, "label"] if fid in ins.facts.index else fid,
                            "baseline": "not measured", "target": "measure first", "basis": "missing baseline"})
                continue
            value = float(fact.point)
            if fid in agreed:
                target, basis = with_unit(f"fact.{fid}", float(agreed[fid]), ins), "agreed"
            else:
                word, cut = _proposed_target(fid, value, ins)
                basis = "proposed: next performance band"
                if cut is None:                          # no bands: the rule that chose the path sets the bar
                    word, cut = _rule_target(ins, d, target_outcome, fid)
                    basis = "proposed: past the threshold that chose the path" if cut is not None else "to be agreed"
                target = word if cut is None or word == "maintain" else f"{word} {with_unit(f'fact.{fid}', cut, ins)}"
                if word == "maintain":
                    target = f"maintain ({with_unit(f'fact.{fid}', value, ins)})"
            out.append({"fact": fid, "decision": d.title(), "measure": ins.facts.at[fid, "label"],
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
    label = signal_label(f"fact.{key}", ins).split(",")[0].split(" (")[0]
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
    def amount(x):
        if unit == "EUR":
            return _eur(x)
        return f"{x:,.0f} {unit}" if abs(x) >= 10 else f"{x:.1f} {unit}"
    shown, now = amount(value), amount(likely)
    return {"option": WORDS.get(opt, opt), "input": label, "value": value,
            "sentence": f"{WORDS.get(opt, opt)} would be cheap enough to justify a move only if {label.lower()} were "
                        f"{'below' if value < likely else 'above'} {shown} (estimate: {now})."}


# ---------------------------------------------------------------------------------------- decision calendar

def _eur(x: float) -> str:
    return f"€{x / 1e6:.2f}M" if abs(x) >= 1e6 else f"€{x / 1e3:,.0f}k"


def calendar(assessment, show_amounts: bool = True) -> list[dict]:
    """Dated hosting decisions: what to decide now, at the refresh, at contract end, and when a move would finish."""
    eng = assessment.engagement
    r = assessment.results.get("hosting")
    if not r:
        return []
    f = {k: (eng.facts[k].point if k in eng.facts and eng.facts[k].point is not None else None)
         for k in ("hw_refresh_due_months", "hw_refresh_capex", "rightsized_share_pct", "contract_end_months",
                   "migration_months")}
    out = []
    target = r.verdict if r.verdict != "insufficient_evidence" else r.leaning
    first = {"improve_current": "Start right-sizing and automating the current infrastructure.",
             "stay_as_is": "Keep the current setup; no hosting programme is started.",
             "move_to_cloud": "Prepare the move; the migration starts once preconditions are met.",
             "hybrid": "Prepare the partial move; the migration starts once preconditions are met.",
             "repatriate": "Prepare the move back; the migration starts once preconditions are met."}.get(target)
    if first:
        out.append({"month": 0, "event": "Decision", "action": first})
    current = eng.config.get("current_hosting", "own_infrastructure")
    if current == "cloud" and target != "repatriate":    # no hardware of its own: no refresh, no colocation contract
        end = eng.facts.get("cloud_commitment_end_months")
        end = end.point if end is not None else None
        if end:
            out.append({"month": max(end - 3, 1), "event": "Hosting review", "action":
                        f"Re-run the hosting assessment with measured costs before the cloud commitment ends (month "
                        f"{end:g}), to decide how much to commit again."})
            out.append({"month": end, "event": "Cloud commitment ends", "action": "Renew, resize or end it, as "
                        "decided at the review."})
        return sorted(out, key=lambda x: x["month"])
    due, capex, k = f["hw_refresh_due_months"], f["hw_refresh_capex"], f["rightsized_share_pct"]
    if due is not None and capex:
        amount = f" ({_eur(capex)})" if show_amounts else ""
        if target == "improve_current" and k:
            saving = f", about {_eur(capex * (1 - k / 100))} less" if show_amounts else ""
            action = (f"Order the refresh for the right-sized estate — {k:g}% of today's capacity{saving}. Confirm the "
                      "sizing at the checkpoint before the order.")
        elif target in ("move_to_cloud", "repatriate") and f["migration_months"]:
            action = ("The refresh falls before cut-over; a bridge (extended support or leased capacity) is needed."
                      if due <= f["migration_months"] else "The move completes before the refresh; it is not ordered.")
        else:
            action = "Order the refresh at today's capacity, or right-size first to reduce it."
        out.append({"month": due, "event": f"Hardware refresh due{amount}", "action": action})
    end = f["contract_end_months"]
    if end is not None:
        review = max(end - 6, 0)
        before_refresh = due is not None and capex and due <= review
        if before_refresh:                              # the refresh would otherwise pre-empt the review
            review = max(due - 3, 1)
        out.append({"month": review, "event": "Hosting review", "action":
                    ("Re-run the hosting assessment with measured costs before the refresh is ordered, so that the "
                     f"refresh does not decide the renewal of the contract ending in month {end:g}."
                     if before_refresh else
                     f"Re-run the hosting assessment six months before the contract ends (month {end:g}), with "
                     "measured costs, to decide whether to renew.")})
        out.append({"month": end, "event": "Colocation contract ends", "action": "Renew or exit, as decided at the review."})
    if target in ("move_to_cloud", "hybrid", "repatriate") and f["migration_months"]:
        out.append({"month": f["migration_months"], "event": "Planned cut-over", "action": "Last workload moved."})
    return sorted(out, key=lambda x: x["month"])


def inaction(assessment, show_amounts: bool = True) -> str | None:
    """What keeping today's setup unchanged costs and carries."""
    eng, ev = assessment.engagement, assessment.evidence
    if "tco.stay" not in ev.signals:
        return None
    pt = {k: (eng.facts[k].point if k in eng.facts else None)
          for k in ("hw_refresh_due_months", "hw_refresh_capex", "infra_bus_factor", "infra_toil_pct")}
    if eng.config.get("current_hosting", "own_infrastructure") == "cloud":   # these describe hardware it does not run
        pt = {k: None for k in pt}
    horizon = eng.instrument.rules["decisions"]["hosting"].get("horizon_years", 5)
    parts = []
    if show_amounts:
        parts.append(f"Keeping today's setup unchanged costs {_eur(float(ev.signals['tco.stay'][0]))} over {horizon} years "
                     "(present value)" + (f", including the {_eur(pt['hw_refresh_capex'])} hardware refresh in month "
                                          f"{pt['hw_refresh_due_months']:g}" if pt["hw_refresh_capex"] else "") + ".")
    risks = []
    if pt["infra_bus_factor"] is not None:
        risks.append(f"{pt['infra_bus_factor']:g} people can restore the platform after a hardware or network failure")
    if pt["infra_toil_pct"] is not None:
        risks.append(f"{pt['infra_toil_pct']:g}% of platform engineering hours go to hardware, data-centre and network "
                     "tasks")
    if risks:
        parts.append("It also keeps today's exposure: " + "; ".join(risks) + ".")
    return " ".join(parts) or None


# ---------------------------------------------------------------------------------------- reopen triggers

OWN_TEST = re.compile(r"would change my mind|would make sense|would be more open|would convince|proof of concept|"
                      r"show me|if we .{3,80} (?:still|and)", re.I)
DECISION_WORDS = {"architecture": ("split", "service", "monolith", "module", "boundar", "deploy"),
                  "hosting": ("cloud", "hardware", "infrastructure", "on-call", "data centre", "data center", "load")}


def _as_trigger(belief: str) -> str:
    text = belief.rstrip(".")
    text = text.replace(" would have to be ", " is ").replace("(currently ", "(today ")
    return text[0].lower() + text[1:]


def triggers(assessment, rows_by_decision: dict, measures_rows: list[dict], calendar_rows: list[dict]) -> list[dict]:
    """When to reopen each decision: the recommended path's own measure falling short, or the nearest alternative's
    conditions coming true — checked at a dated point, with respondents' own tests where they named one."""
    out = []
    quotes = [q for q in (assessment.text.quotes if assessment.text else []) if OWN_TEST.search(q["text"])]
    for d, r in assessment.results.items():
        if r.verdict == "insufficient_evidence":
            continue
        rows = [o for o in rows_by_decision.get(d, []) if not o["is_verdict"]
                and o["state"] in ("conditions not met", "capability gap too large") and o["beliefs"]]
        if not rows:
            continue
        # the next larger step reopens when the recommended path falls short; otherwise the most likely alternative
        size = {"none": 0, "small": 1, "medium": 2, "large": 3}
        verdict_row = next((o for o in rows_by_decision.get(d, []) if o["is_verdict"]), None)
        own = size.get(verdict_row["programme"], 1) if verdict_row else 1
        larger = sorted((o for o in rows if size.get(o["programme"], 0) > own), key=lambda o: size[o["programme"]])
        alt = larger[0] if larger else max(rows, key=lambda o: (o["probability"], -len(o["beliefs"])))
        when = "checkpoint C3 (month 12)"
        if d == "hosting":
            review = next((c for c in calendar_rows if c["event"] == "Hosting review"), None)
            if review:
                when = f"the hosting review (month {review['month']:g})"
        conditions = []
        measure = next((m for m in measures_rows if m["decision"] == d.title() and m["target"].startswith(("below", "at least"))), None)
        if measure:
            name = measure["measure"].split(" (")[0]
            word, _, value = measure["target"].partition(" ")
            still = f"is still at or above {value}" if word == "below" else f"is still below {value}"
            conditions.append(f"the measure “{name[0].lower() + name[1:]}” {still} (today {measure['baseline']}) once "
                              "the first steps are complete")
        conditions.append(_as_trigger(alt["beliefs"][0]))
        own = [{"role": q["role"], "text": q["text"]} for q in quotes
               if any(w in q["text"].lower() for w in DECISION_WORDS[d])][:2]
        out.append({"decision": d, "title": d.title(), "alternative": alt["label"], "when": when,
                    "conditions": conditions, "own_tests": own})
    labels = {k: v["label"] for k, v in assessment.engagement.instrument.outcomes.get("sourcing", {}).items()}
    rw = (assessment.engagement.instrument.rules.get("sourcing") or {}).get("replace_when", {})
    for part in getattr(assessment, "sourcing", []) or []:
        title = f"Build or buy — {part['name']}"
        if part["verdict"] == "keep_building" and part["status"] == "go" and part["beliefs"]:
            out.append({"decision": f"sourcing:{part['id']}", "title": title,
                        "alternative": labels.get("replace_with_product", "Replace it with a product"),
                        "when": "the next annual review", "conditions": [_as_trigger(b) for b in part["beliefs"][:2]],
                        "own_tests": []})
        elif part["verdict"] == "replace_with_product":
            out.append({"decision": f"sourcing:{part['id']}", "title": title,
                        "alternative": labels.get("keep_building", "Keep building it"),
                        "when": "the end of the proof of concept",
                        "conditions": [f"the product meets less than {rw.get('coverage_at_least', 80):g}% of the "
                                       "requirements as is",
                                       f"the confirmed cost of buying exceeds {rw.get('cost_ratio_at_most', 0.85):.2f} "
                                       "of building over five years"], "own_tests": []})
    return out


# ---------------------------------------------------------------------------------------- capacity

def load(steps: list[dict], threshold: int = 4) -> list[str]:
    """Owners carrying many actions in the same phase, across both decisions."""
    from collections import Counter, defaultdict
    phase_of = {**PHASE_OF, "first_steps": "next"}
    names = {"now": "the first three months", "next": "months 3 to 6"}
    counts = Counter((s["owner"], phase_of.get(s["phase"], "next")) for s in steps)
    heavy: dict[str, list[str]] = defaultdict(list)
    for (owner, phase), n in counts.items():
        if n >= threshold:
            heavy[owner].append(f"{n} in {names.get(phase, phase)}")
    notes = []
    for owner, parts in heavy.items():
        decisions = {s["decision"] for s in steps if s["owner"] == owner}
        both = " across both decisions" if {"architecture", "hosting"} <= decisions else ""
        parts[0] = parts[0].replace(" in ", " actions in ", 1)
        notes.append(f"{owner} owns {' and '.join(parts)}{both}: plan the capacity, or delegate some, "
                     "before committing.")
    return notes
