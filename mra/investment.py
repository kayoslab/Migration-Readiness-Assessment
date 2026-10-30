"""What the recommended paths cost to carry out, and when the money and people are needed.

- architecture: effort (person-months, at the fully loaded salary) plus external cost, over the stated duration;
  sampled like every other estimate (two estimators' union, minimum width by grade, the organisation's past overrun
  as reference class), so the investment carries a range.
- hosting: the one-off cost of the recommended hosting path (automation for improving; migration, training and
  dual running for a move) and the hardware refresh where it falls.
- budget by phase: both decisions in one table — months 0–3, 3–6, 6–12, after 12 — in euros and average FTE.

None of this feeds the decision rules: the verdict does not depend on it; the approval does.
"""

from __future__ import annotations

import numpy as np

PHASES = [("0–3", 0, 3), ("3–6", 3, 6), ("6–12", 6, 12), ("after 12", 12, 60)]
STRUCTURAL = ("modular_monolith", "broad_decomposition", "targeted_extraction", "realign_services", "consolidate")
INPUTS = ("arch_effort_person_months", "arch_external_cost", "arch_duration_months")


def _eur(x: float) -> str:
    return f"€{x / 1e6:.2f}M" if abs(x) >= 1e6 else f"€{x / 1e3:,.0f}k"


def _spread(total: np.ndarray, start: np.ndarray, months: np.ndarray, a: float, b: float) -> np.ndarray:
    """Share of an evenly spread amount that falls between months a and b."""
    end = start + np.maximum(months, 1e-9)
    overlap = np.clip(np.minimum(end, b) - np.maximum(start, a), 0, None)
    return total * overlap / np.maximum(months, 1e-9)


def architecture(assessment) -> dict | None:
    eng, ev = assessment.engagement, assessment.evidence
    r = assessment.results.get("architecture")
    if not r or r.verdict not in STRUCTURAL:
        return None
    missing = [k for k in INPUTS if f"fact.{k}" not in ev.signals or np.isnan(ev.signals[f"fact.{k}"]).all()]
    if missing or "fact.fte_cost_annual" not in ev.signals:
        labels = [eng.instrument.facts.at[k, "label"].split(" (")[0] for k in missing]
        return {"estimated": False, "missing": labels}
    effort = ev.signals["fact.arch_effort_person_months"]
    external = np.nan_to_num(ev.signals["fact.arch_external_cost"])
    months = ev.signals["fact.arch_duration_months"]
    cost = effort * ev.signals["fact.fte_cost_annual"] / 12 + external
    start = 3.0 if r.status == "prepare_first" else 0.0
    overrun = eng.facts.get("past_programme_overrun_pct")
    return {
        "estimated": True, "start": start,
        "cost": float(cost[0]), "cost_low": float(np.nanpercentile(cost, 5)), "cost_high": float(np.nanpercentile(cost, 95)),
        "effort": float(effort[0]), "months": float(months[0]),
        "months_high": float(np.nanpercentile(months, 95)), "fte": float(effort[0] / max(months[0], 1e-9)),
        "reference_class": (float(overrun.point) if overrun is not None and overrun.point is not None else None),
        "draws": {"cost": cost, "effort": effort, "months": months},
    }


def hosting_one_off(assessment) -> dict | None:
    eng = assessment.engagement
    r = assessment.results.get("hosting")
    if not r:
        return None
    f = {k: (eng.facts[k].point if k in eng.facts and eng.facts[k].point is not None else 0.0)
         for k in ("automation_investment", "migration_cost", "training_hiring_cost", "migration_months",
                   "hw_refresh_capex", "hw_refresh_due_months", "rightsized_share_pct", "need_share_pct")}
    out = {"items": []}
    if r.verdict == "improve_current":
        out["items"].append({"label": "Automation (one-off)", "amount": f["automation_investment"], "start": 0, "months": 0})
        capacity = f["rightsized_share_pct"] / 100 if f["rightsized_share_pct"] else 1.0
    elif r.verdict in ("move_to_cloud", "hybrid", "repatriate"):
        share = f["need_share_pct"] / 100 if r.verdict == "hybrid" and f["need_share_pct"] else 1.0
        out["items"].append({"label": "Migration", "amount": f["migration_cost"] * share, "start": 0,
                             "months": f["migration_months"] or 12})
        out["items"].append({"label": "Training and hiring", "amount": f["training_hiring_cost"], "start": 0, "months": 0})
        capacity = 1 - share if r.verdict == "hybrid" else (0.0 if f["hw_refresh_due_months"] > (f["migration_months"] or 0) else 1.0)
    else:
        capacity = 1.0
    owns_hardware = eng.config.get("current_hosting", "own_infrastructure") != "cloud" or r.verdict == "repatriate"
    if f["hw_refresh_capex"] and capacity and owns_hardware:
        out["items"].append({"label": "Hardware refresh", "amount": f["hw_refresh_capex"] * capacity,
                             "start": f["hw_refresh_due_months"], "months": 0})
    return out


def budget(assessment, show_amounts: bool = True) -> dict | None:
    """Both decisions by phase; amounts at the likely values, the architecture total with its range."""
    arch = architecture(assessment)
    host = hosting_one_off(assessment)
    rows = []
    if arch and arch["estimated"]:
        d = arch["draws"]
        start = np.full_like(d["months"], arch["start"])
        cells = [_spread(d["cost"], start, d["months"], a, b) for _, a, b in PHASES]
        rows.append({"item": "Architecture: first steps on the recommended path",
                     "cells": [float(c[0]) for c in cells], "total": arch["cost"],
                     "range": f"{_eur(arch['cost_low'])}–{_eur(arch['cost_high'])}"})
    if host:
        for item in host["items"]:
            amount = np.array([float(item["amount"])])
            start, months = np.array([float(item["start"])]), np.array([float(item["months"])])
            if item["months"]:
                cells = [float(_spread(amount, start, months, a, b)[0]) for _, a, b in PHASES]
            else:                                          # a one-off amount in the month it falls
                cells = [float(amount[0]) if a <= item["start"] < b or (a == 0 and item["start"] == 0) else 0.0
                         for _, a, b in PHASES]
            rows.append({"item": f"Hosting: {item['label'].lower()}", "cells": cells, "total": float(amount[0]),
                         "range": None})
    for part in getattr(assessment, "sourcing", []) or []:     # replacing a part: integration over the switch
        if part["verdict"] != "replace_with_product" or part.get("integration_cost") is None:
            continue
        start = 6.0 if part["status"] == "prepare_first" else 3.0   # after the proof of concept (and the separation)
        amount, months = np.array([part["integration_cost"]]), np.array([max(part["switch_months"], 1.0)])
        cells = [float(_spread(amount, np.array([start]), months, a, b)[0]) for _, a, b in PHASES]
        rows.append({"item": f"Build or buy: replacing {part['name'].lower()}", "cells": cells,
                     "total": float(amount[0]), "range": None})
    if not rows:
        return None
    totals = [sum(r["cells"][i] for r in rows) for i in range(len(PHASES))]
    fmt = (lambda x: _eur(x) if x >= 500 else "–") if show_amounts else (lambda x: "" if x < 500 else "●")
    return {"phases": [p for p, _, _ in PHASES], "show_amounts": show_amounts,
            "rows": [{**r, "cells_text": [fmt(c) for c in r["cells"]], "total_text": fmt(r["total"])} for r in rows],
            "totals_text": [fmt(t) for t in totals], "total_text": fmt(sum(totals)),
            "architecture": None if not arch else {k: v for k, v in arch.items() if k != "draws"}}
