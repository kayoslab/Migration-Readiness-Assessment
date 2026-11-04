"""Evidence: survey items and fact-sheet values combined into sub-area and axis scores, per bootstrap draw.

Each draw resamples respondents within their group and samples every ranged fact from its PERT distribution.
Draw 0 is always the point estimate (all respondents, facts at their likely value), so it doubles as the
basis for explanations and divergence findings. Signal arrays have one entry per draw.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .engagement import Engagement, Fact
from .instrument import DONT_KNOW, TECHNICAL_BLOCKS, Instrument

_COUNT = re.compile(r"(\d+)(?:-(\d+))?=(\d+(?:\.\d+)?)")


def count_band(spec: str, yes: int, answered: int, total_rows: int, full_rows: int | None = None) -> float:
    """Score a count grid; "don't know" rows are excluded and the count rescaled to all rows.

    `total_rows` is the number of rows the respondent was shown; `full_rows` (default: the same) the grid's full
    length, on which the count scale is defined — a group shown only some rows is rescaled to the full grid."""
    full_rows = full_rows or total_rows
    if answered == 0 or answered < total_rows / 2:
        return np.nan
    scaled = round(yes * full_rows / answered)
    for lo, hi, score in _COUNT.findall(spec[len("count:"):]):
        if int(lo) <= scaled <= int(hi or lo):
            return float(score)
    return np.nan


def pert(rng: np.random.Generator, low: float, likely: float, high: float, size: int,
         uniform: np.ndarray | None = None) -> np.ndarray:
    """PERT draws; pass shared `uniform` quantiles to correlate several inputs (e.g. migration overruns)."""
    if high <= low:
        return np.full(size, likely, dtype=float)
    a = 1 + 4 * (likely - low) / (high - low)
    b = 1 + 4 * (high - likely) / (high - low)
    if uniform is None:
        return low + rng.beta(a, b, size) * (high - low)
    from scipy.stats import beta
    return low + beta.ppf(uniform, a, b) * (high - low)


def widen(fact: Fact, min_width: dict[str, float]) -> tuple[float, float, float]:
    """Enforce the minimum range width for the fact's source grade (estimates cannot be falsely precise)."""
    low, likely, high = float(fact.low), float(fact.likely), float(fact.high)
    w = min_width.get(fact.grade or "estimate", min_width.get("estimate", 0.0))
    if likely and (high - low) < w * abs(likely):
        low = min(low, likely - w * abs(likely) / 2)
        high = max(high, likely + w * abs(likely) / 2)
    return low, likely, high


def derive_current_state(ins: Instrument, facts: dict[str, Fact]) -> str:
    from .decision import Context, evaluate
    ctx = Context.from_values({f"fact.{k}": v.point for k, v in facts.items()}, ins.rules)
    for step in ins.rules["signals"]["current_state"]["derive"]:
        if "when" not in step or evaluate(step["when"], ctx) is True:
            return step["then"]
    return "single_deployable"


@dataclass
class Evidence:
    signals: dict[str, np.ndarray]                    # numeric signals, shape (B,)
    categories: dict[str, str]                        # categorical facts (fixed)
    current_state: dict[str, str]
    divergences: list[dict] = field(default_factory=list)
    item_groups: pd.DataFrame | None = None           # point estimate: item x role means and n
    missing_required: list[str] = field(default_factory=list)
    flags: dict = field(default_factory=dict)
    fact_point: dict[str, float] = field(default_factory=dict)                  # numeric facts at their likely value
    fact_ranges: dict[str, tuple[float, float]] = field(default_factory=dict)   # widened low/high of ranged facts

    @property
    def draws(self) -> int:
        return len(next(iter(self.signals.values())))

    def at(self, b: int) -> dict:
        values = {k: (None if np.isnan(v[b]) else float(v[b])) for k, v in self.signals.items()}
        values.update({f"fact.{k}": v for k, v in self.categories.items()})
        return values


def respondent_scores(eng: Engagement) -> pd.DataFrame:
    """Score per respondent (index) and scored item (columns); NaN where not answered."""
    ins, ans = eng.instrument, eng.answers
    item_ids = list(ins.items.index[ins.items["scored"] == "true"])
    single = ans[ans["row"].isna()]
    scores = single.pivot_table(index="respondent_id", columns="item_id", values="score", aggfunc="first")
    for gid in [i for i in item_ids if ins.items.at[i, "format"] == "grid"]:   # per-respondent grid scores
        spec, sub = ins.scores(gid), ans[(ans["item_id"] == gid) & ans["row"].notna()]
        full_rows = len(ins.items.at[gid, "rows"].split("|"))
        for rid, g in sub.groupby("respondent_id"):
            answered = int((g["label"] != DONT_KNOW).sum())
            yes = int((g["label"] == "Yes").sum())
            shown = len(ins.rows_for(gid, g["role"].iloc[0])) if not ins.items.at[gid, "rows"].startswith("@") \
                else full_rows
            scores.loc[rid, gid] = count_band(spec, yes, answered, shown, full_rows)
    return scores.reindex(columns=item_ids)


def build_evidence(eng: Engagement, draws: int | None = None, seed: int = 42) -> Evidence:
    ins, rules = eng.instrument, eng.instrument.rules
    ev_cfg = rules.get("evidence", {})
    B = draws or ev_cfg.get("bootstrap_iterations", 2000)
    rng = np.random.default_rng(seed)
    min_n = ev_cfg.get("min_role_n", 5)
    role_weights = ev_cfg.get("role_weights") or {}
    involvement = ev_cfg.get("involvement_weights") or {}
    fw, sw = ev_cfg.get("fact_weight", 2), ev_cfg.get("survey_weight", 1)
    signals: dict[str, np.ndarray] = {}

    # ------------------------------------------------------------------ survey: respondent x item matrices per role
    person_scores = respondent_scores(eng)
    item_ids = list(person_scores.columns)
    ans = eng.answers
    single = ans[ans["row"].isna()]

    people = eng.respondents.set_index("respondent_id") if len(eng.respondents) else pd.DataFrame(columns=["role", "involvement"])
    from .groups import for_engagement
    people = people.assign(group=for_engagement(eng, min_n)) if len(people) else people.assign(group=None)
    technical = np.array([ins.items.at[i, "block"] in TECHNICAL_BLOCKS for i in item_ids])
    roles = list(dict.fromkeys(people["group"].dropna())) if len(people) else []      # reporting groups (mra/groups.py)
    rw = np.array([float(role_weights.get(r, 1.0)) for r in roles])

    role_item_means = np.full((B, len(roles), len(item_ids)), np.nan)
    point_rows = []
    for ri, role in enumerate(roles):
        rids = list(people.index[people["group"] == role])
        S = person_scores.reindex(index=rids).to_numpy(dtype=float)                       # n x k
        inv = np.array([involvement.get(people.at[r, "involvement"], 1.0) if involvement else 1.0 for r in rids])
        W = np.where(technical[None, :], inv[:, None], 1.0) * ~np.isnan(S)
        idx = rng.integers(0, len(rids), size=(B, len(rids)))
        idx[0] = np.arange(len(rids))                                                     # draw 0 = point estimate
        Sb, Wb = np.nan_to_num(S)[idx], W[idx]                                            # B x n x k
        answered = (~np.isnan(S))[idx].sum(axis=1)
        with np.errstate(invalid="ignore", divide="ignore"):
            means = (Sb * Wb).sum(axis=1) / Wb.sum(axis=1)
        means[answered < min_n] = np.nan
        role_item_means[:, ri, :] = means
        for k, item in enumerate(item_ids):
            point_rows.append({"item_id": item, "role": role, "mean": means[0, k], "n": int(answered[0, k])})

    with np.errstate(invalid="ignore", divide="ignore"):
        w = np.where(np.isnan(role_item_means), 0.0, rw[None, :, None])
        item_scores = np.where(w.sum(axis=1) > 0, np.nansum(role_item_means * w, axis=1) / w.sum(axis=1), np.nan) \
            if roles else np.full((B, len(item_ids)), np.nan)
    for k, item in enumerate(item_ids):
        signals[f"item.{item}"] = item_scores[:, k]

    # share_of signals (pooled over respondents who answered the item, resampled per draw)
    for name, spec in rules.get("signals", {}).items():
        if "share_of" not in spec:
            continue
        sub = single[single["item_id"] == spec["item"]]
        sub = sub[~sub["dont_know"] & ~sub["not_applicable"]]
        hits = sub["label"].isin(spec["share_of"]).to_numpy(dtype=float)
        if len(hits) == 0:
            signals[name] = np.full(B, np.nan)
            continue
        idx = rng.integers(0, len(hits), size=(B, len(hits)))
        idx[0] = np.arange(len(hits))
        signals[name] = hits[idx].mean(axis=1)

    # ------------------------------------------------------------------ facts
    min_width = (rules.get("fact_discipline") or {}).get("min_range_width_by_grade", {})
    widen_cfg = (rules.get("fact_discipline") or {}).get("widen_single_values", {})
    ref_class = (rules.get("fact_discipline") or {}).get("reference_class", {})
    overrun_fact = eng.facts.get(ref_class.get("overrun_fact", ""))
    overrun = float(overrun_fact.point) if overrun_fact is not None and overrun_fact.point is not None else 0.0
    correlated = set((rules.get("tco") or {}).get("correlated", []))
    shared_u = rng.random(B)                                     # one overrun quantile per draw for the group
    categories, fact_values, fact_ranges = {}, {}, {}
    for fid, fact in eng.facts.items():
        if fid not in ins.facts.index:
            continue
        if ins.facts.at[fid, "kind"] == "category":
            categories[fid] = fact.value
            continue
        if not fact.is_range and isinstance(fact.value, (int, float)) and fact.value and \
                (ins.facts.at[fid, "unit"] in widen_cfg.get("units", []) or fid in widen_cfg.get("facts", [])):
            fact = Fact(low=float(fact.value), likely=float(fact.value), high=float(fact.value), grade=fact.grade)
        if fact.is_range:
            low, likely, high = widen(fact, min_width)
            if fid in ref_class.get("applies_to", []) and overrun:      # the organisation's own track record
                high = max(high, likely * (1 + overrun / 100))
            if ins.facts.at[fid, "unit"] == "%":
                low, high = max(low, 0.0), min(high, 100.0)
            fact_ranges[fid] = (low, high)
            values = pert(rng, low, likely, high, B, shared_u if fid in correlated else None)
            values[0] = likely
        else:
            values = np.full(B, np.nan if fact.value is None else float(fact.value))
        fact_values[fid] = values
        signals[f"fact.{fid}"] = values

    # ------------------------------------------------------------------ hosting TCO (mra/tco.py)
    tco_problems = []
    hosting = rules.get("decisions", {}).get("hosting", {})
    if any(f in fact_values for f in ("cloud_compute_baseline_annual", "hw_maintenance_annual")):
        from .tco import compute as tco_compute
        tco_signals, tco_problems = tco_compute(fact_values, eng.config.get("current_hosting", "own_infrastructure"),
                                                hosting.get("horizon_years", 5))
        signals.update(tco_signals)

    # ------------------------------------------------------------------ sub-areas: fact bands (weight 2) + survey (weight 1)
    def fact_band_array(fid: str) -> np.ndarray | None:
        if fid in categories:
            band = ins.fact_band(fid, categories[fid])
            return None if band is None else np.full(B, band)
        if fid in fact_values:
            f = ins.facts.loc[fid]
            if f["direction"] == "none" or not f["cuts"]:
                return None
            cuts = np.array([float(c) for c in f["cuts"].split("|")])
            v = fact_values[fid]
            band = 1 + (v[:, None] >= cuts[None, :]).sum(axis=1).astype(float)
            band = np.where(np.isnan(v), np.nan, band if f["direction"] == "up" else 6 - band)
            return band
        return None

    subareas: dict[tuple[str, str, str], dict] = {}
    for item in item_ids:
        it = ins.items.loc[item]
        for d in (["architecture", "hosting"] if it["decision"] == "both" else [it["decision"]]):
            subareas.setdefault((it["block"], d, it["area"]), {"items": [], "facts": []})["items"].append(item)
    for fid, f in ins.facts.iterrows():
        key = (f["axis"], f["decision"], f["area"])
        if f["direction"] != "none" or (f["kind"] == "category" and f["category_scores"]):
            subareas.setdefault(key, {"items": [], "facts": []})["facts"].append(fid)
        if fid in categories or fid in fact_values:
            band = fact_band_array(fid)
            if band is not None:
                signals[f"band.{fid}"] = band

    fact_decides = set(ev_cfg.get("fact_decides") or [])
    sub_scores: dict[tuple, np.ndarray] = {}
    has_fact: dict[tuple, bool] = {}
    backed_by_required: dict[tuple, bool] = {}
    divergences = []
    for key, parts in subareas.items():
        with np.errstate(invalid="ignore"), _quiet():
            survey = np.nanmean(np.stack([signals[f"item.{i}"] for i in parts["items"]]), axis=0) \
                if parts["items"] else np.full(B, np.nan)
            bands = [b for b in (fact_band_array(f) for f in parts["facts"]) if b is not None]
            fact = np.nanmean(np.stack(bands), axis=0) if bands else np.full(B, np.nan)
        block, decision, area = key
        name = f"{block}.{area}" if block in ("fit", "requirement", "locality") else f"{block}.{decision}.{area}"
        wf = np.where(np.isnan(fact), 0, fw)
        ws = np.where(np.isnan(survey) | (name in fact_decides), 0, sw)   # perception checks only: never fill in
        with np.errstate(invalid="ignore", divide="ignore"):
            combined = (np.nan_to_num(fact) * wf + np.nan_to_num(survey) * ws) / (wf + ws)
        sub_scores[key] = combined
        has_fact[key] = bool(bands)
        backed_by_required[key] = any(ins.facts.at[f, "required"] == "true" for f in parts["facts"])
        signals[name] = combined
        if bands and not np.isnan(fact[0]) and not np.isnan(survey[0]) and \
                abs(fact[0] - survey[0]) > ev_cfg.get("divergence_flag_bands", 1.0):
            divergences.append({"sub_area": name, "fact_band": round(float(fact[0]), 2),
                                "survey": round(float(survey[0]), 2), "facts": parts["facts"], "items": parts["items"]})

    # ------------------------------------------------------------------ composite axes
    axes_cfg = rules.get("axes", {})
    for block, decision in {(k[0], k[1]) for k in sub_scores if k[0] in ("need", "locality", "capability")}:
        name = "locality" if block == "locality" else f"{block}.{decision}"
        if block == "locality" and decision != "architecture":
            continue
        areas = axes_cfg.get(f"{block}.{decision}", {}).get("areas") or \
            [k[2] for k in sub_scores if k[0] == block and k[1] == decision]
        keys = [(block, decision, a) for a in areas if (block, decision, a) in sub_scores]
        if not keys:
            continue
        values = np.stack([sub_scores[k] for k in keys])
        weights = np.array([1.0 if has_fact[k] else 0.5 for k in keys])[:, None] * ~np.isnan(values)
        # a sub-area backed by a required fact with no evidence at all leaves the composite unresolved
        core_missing = np.stack([np.isnan(sub_scores[k]) & backed_by_required[k] for k in keys]).any(0)
        with np.errstate(invalid="ignore", divide="ignore"):
            composite = np.where(weights.sum(0) > 0, (np.nan_to_num(values) * weights).sum(0) / weights.sum(0), np.nan)
        signals[name] = np.where(core_missing, np.nan, composite)

    # ------------------------------------------------------------------ required facts that are missing
    arch_state = derive_current_state(ins, eng.facts)
    missing = []
    for fid, f in ins.facts.iterrows():
        need = f["required"] == "true" or (f["required"] == "if_distributed" and arch_state == "distributed") or \
            (f["required"] == "if_cloud" and eng.config.get("current_hosting") == "cloud") or \
            (f["required"] == "if_hybrid" and eng.config.get("current_hosting") == "hybrid")
        if need and (fid not in eng.facts or eng.facts[fid].point is None):
            missing.append(fid)

    # track record (G14): ≥ threshold of informed respondents report a failed programme, in any group large enough
    # to report or across everyone; a small group counts only in the overall share
    threshold = ((rules.get("gates", {}).get("stop_criteria") or {}).get("mandatory_if") or {}).get("value", 0.3)
    g14 = single[(single["item_id"] == "G14") & ~single["dont_know"]]
    concern = False
    if len(g14):
        yes = g14.assign(yes=g14["label"] == "Yes", group=g14["respondent_id"].map(people["group"]))
        by_role = yes.groupby("group")["yes"].agg(["mean", "size"])
        concern = bool((by_role[by_role["size"] >= min_n]["mean"] >= threshold).any() or yes["yes"].mean() >= threshold)
    flags = {"track_record_concern": concern, "tco_problems": tco_problems}

    return Evidence(signals, categories, eng.current_states(arch_state), divergences,
                    pd.DataFrame(point_rows), missing, flags,
                    {k: float(v[0]) for k, v in fact_values.items()}, fact_ranges)


class _quiet:
    def __enter__(self):
        import warnings
        self._ctx = warnings.catch_warnings()
        self._ctx.__enter__()
        warnings.simplefilter("ignore", category=RuntimeWarning)

    def __exit__(self, *exc):
        return self._ctx.__exit__(*exc)
