"""Rule engine: evaluates the pre-registered outcome rules on every bootstrap draw.

Logic is three-valued: a condition is True, False or None (unresolved, e.g. a missing input). An outcome whose
`when` is unresolved makes the draw unresolved — it counts towards "insufficient evidence", never silently towards
another outcome.
"""

from __future__ import annotations

import copy
from collections import Counter
from dataclasses import dataclass, field

import numpy as np

OPS = {
    "<": lambda a, b: a < b, "<=": lambda a, b: a <= b, ">": lambda a, b: a > b, ">=": lambda a, b: a >= b,
    "==": lambda a, b: a == b, "!=": lambda a, b: a != b, "in": lambda a, b: a in b,
}
NUMERIC_PREFIXES = ("fact.", "band.")


class Context:
    """Signal values for one draw, resolving derived signals from the rules lazily."""

    def __init__(self, values: dict, rules: dict, current: dict[str, str] | None = None, decision: str | None = None,
                 outcomes: dict[str, str] | None = None):
        self.values, self.rules = values, rules
        self.current = current or {}
        self.decision = decision
        self.outcomes = outcomes or {}
        self._cache: dict = {}

    @classmethod
    def from_values(cls, values: dict, rules: dict) -> "Context":
        return cls(values, rules)

    def get(self, name: str):
        if name in self._cache:
            return self._cache[name]
        value = self._resolve(name)
        self._cache[name] = value
        return value

    def _resolve(self, name: str):
        if name in self.values:
            return self.values[name]
        if name.startswith("outcome."):
            return self.outcomes.get(name.split(".", 1)[1])
        spec = self.rules.get("signals", {}).get(name)
        if spec is None:
            return None
        if "max_of" in spec or "min_of" in spec:
            members = [self.get(m) for m in spec.get("max_of", spec.get("min_of", []))]
            present = [m for m in members if m is not None]
            if not present:
                return None
            if "max_of" in spec:
                # unresolved only if a missing member could still change the result — reported, not blocking
                return max(present)
            return min(present) if len(present) == len(members) else None
        if "derive" in spec:
            for step in spec["derive"]:
                if "when" not in step:
                    return step["then"]
                result = evaluate(step["when"], self)
                if result is None:
                    return None
                if result:
                    return step["then"]
            return None
        if any(k in spec for k in ("all", "any", "not")):
            return evaluate({k: v for k, v in spec.items() if k in ("all", "any", "not")}, self)
        return None   # share_of signals are precomputed; tco signals arrive with mra/tco.py (M3)


def _compare(cond: dict, ctx: Context):
    if "only_if_current" in cond:
        allowed = cond["only_if_current"]
        allowed = allowed if isinstance(allowed, list) else [allowed]
        if ctx.current.get(ctx.decision) not in allowed:
            return True
    left = ctx.get(cond["signal"])
    if "ref" in cond:
        right = ctx.get(cond["ref"])
    else:
        right = cond.get("value")
    if left is None or right is None:
        return None
    if "premium" in cond:
        premium = ctx.get(cond["premium"]) or 0.0
        right = right * (1 + premium / 100)
    try:
        return bool(OPS[cond.get("op", "==")](left, right))
    except TypeError:
        return None


def evaluate(cond, ctx: Context):
    """Three-valued evaluation of a condition tree."""
    if cond is None:
        return True
    if isinstance(cond, list):
        cond = {"all": cond}
    if "all" in cond:
        results = [evaluate(c, ctx) for c in cond["all"]]
        return False if False in results else (None if None in results else True)
    if "any" in cond:
        results = [evaluate(c, ctx) for c in cond["any"]]
        return True if True in results else (None if None in results else False)
    if "not" in cond:
        r = evaluate(cond["not"], ctx)
        return None if r is None else not r
    return _compare(cond, ctx)


def within_reach(cond, ctx: Context) -> bool:
    """Is an unmet capability close enough to its threshold to be prepared for (see semantics.requires_capability)?"""
    if "any" in cond:
        return any(within_reach(c, ctx) for c in cond["any"])
    if "all" in cond:
        return all(within_reach(c, ctx) for c in cond["all"] if evaluate(c, ctx) is False)
    value, threshold, op = ctx.get(cond.get("signal", "")), cond.get("value"), cond.get("op")
    if not isinstance(value, (int, float)) or not isinstance(threshold, (int, float)):
        return False
    if "reach" in cond:
        bound = cond["reach"]
    elif cond["signal"].startswith(NUMERIC_PREFIXES):
        return False
    else:
        bound = threshold - 0.5 if op in (">", ">=") else threshold + 0.5
    return value >= bound if op in (">", ">=") else value <= bound


def _leaf_name(cond) -> str:
    if "signal" in cond:
        return cond["signal"]
    key = next(k for k in ("any", "all", "not") if k in cond)
    inner = cond[key] if isinstance(cond[key], list) else [cond[key]]
    return f"{key}({', '.join(_leaf_name(c) for c in inner)})"


# ====================================================================================== per-draw evaluation

@dataclass
class DrawResult:
    outcome: str                     # outcome id, or "unresolved"
    status: str                      # go | prepare_first | unresolved
    hard_stops: list[str] = field(default_factory=list)
    unmet: list[str] = field(default_factory=list)
    interim: str | None = None
    unresolved_at: str | None = None
    excluded: list[str] = field(default_factory=list)


def _check_outcome(o: dict, ctx: Context, rules: dict):
    """Returns (applies, status, hard_stops, unmet) — applies is None if unresolved."""
    if "only_if_current" in o:
        allowed = o["only_if_current"] if isinstance(o["only_if_current"], list) else [o["only_if_current"]]
        if ctx.current.get(ctx.decision) not in allowed:
            return False, None, [], []
    when = evaluate(o.get("when"), ctx)
    if when is not True:
        return when, None, [], []
    stops = []
    for h in o.get("blocked_by", []):
        r = evaluate(rules["hard_stops"][h]["when"], ctx)
        if r is None:
            return None, None, [], []
        if r and rules["hard_stops"][h].get("permanent"):
            return False, "excluded", [h], []
        if r:
            stops.append(h)
    unmet, reachable = [], True
    for c in o.get("requires_capability", []):
        r = evaluate(c, ctx)
        if r is None:
            return None, None, [], []
        if r is False:
            unmet.append(_leaf_name(c))
            reachable = reachable and within_reach(c, ctx)
    if unmet and not (len(unmet) <= 2 and reachable):
        return False, "fallthrough", stops, unmet
    status = "prepare_first" if (stops or unmet) else "go"
    return True, status, stops, unmet


def evaluate_draw(rules: dict, decision: str, ctx: Context) -> DrawResult:
    outcomes = rules["decisions"][decision]["outcomes"]
    excluded = []
    for i, o in enumerate(outcomes):
        applies, status, stops, unmet = _check_outcome(o, ctx, rules)
        if applies is None:
            return DrawResult("unresolved", "unresolved", unresolved_at=o["id"], excluded=excluded)
        if status == "excluded":
            excluded.append(f"{o['id']} ({stops[0]})")
        if not applies:
            continue
        result = DrawResult(o["id"], status, stops, unmet, excluded=excluded)
        if status == "prepare_first":
            for later in outcomes[i + 1:]:
                a, s, _, _ = _check_outcome(later, ctx, rules)
                if a and s == "go":
                    result.interim = later["id"]
                    break
        return result
    return DrawResult(rules["decisions"][decision].get("fallback", "insufficient_evidence"), "go")


# ====================================================================================== explanations

def _failing_leaves(cond, ctx: Context) -> list[dict]:
    """The leaf conditions that would all have to change for `cond` to hold (derived signals expanded)."""
    if cond is None:
        return []
    if isinstance(cond, list):
        cond = {"all": cond}
    if "all" in cond:
        unknown = [{"signal": "<unresolved>"} for c in cond["all"] if evaluate(c, ctx) is None]
        return unknown + [leaf for c in cond["all"] if evaluate(c, ctx) is False for leaf in _failing_leaves(c, ctx)]
    if "any" in cond:
        if evaluate(cond, ctx) is not False:
            return []
        options = [_failing_leaves(c, ctx) for c in cond["any"]]
        options = [o for o in options if o]
        return min(options, key=lambda o: (len(o), sum(_distance(c, ctx) for c in o))) if options else []
    if "not" in cond:
        return []
    if _compare(cond, ctx) is not False:
        return []
    spec = ctx.rules.get("signals", {}).get(cond.get("signal", ""), {})
    if isinstance(ctx.get(cond["signal"]), bool) and any(k in spec for k in ("all", "any")):
        inner = {k: v for k, v in spec.items() if k in ("all", "any")}
        return _failing_leaves(inner, ctx) if cond.get("value") is True else []
    return [cond]


def _threshold(cond, ctx: Context):
    return ctx.get(cond["ref"]) if "ref" in cond else cond.get("value")


def _distance(cond, ctx: Context) -> float:
    """How far a failing condition is from holding: share of the 1–5 scale for scores, relative for the rest."""
    value, threshold = ctx.get(cond.get("signal", "")), _threshold(cond, ctx)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isinstance(threshold, (int, float)):
        return float("inf")
    name = cond["signal"]
    on_scale = name.split(".")[0] in ("need", "capability", "fit", "requirement", "locality", "item", "band") \
        or name in ("need_hosting_specific",)
    if on_scale:
        return abs(value - threshold) / 4.0
    return abs(value - threshold) / max(abs(threshold), 1.0)


def what_would_change(rules: dict, decision: str, ctx: Context, leading: str, limit: int = 3) -> list[dict]:
    """Single-condition changes that would make an earlier-ordered outcome apply instead of the leading one."""
    found = []
    for o in rules["decisions"][decision]["outcomes"]:
        if o["id"] == leading:
            break
        if "only_if_current" in o:
            allowed = o["only_if_current"] if isinstance(o["only_if_current"], list) else [o["only_if_current"]]
            if ctx.current.get(decision) not in allowed:
                continue
        leaves = _failing_leaves(o.get("when"), ctx)
        if len(leaves) == 1 and _distance(leaves[0], ctx) != float("inf"):
            c = leaves[0]
            threshold = _threshold(c, ctx)
            found.append({"outcome": o["id"], "signal": c["signal"], "op": c["op"],
                          "threshold": c.get("ref", threshold) if "ref" in c else threshold,
                          "threshold_value": round(float(threshold), 2),
                          "current": round(float(ctx.get(c["signal"])), 2), "distance": round(_distance(c, ctx), 3)})
    return sorted(found, key=lambda f: f["distance"])[:limit]


# ====================================================================================== decision over all draws

@dataclass
class DecisionResult:
    decision: str
    current_state: str
    verdict: str                     # outcome id, or insufficient_evidence
    status: str                      # go | prepare_first | insufficient
    probability: float
    distribution: dict[str, float]
    leaning: str | None = None
    hard_stops: list[str] = field(default_factory=list)
    unmet_capabilities: list[str] = field(default_factory=list)
    interim: str | None = None
    unresolved_share: float = 0.0
    unresolved_at: list[str] = field(default_factory=list)
    what_would_change: list[dict] = field(default_factory=list)
    excluded: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    economics: dict = field(default_factory=dict)
    gates: dict = field(default_factory=dict)
    shadow: dict | None = None

    def as_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


def decide(evidence, rules: dict, decision: str, confidence: float | None = None) -> DecisionResult:
    confidence = confidence or rules.get("evidence", {}).get("confidence", 0.8)
    results = []
    for b in range(evidence.draws):
        ctx = Context(evidence.at(b), rules, evidence.current_state, decision)
        results.append(evaluate_draw(rules, decision, ctx))
    counts = Counter(r.outcome for r in results)
    n = len(results)
    distribution = {k: v / n for k, v in counts.most_common()}
    candidates = {k: v for k, v in distribution.items() if k != "unresolved"}
    leading, p = max(candidates.items(), key=lambda kv: kv[1]) if candidates else ("unresolved", 0.0)
    unresolved = [r for r in results if r.outcome == "unresolved"]
    point_ctx = Context(evidence.at(0), rules, evidence.current_state, decision)

    if p >= confidence:
        mine = [r for r in results if r.outcome == leading]
        prepared = [r for r in mine if r.status == "prepare_first"]
        status = "prepare_first" if len(prepared) >= len(mine) / 2 else "go"
        stops = [s for s, c in Counter(s for r in prepared for s in r.hard_stops).most_common() if c >= len(prepared) / 2]
        unmet = [u for u, c in Counter(u for r in prepared for u in r.unmet).most_common() if c >= len(prepared) / 2]
        interim = Counter(r.interim for r in prepared if r.interim).most_common(1)
        verdict = DecisionResult(decision, evidence.current_state[decision], leading, status, round(p, 3),
                                 distribution, None, stops, unmet, interim[0][0] if interim else None)
    else:
        verdict = DecisionResult(decision, evidence.current_state[decision], "insufficient_evidence", "insufficient",
                                 round(p, 3), distribution, leading if p >= 0.5 and leading != "unresolved" else None)
    verdict.excluded = [e for e, c in Counter(e for r in results for e in r.excluded).most_common() if c >= n / 2]
    verdict.unresolved_share = round(len(unresolved) / n, 3)
    verdict.unresolved_at = [k for k, _ in Counter(r.unresolved_at for r in unresolved).most_common(3)]
    target = verdict.verdict if verdict.verdict != "insufficient_evidence" else (verdict.leaning or "")
    verdict.what_would_change = what_would_change(rules, decision, point_ctx, target) if target else []
    return verdict


def apply_gates(verdict: DecisionResult, evidence, rules: dict, governance: dict, items_present: bool = True) -> DecisionResult:
    """Post-verdict gate check, walking down the rule order for an interim step whose gates pass."""
    from .gates import check_gates
    if verdict.status == "insufficient":
        return verdict
    outcomes = rules["decisions"][verdict.decision]["outcomes"]
    spec = next(o for o in outcomes if o["id"] == verdict.verdict)
    result = check_gates(spec, rules, governance, evidence)
    verdict.gates = result
    if any(g["status"] != "pass" for g in result["required"].values()):
        verdict.status = "prepare_first"
        ctx = Context(evidence.at(0), rules, evidence.current_state, verdict.decision)
        start = [o["id"] for o in outcomes].index(verdict.verdict) + 1
        for later in outcomes[start:]:
            applies, status, _, _ = _check_outcome(later, ctx, rules)
            if applies and status == "go":
                later_gates = check_gates(later, rules, governance, evidence)
                if all(g["status"] == "pass" for g in later_gates["required"].values()):
                    verdict.interim = later["id"]
                    break
    return verdict


def with_rules(engagement, rules: dict):
    """A shallow copy of an engagement whose instrument uses different rules (for the shadow verdict)."""
    eng = copy.copy(engagement)
    eng.instrument = copy.copy(engagement.instrument)
    eng.instrument.rules = rules
    return eng
