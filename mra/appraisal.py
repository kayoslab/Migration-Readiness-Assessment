"""Options appraisal: every path side by side, and what one would need to believe for each to win.

For each option that applies to the current state: how often it applies across the draws, why it does or does not
apply at the point estimate, its cost relative to today (hosting), its open capability gaps and preconditions, and
the stated judgements (programme size, reversibility, time to value) from outcomes.yaml. For every option other than
the verdict, the conditions that would have to hold for it to apply — "what you would need to believe" — in plain
language, with the current values.
"""

from __future__ import annotations

from .decision import Context, _check_outcome, _compare, _failing_leaves, _threshold, evaluate
from .explain import OPS, fmt, outcome_label, signal_label, with_unit

TCO_OPTION = {"stay_as_is": "stay", "improve_current": "improve_current", "hybrid": "hybrid", "move_to_cloud": "cloud",
              "repatriate": "repatriate"}


def _shown(signal: str, value, ins) -> str:
    if "share_of" in ins.rules.get("signals", {}).get(signal, {}) and isinstance(value, (int, float)):
        return f"{value:.0%}"                                 # survey shares are fractions; print them as percentages
    if signal.startswith("payback") and isinstance(value, (int, float)):
        return "never" if value == float("inf") else f"{value:.0f} months"
    if signal.startswith("tco_saving_fte") and isinstance(value, (int, float)):
        return f"{value:.1f} FTE"
    return with_unit(signal, value, ins)


def _routes(cond, ctx: Context) -> list[list[dict]]:
    """Every way a failed condition could still come to hold: one route per branch of a top-level `any`."""
    if isinstance(cond, dict) and "any" in cond and evaluate(cond, ctx) is False:
        return [r for c in cond["any"] if (r := _failing_leaves(c, ctx))]
    leaves = _failing_leaves(cond, ctx)
    return [leaves] if leaves else []


def _belief(cond: dict, ctx: Context, ins) -> str | None:
    if "signal" not in cond or cond["signal"] == "<unresolved>":
        return None
    value = ctx.get(cond["signal"])
    threshold = _threshold(cond, ctx)
    label = signal_label(cond["signal"], ins)
    if "ref" in cond:
        ref = signal_label(cond["ref"], ins).split(" — ")[0].split(" (")[0].lower()
        target = f"{OPS.get(cond['op'], cond['op'])} the {ref} ({_shown(cond['ref'], threshold, ins)})"
    elif isinstance(threshold, bool):
        target = "true" if threshold else "false"
    else:
        target = f"{OPS.get(cond['op'], cond['op'])} {_shown(cond['signal'], threshold, ins)}".strip()
    current = "unknown" if value is None else _shown(cond["signal"], value, ins)
    return f"{label} would have to be {target} (currently {current})."


def _cap_beliefs(spec: dict, ctx: Context, ins) -> list[str]:
    out = []
    for c in spec.get("requires_capability", []):
        if evaluate(c, ctx) is False:
            for leaf in _failing_leaves(c, ctx):
                if (b := _belief(leaf, ctx, ins)):
                    out.append(b)
    return out


def appraise(assessment, decision: str) -> list[dict]:
    eng, ev = assessment.engagement, assessment.evidence
    ins, rules = eng.instrument, eng.instrument.rules
    result = assessment.results[decision]
    ctx = Context(ev.at(0), rules, ev.current_state, decision)
    outcomes = rules["decisions"][decision]["outcomes"]
    current = ev.current_state[decision]
    stay_tco = ctx.get("tco.stay")
    rows, earlier_applies = [], None
    for spec in outcomes:
        oid = spec["id"]
        allowed = spec.get("only_if_current")
        if allowed and current not in (allowed if isinstance(allowed, list) else [allowed]):
            continue
        applies, status, stops, unmet = _check_outcome(spec, ctx, rules)
        meta = ins.outcomes[decision][oid].get("appraisal", {})
        if applies is None:
            state, beliefs = "not decidable", ["Required inputs are missing; see where the evidence is uncertain."]
        elif status == "excluded":
            state = "excluded"
            beliefs = [f"Not possible: {rules['hard_stops'][stops[0]]['label'].lower()}."]
        elif not applies:
            state = "capability gap too large" if status == "fallthrough" else "conditions not met"
            beliefs = []
            for n, route in enumerate(_routes(spec.get("when"), ctx)):
                lines = [b for leaf in route if (b := _belief(leaf, ctx, ins))]
                if n and lines:                                # a second way in: say so, and keep it together
                    lines = ["Or" + (", all of: " if len(lines) > 1 else ": ") + "; ".join(
                        x[0].lower() + x[1:].rstrip(".") for x in lines) + "."]
                beliefs += lines
            beliefs += _cap_beliefs(spec, ctx, ins)          # what it would also take, not only the first hurdle
            beliefs += [f"Hard stop to remove: {rules['hard_stops'][h]['label'].lower()}." for h in spec.get("blocked_by", [])
                        if evaluate(rules["hard_stops"][h]["when"], ctx) is True]
        elif earlier_applies:
            state = "pre-empted"
            summary = " ".join(str(ins.outcomes[decision][oid].get("summary", "")).split())
            beliefs = [f"Its conditions are met, but “{outcome_label(ins, decision, earlier_applies)}” comes "
                       "first in the agreed rule order."] + ([f"What it would do instead: {summary}"] if summary else [])
        elif status == "prepare_first":
            state = "applies after preparation"
            beliefs = [f"Hard stop to remove: {rules['hard_stops'][h]['label'].lower()}." for h in stops] + \
                _cap_beliefs(spec, ctx, ins)
        else:
            state = "applies"
            beliefs = []
        if oid == result.verdict and result.status == "prepare_first":
            state = "applies after preparation"
        if applies and status in ("go", "prepare_first") and earlier_applies is None:
            earlier_applies = oid
        cost = None
        if decision == "hosting" and stay_tco and ctx.get(f"tco.{TCO_OPTION.get(oid, '')}") is not None:
            cost = round(ctx.get(f"tco.{TCO_OPTION[oid]}") / stay_tco, 2)
        rows.append({
            "id": oid, "label": outcome_label(ins, decision, oid), "is_verdict": oid == result.verdict,
            "probability": round(result.distribution.get(oid, 0.0), 2), "state": state,
            "cost_vs_today": cost, "gaps": len(unmet), "preconditions": len(spec.get("requires_gates", [])),
            "programme": meta.get("programme", "–"), "reversibility": meta.get("reversibility", "–"),
            "time_to_value": meta.get("time_to_value", "–"),
            "beliefs": [] if oid == result.verdict else beliefs[:6],
        })
    return rows
