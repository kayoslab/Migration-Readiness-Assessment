"""Reporting groups: who is counted and shown together when a stakeholder group is too small to stand alone.

Groups with at least `min_role_n` respondents stand alone. Smaller groups are pooled only with groups whose stakes
point the same way (pre-registered in decision_rules.yaml, `evidence.pools`): technology leadership with the senior
engineers and operations people, business leadership with finance and risk. Security is never pooled with
Operations, nor business leadership with technology leadership. Remaining small delivery groups form "Other groups".
A pool that still has fewer than `min_role_n` respondents is not reported and does not count.
"""

from __future__ import annotations

import pandas as pd

OTHER = "Other groups"
SENIOR = ("Head of / director", "Executive")
DEFAULT_POOLS = [{"name": "Technology leadership (pooled)", "members": ["TEC"], "senior_from": ["ENG", "OPS"]},
                 {"name": "Business leadership and control (pooled)", "members": ["EXE", "FIN", "SEC"]}]
DEFAULT_OTHER = ["ENG", "PRD", "BUS", "OPS"]


def assign(roles: pd.Series, seniority: pd.Series, rules: dict, min_n: int | None = None) -> pd.Series:
    """Reporting group per respondent (index: respondent id); None where the respondent cannot be reported."""
    ev = rules.get("evidence", {}) or {}
    min_n = min_n or ev.get("min_role_n", 5)
    pools = ev.get("pools", DEFAULT_POOLS)
    other = set(ev.get("other_groups", DEFAULT_OTHER))
    seniority = seniority.reindex(roles.index)
    sizes = roles.value_counts()
    group = roles.where(roles.map(sizes) >= min_n, None).astype(object)
    moved: dict[str, int] = {}
    for pool in pools:
        small = [m for m in pool["members"] if 0 < sizes.get(m, 0) < min_n]
        if not small:
            continue
        members = list(roles.index[roles.isin(small)])
        for home in pool.get("senior_from", []):      # senior people join only if their own group still stands
            seniors = list(roles.index[(roles == home) & seniority.isin(SENIOR)])
            left = sizes.get(home, 0) - moved.get(home, 0) - len(seniors)
            if seniors and (left >= min_n or sizes.get(home, 0) < min_n):
                members += seniors
                moved[home] = moved.get(home, 0) + len(seniors)
        if len(members) >= min_n:
            group.loc[members] = pool["name"]
    rest = roles.index[group.isna() & roles.isin(other)]
    if len(rest) >= min_n:
        group.loc[rest] = OTHER
    return group


def for_engagement(eng, min_n: int | None = None) -> pd.Series:
    """Reporting group per respondent of an engagement (seniority from CX01)."""
    people = eng.respondents.set_index("respondent_id") if len(eng.respondents) else pd.DataFrame(columns=["role"])
    ans = eng.answers
    seniority = ans[(ans["item_id"] == "CX01") & ans["row"].isna()].set_index("respondent_id")["label"] \
        if len(ans) else pd.Series(dtype=object)
    return assign(people["role"], seniority, eng.instrument.rules, min_n)


def group_of_role(groups: pd.Series, roles: pd.Series, role: str) -> str | None:
    """The reporting group most of a role's respondents are counted in (None if they are not reported)."""
    labels = groups[roles == role].dropna()
    return labels.mode().iloc[0] if len(labels) else None


def describe(groups: pd.Series, roles: pd.Series, names: dict) -> list[str]:
    """Plain sentences on how small groups were combined, for the report."""
    out = []
    for label in [g for g in dict.fromkeys(groups.dropna()) if g not in set(roles)]:
        parts = roles[groups == label].value_counts()
        listed = [f"{names.get(r, r)} ({n})" for r, n in parts.items()]
        listed = listed[0] if len(listed) == 1 else ", ".join(listed[:-1]) + " and " + listed[-1]
        out.append(f"{listed} are counted and shown together as “{label}”.")
    dropped = roles[groups.isna()].value_counts()
    if len(dropped):
        listed = [f"{names.get(r, r)} ({n})" for r, n in dropped.items()]
        listed = listed[0] if len(listed) == 1 else ", ".join(listed[:-1]) + " and " + listed[-1]
        out.append(f"{listed} {'is' if len(dropped) == 1 else 'are'} too few to report even when combined; "
                   "these answers are not shown and do not count.")
    return out
