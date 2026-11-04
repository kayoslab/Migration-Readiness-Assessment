"""Voices not heard on their own: groups too small to stand alone, and how far they lean from everyone else.

A group with fewer than `min_role_n` respondents is counted only inside a pool, or not at all (mra/groups.py), so
the report cannot show its own figures. This module says which groups that affects and, in words only, whether such
a group leans a different way from the other respondents on each decision. Two measures per decision:
- direction: the share preferring a change (rather than keeping or improving the current setup), against the rest;
- need: how strongly it sees a need for change (need items), against the rest.

Disclosure (decision_rules.yaml → evidence.unheard): nothing is described for a group under `describe_from_n`;
above it, only bands ("in line", "leans differently", "points the other way") are shown, never figures. A group
with no respondents at all is listed when the decision depends on it (integrity.yaml → critical_groups).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .stakes import CHANGE_OUTCOMES

LEVELS = ("in line with the rest", "leans differently", "points the other way")
DEFAULTS = {"describe_from_n": 3, "direction_bands": [0.2, 0.4], "need_bands": [0.5, 1.0]}
PREFERENCE_ITEMS = {"architecture": "S01", "hosting": "S02"}


def _band(value: float, cuts: list[float]) -> int:
    return int(sum(abs(value) >= c for c in cuts))


def _wants_change(eng, decision: str, state: str) -> pd.Series:
    """Per respondent: 1 prefers a change, 0 prefers keeping or improving the current setup, NaN no direction."""
    ins, ans = eng.instrument, eng.answers
    single = ans[ans["row"].isna()]
    options = dict((label, oid) for oid, label in ins.preference_options(decision, state))
    pref = single[single["item_id"] == PREFERENCE_ITEMS[decision]].set_index("respondent_id")["label"]
    out = pref.map(lambda label: float(options[label] in CHANGE_OUTCOMES) if label in options else np.nan)
    business = single[single["item_id"] == "BP01"].set_index("respondent_id")["label"].fillna("")   # stable vs change
    business = business.map(lambda l: 0.0 if l.startswith("Keeping") else 1.0 if l.startswith("Accepting") else np.nan)
    return pd.concat([out, business[~business.index.isin(out.index)]]).astype(float)


def build(assessment) -> dict:
    eng = assessment.engagement
    ins, rules = eng.instrument, eng.instrument.rules
    ev = rules.get("evidence", {}) or {}
    cfg = {**DEFAULTS, **(ev.get("unheard") or {})}
    min_n = ev.get("min_role_n", 5)
    from .groups import for_engagement
    from .integrity import GROUP_NAMES, load_config
    people = eng.respondents.set_index("respondent_id") if len(eng.respondents) else pd.DataFrame(columns=["role"])
    groups = for_engagement(eng) if len(people) else pd.Series(dtype=object)
    sizes = people["role"].value_counts()
    critical = (load_config(ins.root).get("critical_groups") or {}).get("groups", {})
    decisions = [d for d in ("architecture", "hosting") if d in assessment.results]
    needed = {g for d in decisions for g in critical.get(d, [])}

    from .axes import respondent_scores
    scores = respondent_scores(eng) if len(people) else pd.DataFrame()
    wants = {d: _wants_change(eng, d, assessment.evidence.current_state[d]) for d in decisions}

    rows = []
    for role in [r for r in GROUP_NAMES if 0 < sizes.get(r, 0) < min_n or (r in needed and sizes.get(r, 0) == 0)]:
        n = int(sizes.get(role, 0))
        mine = list(people.index[people["role"] == role])
        rest = list(people.index[people["role"] != role])
        label = groups.get(mine[0]) if mine else None
        label = label if isinstance(label, str) else None
        counted = "No respondents" if n == 0 else f"Counted only within “{label}”" if label else "Not counted"
        row = {"group": GROUP_NAMES[role], "role": role, "n": n, "counted": counted, "described": False,
               "decisions": [], "critical": sorted(d for d in decisions if role in critical.get(d, []))}
        if n >= cfg["describe_from_n"]:
            row["described"] = True
            for d in decisions:
                row["decisions"].append(_compare(ins, scores, wants[d], mine, rest, d, cfg, min_n,
                                                 assessment.results[d]))
        rows.append(row)
    return {"rows": rows, "describe_from_n": cfg["describe_from_n"], "min_n": min_n,
            "findings": [f for r in rows for f in _finding(r)]}


def _compare(ins, scores, wants, mine, rest, decision, cfg, min_n, result) -> dict:
    out = {"decision": decision, "level": 0, "text": LEVELS[0], "against_path": False}
    small_n = cfg["describe_from_n"]
    a, b = wants.reindex(mine).dropna(), wants.reindex(rest).dropna()
    measures = []
    if len(a) >= small_n and len(b) >= min_n:
        gap = float(a.mean() - b.mean())
        measures.append((_band(gap, cfg["direction_bands"]), gap,
                         "prefers a change more often than the rest" if gap > 0 else
                         "prefers keeping or improving the current setup more often than the rest"))
    need = [i for i in scores.columns if ins.items.at[i, "block"] == "need"
            and ins.items.at[i, "decision"] in (decision, "both")]
    diffs = []
    for item in need:
        x, y = scores.reindex(mine)[item].dropna(), scores.reindex(rest)[item].dropna()
        if len(x) >= small_n and len(y) >= min_n:
            diffs.append(float(x.mean() - y.mean()))
    if diffs:
        diff = float(np.mean(diffs))
        measures.append((_band(diff, cfg["need_bands"]), diff,
                         "sees more need for change than the rest" if diff > 0 else
                         "sees less need for change than the rest"))
    if not measures:
        return {**out, "text": "too few answers to compare"}
    level, sign, words = max(measures, key=lambda m: (m[0], abs(m[1])))
    path = result.verdict if result.verdict != "insufficient_evidence" else result.leaning
    if level and path:
        out["against_path"] = (path in CHANGE_OUTCOMES) != (sign > 0)
    out.update(level=level, text=LEVELS[level] if not level else f"{LEVELS[level]}: {words}")
    return out


def _finding(row: dict) -> list[str]:
    """A written finding where a group not heard on its own points the other way from the rest."""
    strong = [d for d in row["decisions"] if d["level"] == 2]
    if not strong:
        return []
    who = f"{row['group']} ({row['n']} respondents)"
    where = "counted only together with other groups" if row["counted"].startswith("Counted") else "not counted"
    parts = "; ".join(f"on {d['decision']} it {d['text'].split(': ', 1)[1]}" +
                      (", against the recommended path" if d["against_path"] else "") for d in strong)
    return [f"{who} is too small to be shown on its own and is {where}, but its answers point the other way: "
            f"{parts}. Hear this group directly before the decision is final."]
