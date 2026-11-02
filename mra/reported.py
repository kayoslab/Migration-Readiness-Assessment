"""What the groups report: survey items that are shown, never scored — the cost of staying, the cost of changing,
and the context leadership and the business set (horizon, prior commitment, how long the system will be used).

For each item (and grid row) and each reporting group (mra/groups.py) with enough answers, the answer given most
often and its share. Where the item is a perception check for a fact, the fact is shown beside it. "Don't know" and
"not applicable" answers are left out of the shares.
"""

from __future__ import annotations

import re

import pandas as pd

SIDES = {"staying": "The cost of staying as it is", "changing": "The cost of changing",
         "context": "Context set by leadership and the business"}
CONTEXT_ITEMS = ("PC01", "X1", "LF01", "MO02T", "SO02")


def _fact(eng, source: str) -> dict | None:
    m = re.search(r"fact (\w+)", source or "")
    if not m or m.group(1) not in eng.facts or m.group(1) not in eng.instrument.facts.index:
        return None
    f = eng.facts[m.group(1)]
    if f.point is None:
        return None
    meta = eng.instrument.facts.loc[m.group(1)]
    value = f"{f.point:g}" if isinstance(f.point, (int, float)) else str(f.point).replace("_", " ")
    unit = "" if meta["unit"] in ("category", "count") else f" {meta['unit']}"
    return {"label": meta["label"], "value": value + unit}


def build(assessment) -> dict:
    eng = assessment.engagement
    ins = eng.instrument
    min_n = ins.rules.get("evidence", {}).get("min_role_n", 5)
    from .groups import for_engagement
    groups = for_engagement(eng)
    ans = eng.answers
    ans = ans[~ans["dont_know"].fillna(False).astype(bool) & ~ans["not_applicable"].fillna(False).astype(bool)
              & (ans["label"].fillna("") != "")]
    ans = ans.assign(group=ans["respondent_id"].map(groups)).dropna(subset=["group"])
    out = {side: [] for side in SIDES}
    for item_id, it in ins.items.iterrows():
        side = it["block"] if it["block"] in ("staying", "changing") else "context" if item_id in CONTEXT_ITEMS else None
        if side is None:
            continue
        sub = ans[ans["item_id"] == item_id]
        rows = [None] if not it["rows"] else list(dict.fromkeys(sub["row"].dropna()))
        for row in rows:
            cell = sub[sub["row"].isna()] if row is None else sub[sub["row"] == row]
            answers = []
            for g, a in cell.groupby("group"):
                if len(a) < min_n:
                    continue
                counts = a["label"].value_counts()
                answers.append({"group": g, "answer": counts.index[0], "share": round(float(counts.iloc[0] / len(a)), 2),
                                "n": int(len(a))})
            if answers:
                out[side].append({"item": item_id, "question": it["text"].replace("{system}", eng.system),
                                  "row": row, "answers": answers, "fact": _fact(eng, it["source"])})
    return {"sides": [{"id": k, "title": SIDES[k], "rows": v} for k, v in out.items() if v]}


def months_absorbable(assessment, row: str = "Slower delivery of new features") -> float | None:
    """Median months the business groups say they can absorb (ABS), over everyone who answered."""
    months = {"Not at all": 0, "Up to 1 month": 1, "1–3 months": 3, "3–6 months": 6, "6–12 months": 12, "Longer": 24}
    a = assessment.engagement.answers
    a = a[(a["item_id"] == "ABS") & (a["row"] == row)]["label"].map(months).dropna()
    min_n = assessment.engagement.instrument.rules.get("evidence", {}).get("min_role_n", 5)
    return float(pd.Series(a).median()) if len(a) >= min_n else None
