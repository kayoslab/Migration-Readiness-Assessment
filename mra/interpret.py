"""Interpretation of every exhibit: an action title stating the insight, and the observations behind it.

The interpretation is computed from the data the exhibit shows, so it is always present and always consistent with
the chart. With --llm, a language model turns each exhibit's data and observations into a short "so what" in
advisory register; its sentences pass the same checks as the narrative, and the computed text is the fallback.
"""

from __future__ import annotations

import numpy as np


def _pct(x: float) -> str:
    return f"{x:.0%}"


def _quote(text: str) -> str:
    """A statement in quotes, closed with a full stop unless it already ends a sentence."""
    return f"“{text}”" + ("" if text.rstrip().endswith(("?", "!", ".")) else ".")


def _short(label: str) -> str:
    return label.split(",")[0].split(" (")[0]


def outcome_probabilities(dist: dict, labels: dict, verdict: str, leaning: str | None, confidence: float,
                          status: str, unresolved: float) -> dict:
    items = sorted(((k, v) for k, v in dist.items() if k not in ("unresolved",)), key=lambda kv: -kv[1])
    lead, p = items[0] if items else (None, 0.0)
    name = labels.get(lead, lead)
    if p >= confidence:
        title = f"“{name}” applies in {_pct(p)} of draws — above the {_pct(confidence)} required"
    else:
        title = f"No path reaches the {_pct(confidence)} required; the most likely, “{name}”, applies in {_pct(p)}"
    points = []
    if len(items) > 1 and items[1][1] >= 0.05:
        points.append(f"The nearest alternative, “{labels.get(items[1][0], items[1][0])}”, applies in "
                      f"{_pct(items[1][1])} of draws.")
    else:
        points.append("No alternative path applies in a meaningful share of draws: the result is robust to sampling.")
    if unresolved >= 0.05:
        points.append(f"In {_pct(unresolved)} of draws a required input is missing, which counts against any verdict.")
    if status == "prepare_first":
        points.append("The path is supported, but preconditions are not yet in place (see the preconditions chapter).")
    return {"title": title, "points": points}


def need_capability(need: np.ndarray, capability: np.ndarray, cuts=(2.5, 3.5), cap_cut: float = 3.5) -> dict:
    n0, c0 = float(need[0]), float(capability[0])
    n_lo, n_hi = np.nanpercentile(need, [5, 95])
    region = ("keep and improve practices" if n0 < cuts[0] else
              "restructure within the system" if n0 < cuts[1] or c0 < cap_cut else "decomposition possible")
    strength = "low" if n0 < cuts[0] else "moderate" if n0 < cuts[1] else "high"
    cap_word = "strong" if c0 >= cap_cut else "adequate" if c0 >= 3.0 else "weak"
    title = (f"Need for change is {strength} ({n0:.1f}), and the delivery capabilities a larger change relies on are "
             f"{cap_word} (weakest {c0:.1f}): {region}")
    points = []
    crossed = [c for c in cuts if n_lo < c < n_hi]
    if crossed:
        points.append(f"The need estimate ranges from {n_lo:.1f} to {n_hi:.1f} across draws and crosses the threshold "
                      f"of {crossed[0]}: the position is not settled.")
    else:
        nearest = min(cuts, key=lambda c: abs(c - n0))
        points.append(f"Across draws the need estimate stays between {n_lo:.1f} and {n_hi:.1f}, clear of the threshold "
                      f"of {nearest} ({abs(nearest - n0):.2f} away at the point estimate).")
    if n0 >= cuts[0] and c0 >= cap_cut and n0 < cuts[1]:
        points.append(f"Capability would allow more, but the need is below the {cuts[1]} at which a broad split "
                      "is warranted: the constraint is the size of the problem, not the ability to change.")
    elif n0 >= cuts[1] and c0 < cap_cut:
        points.append("The need would justify a broader split, but capability is the binding constraint.")
    return {"title": title, "points": points}


def tco(ranges: dict[str, tuple[float, float, float]], words: dict, payback: dict) -> dict:
    order = sorted(ranges, key=lambda o: ranges[o][1])
    best, worst = order[0], order[-1]
    b, w = ranges[best], ranges[worst]
    if b[1] < 1:
        title = (f"{words.get(best, best)} is the cheapest option at {b[1]:.2f} of today's cost; "
                 f"{words.get(worst, worst).lower()} would cost {w[1]:.2f}×")
    else:
        title = f"No option is cheaper than today's setup; the closest, {words.get(best, best).lower()}, costs {b[1]:.2f}×"
    points = []
    straddle = [o for o in order if ranges[o][0] < 1.0 < ranges[o][2]]
    if straddle:
        points.append("The cost range of " + ", ".join(words.get(o, o).lower() for o in straddle)
                      + " includes the cost of today's setup: on cost alone the case is not settled.")
    else:
        points.append("No option's 90% range crosses today's cost: each is clearly cheaper or clearly dearer.")
    if payback.get(best):
        points.append(f"{words.get(best, best)} recovers its one-off costs {int(payback[best])} months after cut-over.")
    return {"title": title, "points": points}


def tornado(rows: list[dict], label_for, option_word: str) -> dict:
    base = rows[0]["base"]
    drivers = rows[1:]
    if not drivers:
        return {"title": "The cost case does not depend on any single uncertain input", "points": []}
    top = drivers[0]
    lo, hi = sorted((top["low"], top["high"]))
    # the decision rules compare a move with an IMPROVED current setup, so this ratio has that base, not today's
    title = (f"For {option_word.lower()}, the {_short(label_for(top['input'])).lower()} moves the cost comparison most "
             f"({lo:.2f}–{hi:.2f}× the cost of an improved current setup)")
    flips = [r for r in drivers if min(r["low"], r["high"]) < 1.0 < max(r["low"], r["high"])]
    points = [f"With every input at its likely value, {option_word.lower()} costs {base:.2f}× an improved current "
              "setup."]
    if flips:
        points.append(f"Only the {_short(label_for(flips[0]['input'])).lower()} could make it cheaper than improving at "
                      "the end of its range; firming up that estimate matters most.")
    else:
        points.append("No single input, at the end of its range, makes it cheaper than improving the current setup: "
                      "the conclusion is robust to the estimates.")
    return {"title": title, "points": points}


def readiness_matrix(matrix, counts, min_n: int) -> dict:
    shown = matrix.where(counts >= min_n)
    flat = shown.stack()
    if flat.empty:
        return {"title": "Too few respondents per group to compare readiness", "points": []}
    (low_area, low_group), low_v = flat.idxmin(), flat.min()
    spread = (shown.max(axis=1) - shown.min(axis=1)).dropna()
    area_means = shown.mean(axis=1).dropna().sort_values()
    title = (f"{area_means.index[0].split(': ', 1)[-1].capitalize()} is the weakest area ({area_means.iloc[0]:.1f}); "
             f"groups differ most on {spread.idxmax().split(': ', 1)[-1]}")
    points = [f"The lowest single rating is {low_group}'s {low_v:.1f} for {low_area.split(': ', 1)[-1]}.",
              f"On {spread.idxmax().split(': ', 1)[-1]}, ratings range over {spread.max():.1f} points between groups."]
    strong = area_means[area_means >= 4.0]
    if len(strong):
        points.append(f"The strongest area is {strong.index[-1].split(': ', 1)[-1]} ({strong.iloc[-1]:.1f}).")
    return {"title": title, "points": points}


def weakest(items: list[dict]) -> dict:
    if not items:
        return {"title": "", "points": []}
    top = items[0]
    title = f"The lowest-rated statement scores {top['score']:.1f}, with {_pct(top['low'])} of answers in the low range"
    polarised = [i for i in items if i["low"] >= 0.25 and i["high"] >= 0.25]
    points = [f"Lowest: {_quote(top['text'])}"]
    if polarised:
        points.append(f"Answers are split on “{polarised[0]['text']}” ({_pct(polarised[0]['low'])} low, "
                      f"{_pct(polarised[0]['high'])} high): respondents experience it differently, which is worth "
                      "clarifying before acting on it.")
    return {"title": title, "points": points}


def divergence(rows: list[dict]) -> dict:
    if not rows:
        return {"title": "", "points": []}
    top = max(rows, key=lambda r: abs(r["survey"] - r["fact"]))
    direction = "more favourably" if top["survey"] > top["fact"] else "less favourably"
    title = f"Respondents rate {top['label'].lower()} {direction} than the measurement suggests ({top['survey']:.1f} vs {top['fact']:.1f})"
    over = [r for r in rows if r["survey"] > r["fact"]]
    points = [f"In {len(over)} of {len(rows)} diverging areas perception is more favourable than measurement."
              if over else "Perception is less favourable than measurement in every diverging area."]
    return {"title": title, "points": points}


def preferences(by_group: dict, labels: dict, verdict: str | None) -> dict:
    from .stakes import top_choice
    tops = {g: top_choice(s) for g, s in by_group.items() if g != "All respondents"}
    tops = {g: t for g, t in tops.items() if t[2]}
    agree = [g for g, (o, _, _) in tops.items() if o == verdict]
    tied = [g for g, (o, _, leaders) in tops.items() if o is None and verdict in leaders]
    if verdict:
        title = f"{len(agree)} of {len(tops)} groups most prefer the path the evidence supports"
        if tied:
            title += f"; {len(tied)} {'is' if len(tied) == 1 else 'are'} split evenly between it and another"
    else:
        title = "Preferred directions by group"
    points = []
    overall = by_group.get("All respondents") or {}
    if verdict and overall:
        rival = max(((o, v) for o, v in overall.items() if o not in (verdict, "no_direction")), key=lambda kv: kv[1],
                    default=None)
        text = f"Across all respondents, {_pct(overall.get(verdict, 0))} prefer it"
        if rival and rival[1] >= overall.get(verdict, 0):
            text += f" and {_pct(rival[1])} prefer “{labels.get(rival[0], rival[0])}”"
        points.append(text + ".")
    split = [g for g, (o, v, _) in tops.items() if o and v >= 0.6 and o != verdict]
    if split:
        g = split[0]
        points.append(f"{g} clearly prefers “{labels.get(tops[g][0], tops[g][0])}” ({_pct(tops[g][1])}).")
    return {"title": title, "points": points}


def stakes(by_group: dict, labels: dict) -> dict:
    cells = [(g, o, v) for g, row in by_group.items() for o, v in row.items()]
    if not cells:
        return {"title": "", "points": []}
    g_lo, o_lo, v_lo = min(cells, key=lambda c: c[2])
    g_hi, o_hi, v_hi = max(cells, key=lambda c: c[2])
    title = (f"{g_lo} expects “{labels.get(o_lo, o_lo)}” to affect their roles most negatively ({v_lo:+.1f}); "
             f"{g_hi} expects most from “{labels.get(o_hi, o_hi)}” ({v_hi:+.1f})")
    return {"title": title, "points": ["These expectations do not affect the recommendation; they indicate where a "
                                       "role plan and targeted communication are needed."]}


def roadmap(rm: dict) -> dict:
    migration = next((b for b in rm["bars"] if b["workstream"] == "Hosting migration"), None)
    now = sum(1 for b in rm["bars"] if b["start"] == 0)
    title = (f"{now} action{'s' if now != 1 else ''} come before any commitment; the first review after three months "
             "decides whether to commit, re-scope or stop")
    points = ["The sequence is indicative: each phase starts only when the review before it has been passed."]
    if migration:
        high = f"–{migration['end_high']:.0f}" if migration["end_high"] else ""
        points.append(f"The hosting migration would end between month {migration['end']:.0f}{high} on the fact sheet's "
                      "estimates.")
    return {"title": title, "points": points}


def stakeholder_map(rows: list[dict]) -> dict:
    engage = [r for r in rows if r["approach"] == "Engage closely"]
    sponsors = [r["group"] for r in rows if r["approach"] == "Involve as sponsors"]
    if len(engage) == 1:
        title = (f"{engage[0]['group']} has high influence, but only {_pct(engage[0]['support'])} of its respondents prefer "
                 "the recommended path: engage before the decision is announced")
    elif engage:
        title = (f"{', '.join(r['group'] for r in engage)} have high influence, but fewer than half of their respondents "
                 "prefer the recommended path: engage before the decision is announced")
    else:
        title = "Every high-influence group mostly supports the recommended path"
    points = []
    if sponsors:
        points.append(f"{', '.join(sponsors)} can act as sponsors of the recommended path.")
    worried = [r["group"] for r in rows if (r["concern"] or 0) >= 0.4]
    if worried:
        points.append(f"Role concern is high in {', '.join(worried)}; address it alongside the communication plan.")
    if any(r["influence_source"] == "default" for r in rows):
        points.append("Influence ratings marked as default are assumptions; agree them with the sponsor.")
    return {"title": title, "points": points}


def benchmark(bm: dict, architecture_verdict: str | None) -> dict:
    rows = [r for r in bm["rows"] if r["score"] is not None]
    if not rows:
        return {"title": "No delivery measures are available to compare with the industry", "points": []}
    seg = "industry" if bm["industry"] == "All industries" else f"{bm['industry']} industry"
    by = {p: [r["label"].lower() for r in rows if r["position"] == p] for p in ("above", "around", "below")}
    if by["below"]:
        title = f"Behind the {seg} average on {_join(by['below'])}"
    elif by["above"] and not by["around"]:
        title = f"Ahead of the {seg} average on every measured delivery measure"
    elif by["above"]:
        title = f"Around the {seg} average on {_join(by['around'])}, and ahead on {_join(by['above'])}"
    else:
        title = f"Around the {seg} average on every measured delivery measure"
    points = []
    throughput_below = any(r["position"] == "below" for r in rows if r["metric"] in ("leadtime", "deployfreq"))
    if architecture_verdict in ("stay_and_improve", None):
        pass
    elif throughput_below:
        points.append("Slower delivery than peers is consistent with the need for change found in the architecture "
                      "assessment.")
    else:
        points.append("Delivery speed is not where the organisation trails its peers, so the case for change rests on "
                      "the architecture findings rather than on delivery performance; these measures should not fall "
                      "while the change is made.")
    missing = [r["label"].lower() for r in bm["rows"] if r["score"] is None]
    if missing:
        points.append(f"Not measured: {_join(missing)}.")
    return {"title": title, "points": points}


def _join(words: list[str]) -> str:
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


def lead_time(by_group: dict, cross_team_pct: float | None) -> dict:
    overall = by_group.get("All respondents asked") or next(iter(by_group.values()))
    top = max(overall, key=overall.get)
    title = f"Lead time goes mainly to {top[0].lower() + top[1:]} ({_pct(overall[top])} of answers)"
    if top != "Waiting on process":
        title += f"; {_pct(overall.get('Waiting on process', 0))} name waiting on approvals, testing or environments"
    groups = [g for g in by_group if g != "All respondents asked"]
    same = [g for g in groups if max(by_group[g], key=by_group[g].get) == top]
    points = []
    if len(same) == len(groups) > 1:
        points.append(f"Every group asked gives the same answer ({', '.join(groups)}).")
    if cross_team_pct is not None:
        points.append(f"{cross_team_pct:g}% of merged changes touch code owned by more than one team.")
    return {"title": title, "points": points}


def sourcing(parts: list[dict]) -> dict:
    decided = [p for p in parts if p.get("differentiation") is not None]
    replace = [p["name"] for p in decided if p["verdict"] == "replace_with_product"]
    keep = [p["name"] for p in decided if p["verdict"] == "keep_building"]
    if replace and keep:
        title = f"Replace {_join_names(replace)} with a product; keep building {_join_names(keep)}"
    elif replace:
        title = f"Every part assessed can be replaced with a product: {_join_names(replace)}"
    elif keep:
        title = f"Keep building every part assessed: {_join_names(keep)}"
    else:
        title = "The evidence does not yet decide whether to build or buy"
    return {"title": title, "points": [f"{p['name']}: {p['verdict'].replace('_', ' ')}." for p in decided]}


def _join_names(names: list[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
