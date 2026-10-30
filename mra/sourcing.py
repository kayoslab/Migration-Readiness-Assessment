"""Build or buy: for each candidate part, keep building it or replace it with a product.

Pre-registered rules (decision_rules.yaml → sourcing): replace only if the part does not set the organisation apart
(survey SO01, rated by the business-facing groups), a product meets enough of its current requirements, and buying is
at least the switching margin cheaper over the horizon. Hard stops (no data export, compliance not met) rule replacing
out. A part whose data other parts also write must be separated first (prepare first). Keeping needs no
preconditions; replacing needs a sponsor, funding and an exit plan.

Uncertainty as in the main assessment: each draw resamples respondents within their group and every estimate within
its range (minimum width by source grade, two estimators' union); the verdict needs the confidence level.
"""

from __future__ import annotations

import numpy as np

from .axes import pert, widen
from .engagement import Fact

ECONOMIC = ("part_maintain_fte", "part_run_cost_annual", "product_licence_annual", "product_integration_cost",
            "product_remaining_fte", "product_switch_months", "product_exit_cost", "product_coverage_pct")
OUTCOMES = ("keep_building", "replace_with_product")


def _sample(fact: Fact | None, rng, draws: int, min_width: dict, unit: str) -> np.ndarray | None:
    if fact is None or fact.point is None:
        return None
    if not fact.is_range:
        if not isinstance(fact.value, (int, float)):
            return None
        fact = Fact(low=float(fact.value), likely=float(fact.value), high=float(fact.value), grade=fact.grade)
    low, likely, high = widen(fact, min_width)
    if unit == "%":
        low, high = max(low, 0.0), min(high, 100.0)
    values = pert(rng, low, likely, high, draws)
    values[0] = likely
    return values


def _differentiation(eng, name: str, spec: dict, rng, draws: int, min_n: int) -> np.ndarray | None:
    ans = eng.answers
    ans = ans[(ans["item_id"] == spec["item"]) & (ans["row"] == name) & ~ans["dont_know"].fillna(False).astype(bool)]
    ans = ans.dropna(subset=["score"])
    groups = {g: sub["score"].to_numpy(float) for g, sub in ans.groupby("role") if g in spec["groups"]}
    counted = {g: v for g, v in groups.items() if len(v) >= min_n}
    if not counted:                                       # too few per group: pool what there is, if enough
        pooled = np.concatenate(list(groups.values())) if groups else np.array([])
        counted = {"pooled": pooled} if len(pooled) >= min_n else {}
    if not counted:
        return None
    out = np.empty(draws)
    for b in range(draws):
        means = [(v if b == 0 else rng.choice(v, size=len(v), replace=True)).mean() for v in counted.values()]
        out[b] = np.mean(means)                          # every group counts equally
    return out


def _npv(monthly: np.ndarray, discount: np.ndarray) -> np.ndarray:
    return (monthly * discount).sum(axis=1)


def _costs(x: dict, fte: float, rate: float, months: int):
    """Monthly cost streams of building (today) and buying, per draw."""
    B = len(x["part_maintain_fte"])
    m = np.arange(1, months + 1)[None, :]
    discount = (1 + rate / 100) ** (-m / 12)
    build = ((x["part_maintain_fte"] * fte + x["part_run_cost_annual"]) / 12)[:, None] * np.ones((B, months))
    switch = np.clip(np.ceil(x["product_switch_months"]), 1, months)[:, None]
    after = ((x["product_licence_annual"] + x["product_remaining_fte"] * fte) / 12)[:, None]
    licence = (x["product_licence_annual"] / 12)[:, None]
    buy = np.where(m <= switch, build + licence, after)  # the part keeps running until the switch; licence from day one
    buy = buy + np.where(m == 1, x["product_integration_cost"][:, None], 0.0) + \
        np.where(m == months, x["product_exit_cost"][:, None], 0.0)
    ratio = _npv(buy, discount) / _npv(build, discount)
    ahead = np.cumsum(buy, axis=1) <= np.cumsum(build, axis=1)
    stays = np.flip(np.cumprod(np.flip(ahead, axis=1), axis=1), axis=1).astype(bool)
    payback = np.where(stays.any(axis=1), stays.argmax(axis=1) + 1, np.inf)
    return _npv(build, discount), _npv(buy, discount), ratio, payback


def evaluate(assessment, draws: int | None = None, seed: int = 42) -> list[dict]:
    eng = assessment.engagement
    if not eng.candidates:
        return []
    ins, rules = eng.instrument, eng.instrument.rules
    spec = rules.get("sourcing") or {}
    if not spec:
        return []
    ev_cfg = rules.get("evidence", {})
    draws = draws or assessment.evidence.draws
    confidence, min_n = ev_cfg.get("confidence", 0.8), ev_cfg.get("min_role_n", 5)
    min_width = (rules.get("fact_discipline") or {}).get("min_range_width_by_grade", {})
    horizon = spec.get("horizon_years", 5)
    fte = float(eng.facts["fte_cost_annual"].point) if "fte_cost_annual" in eng.facts else None
    rate = float(eng.facts["discount_rate_pct"].point) if "discount_rate_pct" in eng.facts else 6.0
    rng = np.random.default_rng(seed + 7)
    out = []
    for cid, name in eng.candidates.items():
        facts = eng.sourcing_facts.get(cid, {})
        x = {k: _sample(facts.get(k), rng, draws, min_width, ins.facts.at[k, "unit"]) for k in ECONOMIC}
        x["product_exit_cost"] = x["product_exit_cost"] if x["product_exit_cost"] is not None else np.zeros(draws)
        diff = _differentiation(eng, name, spec["differentiation"], rng, draws, min_n)
        missing = [ins.facts.at[k, "label"] for k, v in x.items() if v is None]
        if diff is None:
            missing.append("enough ratings of how much the part sets the organisation apart")
        if fte is None:
            missing.append(ins.facts.at["fte_cost_annual", "label"])
        row = {"id": cid, "name": name, "missing": missing}
        if missing:
            out.append({**row, "verdict": "insufficient_evidence", "status": "insufficient", "probability": 0.0,
                        "why": [], "beliefs": [], "hard_stops": [], "gates": [], "seam": None})
            continue
        build, buy, ratio, payback = _costs(x, fte, rate, 12 * horizon)
        rw = spec["replace_when"]
        commodity = diff < spec["differentiation"]["commodity_below"]
        covered = x["product_coverage_pct"] >= rw["coverage_at_least"]
        cheaper = ratio <= rw["cost_ratio_at_most"]
        applies = commodity & covered & cheaper
        share = float(applies.mean())
        stops = [h["label"] for h in spec.get("hard_stops", {}).values()
                 if facts.get(h["fact"]) is not None and facts[h["fact"]].value == h["equals"]]
        seam_fact = facts.get(spec["seam"]["fact"])
        seam = None if seam_fact is None or seam_fact.point is None else float(seam_fact.point)
        if share >= confidence and stops:
            verdict, status = "keep_building", "excluded"
        elif share >= confidence:
            verdict = "replace_with_product"
            status = "prepare_first" if seam is not None and seam > spec["seam"]["at_most"] else "go"
        elif share <= 1 - confidence:
            verdict, status = "keep_building", "go"
        else:
            verdict, status = "insufficient_evidence", "insufficient"
        point = {"differentiation": float(diff[0]), "coverage": float(x["product_coverage_pct"][0]),
                 "ratio": float(ratio[0])}
        conditions = [
            ("differentiation", "How much the part sets the organisation apart", point["differentiation"],
             "below", spec["differentiation"]["commodity_below"], bool(commodity[0])),
            ("coverage", "Share of its requirements a product meets without custom development", point["coverage"],
             "at least", rw["coverage_at_least"], bool(covered[0])),
            ("ratio", "Five-year cost of buying relative to building", point["ratio"], "at most",
             rw["cost_ratio_at_most"], bool(cheaper[0])),
        ]

        def shown(key, value):
            return f"{value:.0f}%" if key == "coverage" else f"{value:.2f}" if key == "ratio" else f"{value:.1f}"
        why, beliefs = [], []
        shares = {"differentiation": float(commodity.mean()), "coverage": float(covered.mean()),
                  "ratio": float(cheaper.mean())}
        if verdict == "insufficient_evidence":            # say which condition is too close to call
            for key, label, value, op, threshold, met in conditions:
                if 0.1 < shares[key] < 0.9:
                    why.append(f"{label}: {shown(key, value)} — {op} {shown(key, threshold)} in {shares[key]:.0%} of "
                               "draws, so too close to call.")
        for key, label, value, op, threshold, met in conditions:
            if verdict == "insufficient_evidence":
                break
            line = f"{label}: {shown(key, value)} (to replace: {op} {shown(key, threshold)})."
            if verdict == "replace_with_product":
                why.append(line)
                beliefs.append(f"{label} would have to be {'at least' if op == 'below' else 'below' if op == 'at least' else 'above'} "
                               f"{shown(key, threshold)} (currently {shown(key, value)}).")
            else:
                (why if not met else []).append(line)
                if not met:
                    beliefs.append(f"{label} would have to be {op} {shown(key, threshold)} "
                                   f"(currently {shown(key, value)}).")
        if verdict == "keep_building" and status == "go" and point["ratio"] <= rw["cost_ratio_at_most"]:
            extra = float(build[0] - buy[0])
            why.append(f"Keeping it costs about €{extra / 1e3:,.0f}k more over five years than a product would — the price "
                       "of keeping it in-house.")
        if verdict == "replace_with_product" and beliefs:
            beliefs = ["Keeping it would apply if any one of these held: " + "; ".join(
                b[0].lower() + b[1:].rstrip(".") for b in beliefs) + "."]
        from .gates import gate_status
        gates = []
        if verdict == "replace_with_product":
            for g in spec.get("requires_gates", []):
                info = gate_status(g, rules, eng.governance, assessment.evidence)
                gates.append({"id": g, "label": info["label"], "status": info["status"]})
        out.append({
            **row, "verdict": verdict, "status": status, "probability": round(share if verdict != "keep_building"
                                                                             else 1 - share, 2),
            "replace_share": round(share, 2), "why": why, "beliefs": beliefs, "hard_stops": stops, "gates": gates,
            "seam": seam, "seam_limit": spec["seam"]["at_most"],
            "differentiation": point["differentiation"],
            "differentiation_range": [float(np.nanpercentile(diff, 5)), float(np.nanpercentile(diff, 95))],
            "coverage": point["coverage"],
            "coverage_range": [float(np.nanpercentile(x["product_coverage_pct"], 5)),
                               float(np.nanpercentile(x["product_coverage_pct"], 95))],
            "ratio": point["ratio"], "ratio_range": [float(np.nanpercentile(ratio, 5)), float(np.nanpercentile(ratio, 95))],
            "build_eur": float(build[0]), "buy_eur": float(buy[0]),
            "build_range": [float(np.nanpercentile(build, 5)), float(np.nanpercentile(build, 95))],
            "buy_range": [float(np.nanpercentile(buy, 5)), float(np.nanpercentile(buy, 95))],
            "payback_months": None if payback[0] == np.inf else int(payback[0]),
            "integration_cost": float(x["product_integration_cost"][0]),
            "switch_months": float(x["product_switch_months"][0]),
            "fte_freed": float(x["part_maintain_fte"][0] - x["product_remaining_fte"][0]),
        })
    return out
