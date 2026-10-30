"""v3 assessment: evidence → decision per draw → gates → shadow verdict under the default rules."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .axes import Evidence, build_evidence
from .decision import DecisionResult, apply_gates, decide, with_rules
from .engagement import Engagement, load_engagement

IMPLEMENTED = ("architecture", "hosting")
OPTION_FOR = {"move_to_cloud": "cloud", "hybrid": "hybrid", "repatriate": "repatriate", "improve_current": "improve_current"}


@dataclass
class Assessment:
    engagement: Engagement
    evidence: Evidence
    results: dict[str, DecisionResult]
    problems: list[str] = field(default_factory=list)
    stakes: object = None                       # mra.stakes.StakesReport
    fact_checks: list = field(default_factory=list)   # mra.fact_checks.FactCheck
    text: object = None                         # mra.llm.TextAnalysis (optional)
    narrative: object = None                    # mra.narrative.Narrative (optional)
    sourcing: list = field(default_factory=list)  # build or buy per candidate part (mra.sourcing)


def assess(path: str | Path | Engagement, decisions=IMPLEMENTED, draws: int | None = None, seed: int = 42,
           with_llm: bool = False) -> Assessment:
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
        if d == "hosting":
            _hosting_notes(r, evidence, eng)
        results[d] = r
    facts = eng.instrument.facts
    relevant = [f for f in evidence.missing_required if facts.at[f, "decision"] in (*decisions, "both")]
    problems = list(eng.problems) + [f"required fact missing: {f}" for f in relevant] + \
        list(evidence.flags.get("tco_problems", []))
    from .stakes import analyse as analyse_stakes
    from .fact_checks import check as check_facts
    assessment = Assessment(eng, evidence, results, problems, analyse_stakes(eng, evidence, results),
                            check_facts(eng))
    from .sourcing import evaluate as evaluate_sourcing
    assessment.sourcing = evaluate_sourcing(assessment, draws, seed)
    if with_llm:
        from .llm import analyse_engagement_text
        assessment.text = analyse_engagement_text(eng)
    return assessment


def _hosting_notes(r: DecisionResult, evidence: Evidence, eng: Engagement) -> None:
    """Unmet specific need, cost sensitivity of the leading option, and horizons 3 / 5 / 7 years."""
    from .decision import Context
    from .tco import horizons, sensitivity
    point = Context(evidence.at(0), eng.instrument.rules, evidence.current_state, "hosting")
    need = point.get("need_hosting_specific")
    current = eng.config.get("current_hosting", "own_infrastructure")
    if need is not None and need >= 3.5 and r.verdict in ("stay_as_is", "improve_current"):
        candidates = [o for o in ("hybrid", "cloud") if point.get(f"tco.{o}") is not None]
        if candidates and point.get("tco.stay") is not None:
            cheapest = min(candidates, key=lambda o: point.get(f"tco.{o}"))
            base = point.get(f"tco.{r.verdict}") if r.verdict == "improve_current" else point.get("tco.stay")
            extra = point.get(f"tco.{cheapest}") - base
            words = {"hybrid": "running selected workloads in a public cloud", "cloud": "moving to the cloud"}
            amount = f"€{abs(extra) / 1e3:,.0f}k" if abs(extra) < 1e6 else f"€{abs(extra) / 1e6:.2f}M"
            r.notes.append(f"A strong specific hosting need ({need:.1f}) is not met by this outcome. Meeting it by "
                           f"{words[cheapest]}, the cheapest way, would cost {amount} "
                           f"{'more' if extra >= 0 else 'less'} over "
                           f"{eng.instrument.rules['decisions']['hosting'].get('horizon_years', 5)} years.")
    if point.get("tco.stay") is None:
        return
    options = [k.split(".", 1)[1] for k in evidence.signals if k.startswith("tco.")]
    alternatives = [o for o in options if o not in ("stay", "improve_current")]
    chosen = OPTION_FOR.get(r.verdict if r.verdict != "insufficient_evidence" else (r.leaning or ""))
    # tornado for the verdict's option, or else for the strongest alternative to it
    focus = chosen if chosen in alternatives else min(alternatives, key=lambda o: point.get(f"tco_ratio.{o}") or 9e9)
    r.economics = {
        "tco": {o: round(point.get(f"tco.{o}")) for o in options if point.get(f"tco.{o}") is not None},
        "ratio": {o: round(point.get(f"tco_ratio.{o}"), 3) for o in options if point.get(f"tco_ratio.{o}") is not None},
        "payback_months": {o: (None if point.get(f"payback_months.{o}") == float("inf") else point.get(f"payback_months.{o}"))
                           for o in options if point.get(f"payback_months.{o}") is not None},   # None = never within horizon
        "horizons": horizons(evidence.fact_point, current),
        "tornado_option": focus,
    }
    facts = eng.instrument.facts
    hosting_ranges = {k: v for k, v in evidence.fact_ranges.items() if facts.at[k, "decision"] == "hosting"}
    tornado = sensitivity(evidence.fact_point, hosting_ranges, current, focus)
    r.economics["tornado"] = tornado[:1] + [t for t in tornado[1:] if t["swing"] > 0.001][:8]
