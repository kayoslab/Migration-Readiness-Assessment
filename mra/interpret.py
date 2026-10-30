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
    title = f"Need for change is {strength} ({n0:.1f}) and the weakest capability is {cap_word} ({c0:.1f}): {region}"
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
    title = (f"For {option_word.lower()}, the {_short(label_for(top['input'])).lower()} moves the cost case most "
             f"({lo:.2f}–{hi:.2f}× today's cost)")
    flips = [r for r in drivers if min(r["low"], r["high"]) < 1.0 < max(r["low"], r["high"])]
    points = [f"With every input at its likely value, {option_word.lower()} costs {base:.2f}× today's setup."]
    if flips:
        points.append(f"Only the {_short(label_for(flips[0]['input'])).lower()} could bring it below today's cost at the end of its "
                      "range; firming up that estimate matters most.")
    else:
        points.append("No single input, at the end of its range, makes it cheaper than today's setup: the conclusion "
                      "is robust to the estimates.")
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
    tops = {g: max(((o, v) for o, v in s.items() if o != "no_direction"), key=lambda kv: kv[1], default=(None, 0))
            for g, s in by_group.items() if g != "All respondents"}
    agree = [g for g, (o, _) in tops.items() if o == verdict]
    title = (f"{len(agree)} of {len(tops)} groups most prefer the path the evidence supports"
             if verdict else "Preferred directions by group")
    points = []
    split = [g for g, (o, v) in tops.items() if v >= 0.6 and o != verdict]
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
