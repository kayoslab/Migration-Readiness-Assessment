"""Scoring, uncertainty and the readiness verdict.

Pipeline (identical for domains and themes, selected by `group_col`):

1. Person score   s[p, g] = mean of the answered items in group g that person p's role was asked,
                  provided they answered at least `min_item_coverage` of them.
2. Role score     R[r, g] = mean of s[p, g] over the people in role r.
3. Group index    I[g]    = sum_r w_r * R[r, g] / sum_r w_r over roles with n >= min_role_n.
                  Every stakeholder group counts with its agreed weight, not its headcount.
4. Uncertainty    stratified bootstrap: resample people within each role, recompute 2-3.
5. Status         RED / AMBER / GREEN from the point estimate, flagged "uncertain" when the
                  bootstrap puts less than `confidence` probability on that status.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats

from .config import Config, DecisionRules
from .data import Survey

RED, AMBER, GREEN = "RED", "AMBER", "GREEN"

PROCEED = "Proceed"
CONDITIONAL = "Proceed with conditions"
NOT_READY = "Not ready"
INSUFFICIENT = "Insufficient evidence"


def classify(value: float, rules: DecisionRules) -> str | None:
    if value is None or np.isnan(value):
        return None
    if value < rules.red_below:
        return RED
    return GREEN if value >= rules.green_from else AMBER


# --------------------------------------------------------------------------- person & role scores

def person_scores(survey: Survey, group_col: str, min_coverage: float) -> pd.DataFrame:
    """Rows = respondents (with role), columns = groups. NaN where not asked or too few answers."""
    q = survey.questionnaire
    df = survey.likert.merge(q[[group_col]], left_on="item_id", right_index=True)
    df = df.dropna(subset=[group_col])
    agg = df.groupby(["respondent_id", "role", group_col]).agg(
        asked=("item_id", "size"), answered=("value", "count"), score=("value", "mean")
    )
    agg.loc[agg["answered"] < np.ceil(agg["asked"] * min_coverage), "score"] = np.nan
    wide = agg["score"].unstack(group_col)
    wide = wide.reset_index().set_index("respondent_id")
    groups = [g for g in pd.unique(q[group_col].dropna()) if g in wide.columns]
    return wide[["role", *groups]]


def items_asked(survey: Survey, group_col: str) -> pd.DataFrame:
    """Number of scored items per role x group."""
    q = survey.questionnaire[survey.questionnaire["Type"] == "Quantitative"]
    return pd.DataFrame({r: q[q[r]].groupby(group_col).size() for r in survey.roles}).fillna(0).astype(int)


def _weighted_index(role_means: np.ndarray, weights: np.ndarray) -> np.ndarray:
    """role_means: (..., roles, groups) with NaN for ineligible cells -> (..., groups)."""
    w = np.where(np.isnan(role_means), 0.0, weights[:, None])
    total = w.sum(axis=-2)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(total > 0, np.nansum(role_means * w, axis=-2) / total, np.nan)


@dataclass
class GroupResult:
    group_col: str
    groups: list[str]
    roles: list[str]
    person: pd.DataFrame            # respondent x group
    role_mean: pd.DataFrame         # role x group (NaN if not eligible)
    role_n: pd.DataFrame            # role x group respondent counts
    role_items: pd.DataFrame        # role x group number of items asked
    role_raw_mean: pd.DataFrame     # role x group, including roles below min_role_n (descriptive)
    role_ci: dict                   # (role, group) -> (lo, hi)
    role_p_red: pd.DataFrame        # role x group probability of RED
    summary: pd.DataFrame           # per group: index, ci, probabilities, status, min role ...
    boot_index: np.ndarray = field(repr=False)  # (B, groups)


def score_groups(survey: Survey, cfg: Config, group_col: str = "Category") -> GroupResult:
    rules = cfg.rules
    person = person_scores(survey, group_col, rules.min_item_coverage)
    groups = [c for c in person.columns if c != "role"]
    roles = survey.roles
    weights = np.array([rules.weight(r) for r in roles])

    role_raw_mean = person.groupby("role")[groups].mean().reindex(roles)
    role_n = person.groupby("role")[groups].count().reindex(roles).fillna(0).astype(int)
    role_items = items_asked(survey, group_col).T.reindex(index=roles, columns=groups).fillna(0).astype(int)
    eligible = (role_n >= rules.min_role_n) & (role_items >= rules.min_role_items)
    role_mean = role_raw_mean.where(eligible)

    # Stratified bootstrap: resample people within each role
    rng = np.random.default_rng(cfg.stats.seed)
    B = cfg.stats.bootstrap_iterations
    boot_roles = np.full((B, len(roles), len(groups)), np.nan)
    for i, role in enumerate(roles):
        m = person.loc[person["role"] == role, groups].to_numpy(dtype=float)
        if len(m) == 0:
            continue
        draw = m[rng.integers(0, len(m), size=(B, len(m)))]
        with np.errstate(invalid="ignore"), _quiet():
            boot_roles[:, i, :] = np.nanmean(draw, axis=1)
    boot_roles = np.where(eligible.to_numpy()[None, :, :], boot_roles, np.nan)
    boot_index = _weighted_index(boot_roles, weights)
    index = _weighted_index(role_mean.to_numpy(), weights)

    role_ci, role_p_red = {}, pd.DataFrame(np.nan, index=roles, columns=groups)
    for i, role in enumerate(roles):
        for j, g in enumerate(groups):
            if eligible.iat[i, j]:
                b = boot_roles[:, i, j]
                b = b[~np.isnan(b)]
                role_ci[(role, g)] = tuple(np.percentile(b, [2.5, 97.5]))
                role_p_red.iat[i, j] = float(np.mean(b < rules.red_below))

    rows = []
    for j, g in enumerate(groups):
        b = boot_index[:, j]
        b = b[~np.isnan(b)]
        point = index[j]
        status = classify(point, rules)
        if len(b):
            p = {RED: np.mean(b < rules.red_below), GREEN: np.mean(b >= rules.green_from)}
            p[AMBER] = 1 - p[RED] - p[GREEN]
            lo, hi = np.percentile(b, [2.5, 97.5])
            p_proceed = float(np.mean(b >= rules.proceed_from))
        else:
            p, lo, hi, p_proceed = {RED: np.nan, AMBER: np.nan, GREEN: np.nan}, np.nan, np.nan, np.nan
        scored = role_mean[g].dropna()
        rows.append({
            "group": g,
            "index": point,
            "ci_low": lo,
            "ci_high": hi,
            "status": status,
            "status_probability": p.get(status, np.nan) if status else np.nan,
            "uncertain": bool(status) and p.get(status, 0) < rules.confidence,
            "p_red": p[RED], "p_amber": p[AMBER], "p_green": p[GREEN],
            "p_proceed": p_proceed,
            "roles_scored": list(scored.index),
            "roles_not_scored": [r for r in roles if role_items.at[r, g] > 0 and r not in scored.index],
            "min_role": scored.idxmin() if len(scored) else None,
            "min_role_score": scored.min() if len(scored) else np.nan,
            "max_role": scored.idxmax() if len(scored) else None,
            "max_role_score": scored.max() if len(scored) else np.nan,
            "respondents": int(person[g].notna().sum()),
        })
    summary = pd.DataFrame(rows).set_index("group")
    return GroupResult(group_col, groups, roles, person, role_mean, role_n, role_items, role_raw_mean,
                       role_ci, role_p_red, summary, boot_index)


class _quiet:
    """Silence 'Mean of empty slice' warnings inside the bootstrap."""

    def __enter__(self):
        import warnings
        self._ctx = warnings.catch_warnings()
        self._ctx.__enter__()
        warnings.simplefilter("ignore", category=RuntimeWarning)

    def __exit__(self, *exc):
        return self._ctx.__exit__(*exc)


# --------------------------------------------------------------------------- reliability

def cronbach_alpha(items: pd.DataFrame, min_periods: int = 3) -> float:
    """Cronbach's alpha from the pairwise item covariance matrix (tolerates scattered missing answers).

    alpha = k / (k - 1) * (1 - trace(C) / sum(C))
    """
    k = items.shape[1]
    if k < 2:
        return np.nan
    cov = items.cov(min_periods=min_periods).to_numpy()
    if np.isnan(cov).any():
        return np.nan
    total = cov.sum()
    return np.nan if total <= 0 else k / (k - 1) * (1 - np.trace(cov) / total)


def reliability(survey: Survey, cfg: Config, group_col: str = "Category") -> pd.DataFrame:
    """Alpha per role x group (only cells that feed the index: enough people and items)."""
    q = survey.questionnaire
    rows = []
    for role in survey.roles:
        sub = survey.likert[survey.likert["role"] == role]
        wide = sub.pivot_table(index="respondent_id", columns="item_id", values="value", aggfunc="first")
        for g, items in q[q["Type"] == "Quantitative"].groupby(group_col):
            cols = [i for i in items.index if items.at[i, role] and i in wide.columns]
            if len(cols) < max(cfg.rules.min_role_items, 2) or len(wide) < cfg.rules.min_role_n:
                continue
            rows.append({"group": g, "role": role, "items": len(cols), "n": len(wide),
                         "alpha": cronbach_alpha(wide[cols].astype(float))})
    df = pd.DataFrame(rows, columns=["group", "role", "items", "n", "alpha"])
    return df


def reliability_summary(rel: pd.DataFrame, rules: DecisionRules) -> pd.DataFrame:
    if rel.empty:
        return pd.DataFrame(columns=["median_alpha", "min_alpha", "reliable"])
    out = rel.groupby("group")["alpha"].agg(median_alpha="median", min_alpha="min")
    out["reliable"] = out["median_alpha"] >= rules.min_reliability
    return out


# --------------------------------------------------------------------------- role differences

def role_differences(res: GroupResult, rules: DecisionRules) -> pd.DataFrame:
    """Kruskal-Wallis across scored roles per group, with epsilon-squared and BH-adjusted q."""
    rows = []
    for g in res.groups:
        roles = [r for r in res.roles if not np.isnan(res.role_mean.at[r, g])]
        samples = [res.person.loc[res.person["role"] == r, g].dropna().to_numpy() for r in roles]
        if len(samples) < 2:
            continue
        h, p = stats.kruskal(*samples)
        n = sum(len(s) for s in samples)
        rows.append({"group": g, "roles": len(roles), "n": n, "H": h, "p": p,
                     "epsilon_sq": h / (n - 1) if n > 1 else np.nan,
                     "spread": res.role_mean.loc[roles, g].max() - res.role_mean.loc[roles, g].min()})
    df = pd.DataFrame(rows)
    if len(df):
        df["q"] = stats.false_discovery_control(df["p"].to_numpy())
        df = df.set_index("group")
    return df


# --------------------------------------------------------------------------- item level

def item_statistics(survey: Survey, cfg: Config) -> pd.DataFrame:
    """Per item: role means (scored roles only), role-weighted item score, distribution, gap test."""
    rules = cfg.rules
    q = survey.questionnaire
    lk = survey.likert
    rng = np.random.default_rng(cfg.stats.seed + 1)
    B = cfg.stats.permutation_iterations
    rows = []
    for item_id, sub in lk.groupby("item_id"):
        answered = sub.dropna(subset=["value"])
        counts = answered.groupby("role")["value"].agg(["mean", "count"])
        scored = counts[counts["count"] >= rules.min_role_n]
        w = np.array([rules.weight(r) for r in scored.index])
        score = float(np.average(scored["mean"], weights=w)) if len(scored) else np.nan
        dist = answered["value"].value_counts().reindex([1, 2, 3, 4, 5], fill_value=0)
        row = {
            "item_id": item_id,
            "question": q.at[item_id, "Question"],
            "domain": q.at[item_id, "Category"],
            "theme": q.at[item_id, "Theme"] if "Theme" in q.columns else None,
            "critical": bool(q.at[item_id, "Critical"]),
            "score": score,
            "n": int(len(answered)),
            "asked": int(len(sub)),
            "dont_know": int(sub["dont_know"].sum()),
            "role_means": {r: float(m) for r, m in scored["mean"].items()},
            **{f"n_{k}": int(v) for k, v in dist.items()},
            "gap": np.nan, "gap_p": np.nan, "gap_high_role": None, "gap_low_role": None,
        }
        if len(scored) >= 2:
            pool = answered[answered["role"].isin(scored.index)]
            values = pool["value"].to_numpy()
            labels = pd.Categorical(pool["role"], categories=list(scored.index)).codes
            observed = scored["mean"].max() - scored["mean"].min()
            perm = rng.permuted(np.tile(labels, (B, 1)), axis=1)
            means = np.stack([(np.where(perm == k, values, 0).sum(1) / (perm == k).sum(1))
                              for k in range(len(scored))], axis=1)
            null = means.max(1) - means.min(1)
            row.update(gap=float(observed), gap_p=float((1 + np.sum(null >= observed - 1e-12)) / (1 + B)),
                       gap_high_role=scored["mean"].idxmax(), gap_low_role=scored["mean"].idxmin())
        rows.append(row)
    df = pd.DataFrame(rows).set_index("item_id")
    tested = df["gap_p"].notna()
    df["gap_q"] = np.nan
    if tested.any():
        df.loc[tested, "gap_q"] = stats.false_discovery_control(df.loc[tested, "gap_p"].to_numpy())
    total = df[[f"n_{k}" for k in range(1, 6)]].sum(axis=1).replace(0, np.nan)
    df["pct_disagree"] = (df["n_1"] + df["n_2"]) / total
    df["pct_neutral"] = df["n_3"] / total
    df["pct_agree"] = (df["n_4"] + df["n_5"]) / total
    return df


# --------------------------------------------------------------------------- verdict

@dataclass
class Verdict:
    decision: str
    evidence: str                 # "strong" | "indicative" | "insufficient"
    reasons: list[str]
    blocking: list[str]           # groups / role-group pairs that block "Proceed"


def verdict(domains: GroupResult, survey: Survey, cfg: Config) -> Verdict:
    rules = cfg.rules
    n_by_role = survey.respondents["role"].value_counts()
    essential = rules.essential_roles or survey.roles
    missing = [r for r in essential if n_by_role.get(r, 0) < rules.min_role_n]
    if missing:
        return Verdict(INSUFFICIENT, "insufficient",
                       [f"Fewer than {rules.min_role_n} respondents from: {', '.join(missing)}."], missing)

    evidence = "strong" if all(n_by_role.get(r, 0) >= rules.strong_evidence_role_n for r in essential) \
        else "indicative"
    s = domains.summary
    red = [g for g in s.index if s.at[g, "p_red"] >= rules.confidence]
    vetoes = [f"{r} on {g}" for g in rules.role_veto_domains if g in domains.groups
              for r in essential if domains.role_p_red.at[r, g] >= rules.confidence]
    if red or vetoes:
        reasons = [f"{g} is RED with ≥{rules.confidence:.0%} probability." for g in red]
        reasons += [f"{v} is RED with ≥{rules.confidence:.0%} probability." for v in vetoes]
        return Verdict(NOT_READY, evidence, reasons, red + vetoes)

    below = [g for g in s.index if not s.at[g, "p_proceed"] >= rules.confidence]
    role_red = [f"{r} on {g}" for g in domains.groups for r in domains.roles
                if domains.role_mean.at[r, g] < rules.red_below]
    if not below and not role_red:
        return Verdict(PROCEED, evidence,
                       [f"Every domain clears {rules.proceed_from:.1f} with ≥{rules.confidence:.0%} probability "
                        "and no stakeholder group scores any domain RED."], [])
    reasons = [f"{g} does not clear {rules.proceed_from:.1f} with ≥{rules.confidence:.0%} probability."
               for g in below]
    reasons += [f"{v} scores below {rules.red_below:.1f}." for v in role_red]
    return Verdict(CONDITIONAL, evidence, reasons, below + role_red)
