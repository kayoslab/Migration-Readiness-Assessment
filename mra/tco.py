"""Hosting total cost of ownership per option, per bootstrap draw (decision_rules.yaml → tco).

All inputs come from the fact sheet (low / likely / high, widened by source grade, PERT-sampled in mra/axes.py).
Every option is evaluated on the same draw, so shared assumptions (growth, salaries, price changes) cancel out
in the ratios ("common random numbers"). Costs are monthly cash flows over the horizon, discounted at the
pre-registered rate:

    TCO(option) = Σ_m (run cost_m + one-offs_m) / (1+r)^(m/12) − residual value at horizon end

Options by current hosting state:
    own_infrastructure: stay (as is) · improve_current (right-sized) · cloud · hybrid
    cloud:              stay (as is) · improve_current (optimised cloud) · repatriate · hybrid
Ratios divide by the optimised current state, except improve_current, which divides by the current state as is.
"""

from __future__ import annotations

import numpy as np

OWN_RUN = ["hw_maintenance_annual", "dc_cost_annual", "network_transit_annual", "dr_site_annual", "licence_cost_annual"]
CLOUD_RUN = ["cloud_egress_annual", "cloud_network_internal_annual", "cloud_support_tooling_annual",
             "cloud_managed_annual", "cloud_dr_annual"]
COMMON = ["fte_cost_annual", "growth_pct_annual", "own_price_change_pct_annual", "cloud_price_change_pct_annual",
          "discount_rate_pct", "migration_cost", "migration_months", "dual_run_months", "training_hiring_cost",
          "rightsized_share_pct", "automation_investment", "toil_reduction_pct", "exit_cost"]
OWN = OWN_RUN + ["ops_fte", "infra_share_pct", "hw_refresh_capex", "hw_refresh_due_months", "residual_value"]
CLOUD = ["cloud_compute_baseline_annual", "cloud_committed_share_pct", "cloud_commit_discount_pct",
         "cloud_peak_cost_annual", "cloud_ops_fte"] + CLOUD_RUN
HYBRID = ["need_share_pct", "hybrid_interconnect_annual", "hybrid_overhead_fte"]
OPTIONAL_ZERO = ["bridge_cost", "sunk_commitment_cost", "exit_cost", "hybrid_interconnect_annual", "hybrid_overhead_fte"]


class Missing(Exception):
    pass


class _Model:
    def __init__(self, f: dict[str, np.ndarray], horizon_years: int):
        self.f = f
        self.B = len(next(iter(f.values())))
        self.M = 12 * horizon_years
        self.m = np.arange(1, self.M + 1)[None, :]                                   # 1 x M
        self.growth = (1 + self.v("growth_pct_annual") / 100)[:, None] ** ((self.m - 1) / 12)
        self.p_own = (1 + self.v("own_price_change_pct_annual") / 100)[:, None] ** ((self.m - 1) / 12)
        self.p_cloud = (1 + self.v("cloud_price_change_pct_annual") / 100)[:, None] ** ((self.m - 1) / 12)
        self.discount = (1 + self.v("discount_rate_pct") / 100)[:, None] ** (-self.m / 12)
        self.fte = self.v("fte_cost_annual")

    def v(self, name: str) -> np.ndarray:
        if name in self.f and not np.isnan(self.f[name]).all():
            return np.nan_to_num(self.f[name])
        if name in OPTIONAL_ZERO:
            return np.zeros(self.B)
        raise Missing(name)

    def at_month(self, amount: np.ndarray, month: np.ndarray) -> np.ndarray:
        """A one-off amount placed in the given month (ignored beyond the horizon)."""
        mm = np.clip(np.ceil(month), 1, None)[:, None]
        return np.where(self.m == mm, amount[:, None], 0.0)

    # ------------------------------------------------------------------ monthly running costs
    def own(self, capacity: np.ndarray, staff_factor: np.ndarray | float = 1.0) -> np.ndarray:
        infra = sum(self.v(k) for k in OWN_RUN) / 12
        staff = self.v("ops_fte") * self.v("infra_share_pct") / 100 * self.fte / 12
        return infra[:, None] * capacity[:, None] * self.growth * self.p_own + (staff[:, None] * staff_factor)

    def cloud(self, share: np.ndarray, rightsize: np.ndarray | float = 1.0, staff: bool = True) -> np.ndarray:
        """Cloud running cost for `share` of the estate; in hybrid setups staffing comes from hybrid_overhead_fte."""
        committed = np.clip(self.v("cloud_committed_share_pct") / 100, 0, 1)
        compute = self.v("cloud_compute_baseline_annual") * (committed * (1 - self.v("cloud_commit_discount_pct") / 100)
                                                            + (1 - committed)) + self.v("cloud_peak_cost_annual")
        other = sum(self.v(k) for k in CLOUD_RUN)
        monthly = ((compute * rightsize + other) / 12)[:, None] * self.growth * self.p_cloud * share[:, None]
        if not staff:
            return monthly
        return monthly + (self.v("cloud_ops_fte") * self.fte / 12)[:, None] * (share > 0)[:, None]

    def refresh(self, capacity: np.ndarray) -> np.ndarray:
        due = self.v("hw_refresh_due_months")
        grown = (1 + self.v("growth_pct_annual") / 100) ** (np.maximum(due - 1, 0) / 12)
        return self.at_month(self.v("hw_refresh_capex") * capacity * grown, due)

    def residual(self, capacity: np.ndarray) -> np.ndarray:
        return self.at_month(self.v("residual_value") * capacity, np.full(self.B, self.M))

    def transition(self, before: np.ndarray, after: np.ndarray) -> np.ndarray:
        """Pay `before` until cut-over (migration_months); `after` from dual_run_months before cut-over."""
        cut = self.v("migration_months")[:, None]
        start_after = cut - self.v("dual_run_months")[:, None]
        return np.where(self.m <= cut, before, 0.0) + np.where(self.m > start_after, after, 0.0)

    def npv(self, monthly: np.ndarray, residual: np.ndarray | None = None) -> np.ndarray:
        total = (monthly * self.discount).sum(axis=1)
        if residual is not None:
            total -= (residual * self.discount).sum(axis=1)
        return total


def _options(model: _Model, current: str) -> dict[str, dict]:
    """Monthly cost streams (and residual values) per option."""
    B, one = model.B, np.ones(model.B)
    k = np.clip(model.v("rightsized_share_pct") / 100, 0.05, 1.0)
    start = np.ones(B)
    ramp = np.clip(model.m / 12, 0, 1)                                             # toil reduction ramps over a year
    toil = 1 - model.v("toil_reduction_pct")[:, None] / 100 * ramp
    migration = model.at_month(model.v("migration_cost") + model.v("training_hiring_cost"), start)
    exit_cost = model.at_month(model.v("exit_cost"), np.full(B, model.M))
    improve_once = model.at_month(model.v("automation_investment"), start)

    if current == "own_infrastructure":
        h = np.clip(model.v("need_share_pct") / 100, 0, 1)
        due, cut = model.v("hw_refresh_due_months"), model.v("migration_months")
        bridge = model.at_month(np.where(due <= cut, model.v("bridge_cost"), 0.0), due)
        remaining = k * (1 - h)                       # the core that stays is right-sized, like the baseline
        hybrid_after = model.own(remaining, toil) + model.cloud(h, staff=False) + \
            ((model.v("hybrid_interconnect_annual") + model.v("hybrid_overhead_fte") * model.fte) / 12)[:, None]
        return {
            "stay": {"cost": model.own(one) + model.refresh(one), "residual": model.residual(one)},
            "improve_current": {"cost": model.own(k, toil) + model.refresh(k) + improve_once, "residual": model.residual(k)},
            "cloud": {"cost": model.transition(model.own(one), model.cloud(one)) + migration + bridge + exit_cost,
                      "residual": None},
            "hybrid": {"cost": model.transition(model.own(one), hybrid_after) + model.refresh(remaining) * (due > cut)[:, None]
                       + bridge + model.at_month((model.v("migration_cost") * h) + model.v("training_hiring_cost"), start)
                       + model.at_month(model.v("exit_cost") * h, np.full(B, model.M)),
                       "residual": model.residual(remaining)},
        }
    if current == "cloud":
        h = np.clip(model.v("need_share_pct") / 100, 0, 1)        # share that keeps its specific need in the cloud
        back = 1 - h
        capex = model.at_month(model.v("hw_refresh_capex"), start)
        sunk = model.at_month(model.v("sunk_commitment_cost"), start)
        hybrid_after = model.cloud(h, k, staff=False) + model.own(back) + \
            ((model.v("hybrid_interconnect_annual") + model.v("hybrid_overhead_fte") * model.fte) / 12)[:, None]
        return {
            "stay": {"cost": model.cloud(one), "residual": None},
            "improve_current": {"cost": model.cloud(one, k) + improve_once, "residual": None},
            "repatriate": {"cost": model.transition(model.cloud(one), model.own(one)) + capex + migration + sunk,
                           "residual": model.residual(one)},
            "hybrid": {"cost": model.transition(model.cloud(one), hybrid_after) + model.at_month(model.v("hw_refresh_capex") * back, start)
                       + model.at_month(model.v("migration_cost") * back + model.v("training_hiring_cost"), start)
                       + model.at_month(model.v("sunk_commitment_cost") * back, start),
                       "residual": model.residual(back)},
        }
    raise Missing(f"TCO for current hosting state {current!r} is not modelled yet")


def compute(facts: dict[str, np.ndarray], current: str, horizon_years: int = 5) -> tuple[dict[str, np.ndarray], list[str]]:
    """Signals tco.<option>, tco_ratio.<option>, payback_months.<option>, tco_saving_fte.<option>; plus problems."""
    try:
        model = _Model(facts, horizon_years)
        options = _options(model, current)
    except Missing as exc:
        return {}, [f"hosting TCO not computed: missing {exc}"]
    tco = {o: model.npv(s["cost"], s["residual"]) for o, s in options.items()}
    cumulative = {o: np.cumsum(s["cost"], axis=1) for o, s in options.items()}
    signals = {f"tco.{o}": v for o, v in tco.items()}
    for option in options:
        if option == "stay":
            continue
        base = "stay" if option == "improve_current" else "improve_current"
        signals[f"tco_ratio.{option}"] = tco[option] / tco[base]
        ahead = cumulative[option] <= cumulative[base]
        # payback: first month from which the option stays cheaper on a cumulative basis
        stays_ahead = np.flip(np.cumprod(np.flip(ahead, axis=1), axis=1), axis=1).astype(bool)
        first = np.where(stays_ahead.any(axis=1), stays_ahead.argmax(axis=1) + 1, np.inf)
        signals[f"payback_months.{option}"] = first.astype(float)
        signals[f"tco_saving_fte.{option}"] = (tco[base] - tco[option]) / horizon_years / model.fte
    return signals, []


def sensitivity(point: dict[str, float], ranges: dict[str, tuple[float, float]], current: str, option: str,
                horizon_years: int = 5) -> list[dict]:
    """Tornado data: the option's TCO ratio with each ranged input at its low and high value, others at likely."""
    def ratio(values: dict[str, float]) -> float:
        signals, problems = compute({k: np.array([v], dtype=float) for k, v in values.items()}, current, horizon_years)
        return float(signals.get(f"tco_ratio.{option}", [np.nan])[0])
    base = ratio(point)
    rows = []
    for name, (low, high) in ranges.items():
        lo, hi = ratio({**point, name: low}), ratio({**point, name: high})
        rows.append({"input": name, "low": lo, "high": hi, "swing": abs(hi - lo)})
    return [{"base": base}] + sorted(rows, key=lambda r: -r["swing"])


def horizons(point: dict[str, float], current: str, years=(3, 5, 7)) -> dict[int, dict[str, float]]:
    out = {}
    for y in years:
        signals, _ = compute({k: np.array([v], dtype=float) for k, v in point.items()}, current, y)
        out[y] = {k.split(".", 1)[1]: round(float(v[0]), 3) for k, v in signals.items() if k.startswith("tco_ratio.")}
    return out
