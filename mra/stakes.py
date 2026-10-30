"""Preferences, personal stakes and alignment diagnostics — reported at group level only, never decisive.

Principles (decision_rules.yaml → stakes):
- Every cross-tab respects `min_cell_n`; small groups are pooled into "other groups" and, where that would
  allow a small group to be calculated by difference, the all-respondent total is suppressed as well.
- Status-quo stakes and change stakes are reported symmetrically, side by side.
- Stakes never weight or discount anyone's answers; findings are framed as change-management inputs.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats

STAKE_VALUES = {"Reduces it": -1, "No real change": 0, "Increases it": 1,                      # S04
                "Makes it harder": -1, "No real effect": 0, "Helps": 1}                          # S05
CONCERN = {"Not at all": 0, "A little": 1, "Moderately": 2, "Very much": 3}
NO_DIRECTION = {"No preference", "I don't know enough to have a view"}
LEADERSHIP, DELIVERY = ("TEC", "EXE"), ("ENG", "OPS")
CHANGE_OUTCOMES = {"targeted_extraction", "broad_decomposition", "realign_services", "consolidate",
                   "move_to_cloud", "hybrid", "repatriate"}


@dataclass
class StakesReport:
    preferences: dict = field(default_factory=dict)        # decision -> {group: {outcome: share}, ...}
    preference_vs_evidence: list = field(default_factory=list)
    stake_alignment: list = field(default_factory=list)    # motivated-reasoning diagnostics per group & decision
    stakes_by_option: dict = field(default_factory=dict)   # decision -> {group: {outcome: mean stake}}
    concern: dict = field(default_factory=dict)
    leadership_disagreement: list = field(default_factory=list)
    watermelon: list = field(default_factory=list)
    fit: dict = field(default_factory=dict)
    fit_gaps: list = field(default_factory=list)
    precommitments: dict = field(default_factory=dict)
    suppressed: list = field(default_factory=list)
    findings: list = field(default_factory=list)            # neutral sentences for the report


# ---------------------------------------------------------------------------------------- disclosure control

def reportable_groups(sizes: pd.Series, min_n: int) -> tuple[list[str], list[str], bool]:
    """(groups shown individually, groups pooled into 'other groups', whether the overall total may be shown)."""
    shown = [g for g, n in sizes.items() if n >= min_n]
    small = [g for g, n in sizes.items() if 0 < n < min_n]
    pooled_n = int(sizes[small].sum()) if small else 0
    pooled = small if pooled_n >= min_n else []
    # if small groups can neither be shown nor pooled, the total would reveal them by difference
    total_ok = not small or pooled_n >= min_n
    return shown, pooled, total_ok


def level(label: str) -> str | None:
    if not label:
        return None
    return "Individual contributors" if label == "Individual contributor" else "Managers and above"


# ---------------------------------------------------------------------------------------- analysis

def analyse(eng, evidence, results: dict) -> StakesReport:
    ins, rules = eng.instrument, eng.instrument.rules
    cfg = rules.get("stakes", {})
    min_n = cfg.get("min_cell_n", 5)
    gap_from = cfg.get("report_stake_gap_from", 0.3)
    ans = eng.answers
    people = eng.respondents.set_index("respondent_id") if len(eng.respondents) else pd.DataFrame()
    rep = StakesReport()
    rng = np.random.default_rng(rules.get("statistics", {}).get("seed", 42))
    if people.empty:
        return rep

    seniority = ans[(ans["item_id"] == "CX01") & ans["row"].isna()].set_index("respondent_id")["label"]
    people = people.assign(level=seniority.reindex(people.index).map(level))
    sizes = people["role"].value_counts()
    shown, pooled, total_ok = reportable_groups(sizes, min_n)
    if set(sizes.index) - set(shown) - set(pooled):
        rep.suppressed.append("Groups below the minimum size are not reported"
                              + ("" if total_ok else "; the all-respondent total is withheld to protect them") + ".")

    def group_of(role: str) -> str | None:
        return role if role in shown else ("Other groups" if role in pooled else None)

    people["group"] = people["role"].map(group_of)

    for decision, item, stake_items in (("architecture", "S01", ("S04", "S05")), ("hosting", "S02", ("S04", "S05"))):
        if decision not in results:
            continue
        state = evidence.current_state[decision]
        options = dict((label, oid) for oid, label in ins.preference_options(decision, state))
        pref = ans[(ans["item_id"] == item) & ans["row"].isna()].set_index("respondent_id")["label"]
        pref = pref.reindex(people.index)
        chosen = pref.map(options)                       # outcome id, NaN for no direction / no answer
        people[f"pref_{decision}"] = chosen

        # ---- preference distribution per group (and by level, collapsed for anonymity)
        dist = {}
        for g, sub in people.groupby("group"):
            answered = pref.loc[sub.index].dropna()
            if len(answered) >= min_n:
                dist[g] = _shares(answered.map(lambda l: options.get(l, "no_direction")))
        if total_ok:
            answered = pref.dropna()
            if len(answered) >= min_n:
                dist["All respondents"] = _shares(answered.map(lambda l: options.get(l, "no_direction")))
        by_level = {}
        for lv, sub in people.groupby("level"):
            answered = pref.loc[sub.index].dropna()
            if len(answered) >= min_n:
                by_level[lv] = _shares(answered.map(lambda l: options.get(l, "no_direction")))
        rep.preferences[decision] = {"by_group": dist, "by_level": by_level,
                                     "labels": {oid: label for label, oid in options.items()}}

        # ---- preference vs evidence
        verdict = results[decision].verdict
        evidence_path = verdict if verdict != "insufficient_evidence" else results[decision].leaning
        for g, shares in dist.items():
            if not evidence_path or g == "All respondents":
                continue
            directed = {o: s for o, s in shares.items() if o != "no_direction"}
            if not directed:
                continue
            top, top_share = max(directed.items(), key=lambda kv: kv[1])
            rep.preference_vs_evidence.append({
                "decision": decision, "group": g, "most_preferred": top, "share": round(top_share, 2),
                "evidence_path": evidence_path, "share_preferring_evidence_path": round(shares.get(evidence_path, 0.0), 2),
                "differs": top != evidence_path})

        # ---- stakes per option and motivated-reasoning diagnostic
        stake_rows = ans[ans["item_id"].isin(stake_items) & ans["row"].notna()].copy()
        stake_rows["value"] = stake_rows["label"].map(STAKE_VALUES)
        stake_rows["outcome"] = stake_rows["row"].map(options)
        stake_rows = stake_rows.dropna(subset=["value", "outcome"])
        per_option = stake_rows.groupby(["respondent_id", "outcome"])["value"].mean().unstack()
        by_option = {}
        for g, sub in people.groupby("group"):
            rows = per_option.reindex(sub.index).dropna(how="all")
            if len(rows) >= min_n:
                by_option[g] = {o: round(float(v), 2) for o, v in rows.mean().items() if not np.isnan(v)}
        rep.stakes_by_option[decision] = by_option

        for g, sub in people.groupby("group"):
            pairs = []
            for rid in sub.index:
                p = people.at[rid, f"pref_{decision}"]
                if pd.isna(p) or rid not in per_option.index:
                    continue
                for o, v in per_option.loc[rid].dropna().items():
                    pairs.append((rid, float(o == p), v, o))
            respondents = {r for r, _, _, _ in pairs}
            if len(respondents) < min_n:
                continue
            frame = pd.DataFrame(pairs, columns=["rid", "preferred", "stake", "option"])
            gap_value, p_value = stake_gap_test(frame, rng)
            prefers_change = people.loc[list(respondents), f"pref_{decision}"].isin(CHANGE_OUTCOMES).mean()
            rep.stake_alignment.append({
                "decision": decision, "group": g, "respondents": len(respondents),
                "stake_gap": round(gap_value, 2), "p": round(p_value, 3),
                "share_preferring_change": round(float(prefers_change), 2),
                # preferences that track one's own benefit; preferring what costs you is not motivated reasoning
                "notable": bool(gap_value >= gap_from and p_value < 0.05)})

    # ---- multiple testing: Benjamini–Hochberg across the groups tested for each decision
    for decision in {a["decision"] for a in rep.stake_alignment}:
        family = [a for a in rep.stake_alignment if a["decision"] == decision]
        qs = stats.false_discovery_control([a["p"] for a in family])
        for a, q in zip(family, qs):
            a["q"] = round(float(q), 3)
            a["notable"] = bool(a["stake_gap"] >= gap_from and q < 0.05)

    # ---- concern (self and projective)
    for item, key in (("S06", "self"), ("S06P", "projective")):
        lab = ans[(ans["item_id"] == item) & ans["row"].isna()].set_index("respondent_id")["label"].map(CONCERN)
        for g, sub in people.groupby("group"):
            values = lab.reindex(sub.index).dropna()
            if len(values) >= min_n:
                rep.concern.setdefault(g, {})[key] = round(float((values >= 2).mean()), 2)   # moderately or very

    # ---- within-leadership disagreement and the "watermelon" pattern
    groups_present = set(people["group"].dropna())
    if all(g in groups_present for g in LEADERSHIP):
        for decision in rep.preferences:
            d = rep.preferences[decision]["by_group"]
            if all(g in d for g in LEADERSHIP):
                keys = set(d["TEC"]) | set(d["EXE"])
                tvd = 0.5 * sum(abs(d["TEC"].get(k, 0) - d["EXE"].get(k, 0)) for k in keys)
                if tvd >= 0.4:
                    rep.leadership_disagreement.append({"decision": decision, "distance": round(tvd, 2),
                                                        "TEC": d["TEC"], "EXE": d["EXE"]})
    ig = evidence.item_groups
    if ig is not None and len(ig):
        for item in ("AA01", "AA02", "AA03", "G16", "G04"):
            sub = ig[(ig["item_id"] == item) & (ig["n"] >= min_n)].dropna(subset=["mean"])
            lead = sub[sub["role"].isin(LEADERSHIP)]["mean"]
            deliv = sub[sub["role"].isin(DELIVERY)]["mean"]
            if len(lead) and len(deliv) and lead.mean() - deliv.mean() >= 1.0:
                rep.watermelon.append({"item": item, "text": ins.items.at[item, "text"].replace("{system}", eng.system),
                                       "leadership": round(float(lead.mean()), 2), "delivery": round(float(deliv.mean()), 2)})

    # ---- operating-model fit per outcome, and cross-group gaps on fit items
    rep.fit = fit_profile(rules, evidence)
    if ig is not None and len(ig):
        fit_items = ins.items.index[ins.items["block"].isin(["fit", "requirement"])]
        for item in fit_items:
            sub = ig[(ig["item_id"] == item) & (ig["n"] >= min_n)].dropna(subset=["mean"])
            if len(sub) >= 2 and sub["mean"].max() - sub["mean"].min() >= 1.0:
                hi, lo = sub.loc[sub["mean"].idxmax()], sub.loc[sub["mean"].idxmin()]
                rep.fit_gaps.append({"item": item, "area": ins.items.at[item, "area"],
                                     "high": (hi["role"], round(float(hi["mean"]), 2)),
                                     "low": (lo["role"], round(float(lo["mean"]), 2))})

    # ---- pre-commitments (S08), grouped, for comparison with the evidence after results
    texts = ans[(ans["item_id"] == "S08") & ans["label"].astype(bool)]
    for rid, label in texts.set_index("respondent_id")["label"].items():
        g = people.at[rid, "group"] if rid in people.index else None
        if g:
            rep.precommitments.setdefault(g, []).append(label)
    rep.precommitments = {g: v for g, v in rep.precommitments.items() if len(v) >= min_n}

    rep.findings = _findings(rep, ins)
    return rep


def stake_gap_test(frame: pd.DataFrame, rng, permutations: int = 4000) -> tuple[float, float]:
    """Within-respondent test of whether people prefer the option that benefits them.

    Statistic: mean over respondents of (stake in the preferred option − mean stake in their other options).
    Null: the preferred option is unrelated to one's own stake, i.e. a random pick among the options each person
    rated. Works when a whole group shares one preference; random answers average out to zero.
    Returns (gap, one-sided p-value).
    """
    groups = [g for _, g in frame.groupby("rid") if len(g) >= 2 and g["preferred"].any()]
    if not groups:
        return np.nan, 1.0
    k = max(len(g) for g in groups)
    diffs = np.full((len(groups), k), np.nan)        # d_i(j) = stake_j − mean of the respondent's other stakes
    chosen = np.zeros(len(groups), dtype=int)
    sizes = np.zeros(len(groups), dtype=int)
    for i, g in enumerate(groups):
        v = g["stake"].to_numpy(float)
        n = len(v)
        diffs[i, :n] = v - (v.sum() - v) / (n - 1)
        chosen[i] = int(np.argmax(g["preferred"].to_numpy()))
        sizes[i] = n
    observed = float(np.nanmean(diffs[np.arange(len(groups)), chosen]))
    picks = (rng.random((permutations, len(groups))) * sizes).astype(int)
    null = np.take_along_axis(np.broadcast_to(diffs, (permutations, *diffs.shape)), picks[..., None], axis=2)[..., 0]
    null_means = null.mean(axis=1)
    return observed, float((1 + (null_means >= observed - 1e-12).sum()) / (1 + permutations))


def _shares(series: pd.Series) -> dict[str, float]:
    return {k: round(float(v), 2) for k, v in series.value_counts(normalize=True).items()}


def fit_profile(rules: dict, evidence) -> dict:
    """For each outcome: the fit and requirement conditions it sets, the current value and whether it is met."""
    point = evidence.at(0)
    out = {}
    for decision, spec in rules.get("decisions", {}).items():
        for o in spec["outcomes"]:
            conds = []
            for c in _leaves(o.get("requires_capability", [])) + _leaves(o.get("when")):
                if c.get("signal", "").split(".")[0] in ("fit", "requirement"):
                    value = point.get(c["signal"])
                    met = None if value is None else bool({">=": value >= c["value"], ">": value > c["value"],
                                                          "<": value < c["value"], "<=": value <= c["value"]}[c["op"]])
                    conds.append({"signal": c["signal"], "op": c["op"], "threshold": c["value"],
                                  "current": None if value is None else round(value, 2), "met": met})
            if conds:
                out[f"{decision}.{o['id']}"] = conds
    return out


def _leaves(node) -> list[dict]:
    if node is None:
        return []
    if isinstance(node, list):
        return [leaf for n in node for leaf in _leaves(n)]
    if "signal" in node:
        return [node]
    return [leaf for k in ("all", "any", "not") if k in node for leaf in _leaves(node[k])]


def _findings(rep: StakesReport, ins) -> list[str]:
    """Neutral, descriptive sentences — inputs for change management, not judgements of motive."""
    label = {d: {**{o: s.get("label", o) for o, s in ins.outcomes[d].items()}} for d in ("architecture", "hosting")}
    out = []
    for p in rep.preference_vs_evidence:
        if p["differs"] and p["share"] >= 0.5:          # only clear majorities become written findings
            out.append(f"{p['group']}: the most preferred {p['decision']} direction "
                       f"(“{label[p['decision']].get(p['most_preferred'], p['most_preferred'])}”, {p['share']:.0%}) "
                       f"differs from the path the evidence supports; {p['share_preferring_evidence_path']:.0%} prefer that path.")
    for a in rep.stake_alignment:
        if a["notable"]:
            direction = "towards change" if a["share_preferring_change"] >= 0.5 else "towards the current setup"
            out.append(f"{a['group']} ({a['decision']}): preferences, which lean {direction}, track the expected effect "
                       f"on respondents' own roles and skills (the preferred option is rated {a['stake_gap']:+.2f} better for "
                       f"them than the alternatives). Plans should address how each option affects this group.")
    for w in rep.watermelon:
        out.append(f"Leadership rates “{w['text']}” at {w['leadership']:.1f}, engineering and operations at "
                   f"{w['delivery']:.1f}: a gap worth discussing before any commitment.")
    for d in rep.leadership_disagreement:
        out.append(f"Technology and business leadership differ markedly in their preferred {d['decision']} direction; "
                   f"align the leadership team before communicating a decision.")
    for g, c in rep.concern.items():
        if c.get("self", 0) >= 0.4:
            out.append(f"{g}: {c['self']:.0%} report moderate or strong concern about effects on their role; "
                       f"a role plan should accompany any change.")
    for gap in rep.fit_gaps:
        out.append(f"Groups describe current practice differently ({gap['area'].replace('_', ' ')}: {gap['high'][0]} "
                   f"{gap['high'][1]:.1f} vs {gap['low'][0]} {gap['low'][1]:.1f}).")
    return out
