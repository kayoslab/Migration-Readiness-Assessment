"""Stakeholder map: each group's support for the recommended paths against its influence on the decision.

Support is measured: the share of a group's respondents whose preferred direction is the recommended path (or the
interim step towards it), averaged over the decisions. Influence is not measurable from the survey; it comes from
engagement.yaml (influence: {GROUP: high|medium|low}) and otherwise from a stated default. Groups only, never below
the minimum group size. "Other groups" is left out because its influence is not defined; a pre-registered pool
(mra/groups.py) carries the highest influence among its members. Answers are never
weighted by influence — the map is for planning engagement, not for the verdict.

Off unless engagement.yaml sets report: {stakeholder_map: true}; it is the most sensitive exhibit in the report and
should be discussed with the sponsor first.
"""

from __future__ import annotations

LEVEL = {"low": 1, "medium": 2, "high": 3}
DEFAULT_INFLUENCE = {"EXE": "high", "TEC": "high"}            # everyone else: medium
APPROACH = {  # (high influence, high support)
    (True, True): "Involve as sponsors",
    (True, False): "Engage closely",
    (False, True): "Keep informed and involved",
    (False, False): "Inform and listen",
}
POOLED = ("Other groups", "All respondents")


def stakeholder_map(assessment) -> list[dict]:
    eng, st = assessment.engagement, assessment.stakes
    if not st or not (eng.config.get("report") or {}).get("stakeholder_map"):
        return []
    configured = eng.config.get("influence") or {}
    support: dict[str, list[float]] = {}
    for d, prefs in st.preferences.items():
        r = assessment.results.get(d)
        if not r:
            continue
        backed = {x for x in (r.verdict, r.leaning, r.interim) if x and x != "insufficient_evidence"}
        for g, shares in prefs["by_group"].items():
            if g in POOLED:
                continue
            support.setdefault(g, []).append(sum(v for o, v in shares.items() if o in backed))
    from .groups import DEFAULT_POOLS
    pools = {p["name"]: p["members"] for p in (eng.instrument.rules.get("evidence", {}).get("pools") or DEFAULT_POOLS)}

    def influence(g):                                 # a pool carries the highest influence among its members
        if g in pools:
            return max((configured.get(m) or DEFAULT_INFLUENCE.get(m, "medium") for m in pools[g]), key=LEVEL.get)
        return configured.get(g) or DEFAULT_INFLUENCE.get(g, "medium")

    rows = []
    for g, values in support.items():
        level = influence(g)
        s = sum(values) / len(values)
        high_infl, high_supp = LEVEL[level] >= 3, s >= 0.5
        concern = st.concern.get(g, {}).get("self")
        rows.append({"group": g, "support": round(s, 2), "by_decision": [round(v, 2) for v in values],
                     "influence": level, "influence_source": "agreed" if g in configured else "default",
                     "approach": APPROACH[(high_infl, high_supp)],
                     "concern": round(concern, 2) if concern is not None else None})
    return sorted(rows, key=lambda r: (-LEVEL[r["influence"]], r["support"]))
