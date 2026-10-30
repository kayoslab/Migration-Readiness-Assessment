"""Organisational readiness by stakeholder group, from the v3 survey (the strongest parts of the v2 report).

- matrix: each group's view of every sub-area where a higher score means more ready (capability, operating-model
  fit, alignment, governance awareness); cells below the minimum group size are marked, not hidden. Need is not
  readiness — it is shown in the decision chapters.
- differences: Kruskal–Wallis across groups per sub-area on person-level scores, ε² and Benjamini–Hochberg q
- weakest: the statements with the lowest group-weighted score, with how answers were distributed
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats

from .explain import signal_label

BLOCKS = ("capability", "fit", "alignment", "governance")          # higher = more ready


@dataclass
class Readiness:
    matrix: pd.DataFrame                     # sub-area label x group → mean (NaN where not asked)
    counts: pd.DataFrame                     # same shape → respondents
    differences: list[dict] = field(default_factory=list)
    weakest: list[dict] = field(default_factory=list)


def _sub_area_name(it) -> str:
    if it["block"] in ("fit", "requirement", "locality"):
        return f"{it['block']}.{it['area']}"
    decision = "architecture" if it["decision"] == "both" else it["decision"]
    return f"{it['block']}.{decision}.{it['area']}"


def analyse(eng, min_n: int = 5) -> Readiness:
    ins = eng.instrument
    items = ins.items[(ins.items["scored"] == "true") & ins.items["block"].isin(BLOCKS)]
    ans = eng.answers[eng.answers["item_id"].isin(items.index) & eng.answers["row"].isna()].dropna(subset=["score"])
    if ans.empty:
        return Readiness(pd.DataFrame(), pd.DataFrame())
    ans = ans.assign(sub=ans["item_id"].map(lambda i: _sub_area_name(items.loc[i])))

    # person-level sub-area scores (mean of the person's answered items in the sub-area)
    person = ans.groupby(["respondent_id", "role", "sub"])["score"].mean().reset_index()
    groups = list(dict.fromkeys(eng.respondents["role"]))
    means = person.groupby(["sub", "role"])["score"].mean().unstack().reindex(columns=groups)
    counts = person.groupby(["sub", "role"])["score"].count().unstack().reindex(columns=groups).fillna(0).astype(int)
    order = sorted(means.index, key=lambda s: (BLOCKS.index(s.split(".")[0]), s))
    means, counts = means.loc[order], counts.loc[order]
    labels = {s: _label(s, ins) for s in order}
    matrix, count_m = means.rename(index=labels), counts.rename(index=labels)

    diffs = []
    for sub in order:
        samples = {g: person[(person["sub"] == sub) & (person["role"] == g)]["score"].to_numpy() for g in groups}
        samples = {g: v for g, v in samples.items() if len(v) >= min_n}
        if len(samples) < 2 or len({x for v in samples.values() for x in v}) < 2:
            continue
        h, p = stats.kruskal(*samples.values())
        n = sum(len(v) for v in samples.values())
        g_means = {g: float(v.mean()) for g, v in samples.items()}
        hi, lo = max(g_means, key=g_means.get), min(g_means, key=g_means.get)
        diffs.append({"sub_area": labels[sub], "groups": len(samples), "epsilon_sq": h / (n - 1), "p": p,
                      "high": (hi, round(g_means[hi], 1)), "low": (lo, round(g_means[lo], 1)),
                      "spread": round(g_means[hi] - g_means[lo], 2)})
    if diffs:
        for d, q in zip(diffs, stats.false_discovery_control([d["p"] for d in diffs])):
            d["q"] = float(q)
            d["effect"] = "large" if d["epsilon_sq"] >= 0.26 else "moderate" if d["epsilon_sq"] >= 0.08 else "small"
            d["significant"] = bool(q < 0.05)
        diffs.sort(key=lambda d: -d["epsilon_sq"])

    weakest = []
    item_group = ans.groupby(["item_id", "role"])["score"].agg(["mean", "count"]).reset_index()
    item_group = item_group[item_group["count"] >= min_n]
    item_score = item_group.groupby("item_id")["mean"].mean().sort_values()
    for item_id, score in item_score.head(10).items():
        s = ans[ans["item_id"] == item_id]["score"]
        weakest.append({"item": item_id, "text": ins.items.at[item_id, "text"].replace("{system}", eng.system),
                        "score": round(float(score), 2), "n": int(len(s)),
                        "low": float((s <= 2).mean()), "mid": float((s == 3).mean()), "high": float((s >= 4).mean())})
    return Readiness(matrix, count_m, diffs, weakest)


AREA = {"shared_view": "shared view of the future", "rationale": "reasons explained", "middle_management":
        "manager protects improvement time", "capacity": "protected capacity", "change_load": "few competing changes",
        "sponsor": "accountable sponsor known"}


def _label(sub: str, ins) -> str:
    parts = sub.split(".")
    head, area = parts[0], parts[-1]
    word = {"capability": "Capability", "fit": "Operating-model fit", "alignment": "Alignment",
            "governance": "Governance"}[head]
    text = AREA.get(area) or signal_label(sub, ins).lower()
    qualifier = " (hosting)" if len(parts) == 3 and parts[1] == "hosting" else ""
    return f"{word}{qualifier}: {text}"
