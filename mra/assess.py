"""v3 assessment: evidence → decision per draw → gates → shadow verdict under the default rules."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .axes import Evidence, build_evidence
from .decision import DecisionResult, apply_gates, decide, with_rules
from .engagement import Engagement, load_engagement

IMPLEMENTED = ("architecture",)   # hosting arrives with the TCO model (M3)


@dataclass
class Assessment:
    engagement: Engagement
    evidence: Evidence
    results: dict[str, DecisionResult]
    problems: list[str] = field(default_factory=list)


def assess(path: str | Path | Engagement, decisions=IMPLEMENTED, draws: int | None = None, seed: int = 42) -> Assessment:
    eng = path if isinstance(path, Engagement) else load_engagement(path)
    rules = eng.instrument.rules
    evidence = build_evidence(eng, draws, seed)
    results = {}
    for d in decisions:
        r = decide(evidence, rules, d)
        r = apply_gates(r, evidence, rules, eng.governance)
        if rules != eng.default_rules:
            shadow_eng = with_rules(eng, eng.default_rules)
            shadow_ev = build_evidence(shadow_eng, draws, seed)
            s = decide(shadow_ev, eng.default_rules, d)
            r.shadow = {"verdict": s.verdict, "status": s.status, "probability": s.probability}
        results[d] = r
    facts = eng.instrument.facts
    relevant = [f for f in evidence.missing_required if facts.at[f, "decision"] in (*decisions, "both")]
    problems = list(eng.problems) + [f"required fact missing: {f}" for f in relevant]
    return Assessment(eng, evidence, results, problems)
