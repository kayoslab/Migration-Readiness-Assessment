"""Plain-language labels and sentences for signals, conditions and verdicts (used by the v3 report and CLI)."""

from __future__ import annotations

from .instrument import Instrument

AREA_WORDS = {
    "coupling": "coupling between teams", "blast_radius": "failures spreading between parts",
    "business_impact": "business impact of platform limits", "cognitive_load": "team cognitive load",
    "growth": "approved growth", "distinct_profiles": "parts with a distinct profile",
    "delivery_pipeline": "delivery pipeline", "delivery_throughput": "delivery throughput",
    "platform_basics": "platform basics", "platform_distribution": "platform for many deployables",
    "operations": "operations", "data": "data separability", "modularity": "enforced module boundaries",
    "skills": "distributed-systems skills", "domain_ownership": "domain ownership",
    "distributed_operations": "distributed ways of operating", "consistency_tolerance": "tolerance for short delays in consistency",
    "concentration": "concentration of friction", "seam_data": "separability of the candidate's data",
    "elasticity": "load variability", "capacity_lead_time": "capacity lead time",
    "managed_services": "need for managed services", "ops_burden": "infrastructure toil", "reach": "geographic reach",
    "automation": "infrastructure automation", "cloud_skills": "cloud operations skills",
    "cost_discipline": "cost transparency", "onprem_ops": "hardware operations skills",
}
OPS = {">=": "at least", ">": "above", "<=": "at most", "<": "below", "==": "", "!=": "not"}
OPTION_WORDS = {"cloud": "moving to the cloud", "hybrid": "a hybrid setup", "repatriate": "moving back from the cloud",
                "improve_current": "improving the current setup", "stay": "keeping the current setup"}
STATUS_WORDS = {"go": "Proceed", "prepare_first": "Prepare first", "insufficient": "Insufficient evidence"}


def signal_label(signal: str, ins: Instrument) -> str:
    p = signal.split(".")
    head = p[0]
    if head == "fact" and p[1] in ins.facts.index:
        return ins.facts.at[p[1], "label"]
    if head == "item" and p[1] in ins.items.index:
        return f"“{ins.items.at[p[1], 'text']}”"
    if head == "need" and len(p) == 2:
        return f"Need for change ({p[1]})"
    if head in ("need", "capability") and len(p) == 3:
        return AREA_WORDS.get(p[2], p[2].replace("_", " ")).capitalize()
    if head in ("fit", "requirement", "locality") and len(p) == 2:
        return AREA_WORDS.get(p[1], p[1].replace("_", " ")).capitalize()
    if head == "locality":
        return "Concentration of friction in a few areas"
    if head in ("tco_ratio", "payback_months", "payback_after_cutover", "tco_saving_fte"):
        what = {"tco_ratio": "Cost relative to the current setup", "payback_months": "Payback (months from decision)",
                "payback_after_cutover": "Payback (months after cut-over)", "tco_saving_fte": "Annual saving in salaries"}[head]
        return f"{what} for {OPTION_WORDS.get(p[1], p[1])}"
    spec = ins.rules.get("signals", {}).get(signal)
    if spec and spec.get("description"):
        return spec["description"]
    return signal.replace("_", " ")


def fmt(value) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:,.0f}" if abs(value) >= 100 else f"{value:.2f}".rstrip("0").rstrip(".")
    return str(value)


def outcome_label(ins: Instrument, decision: str, outcome: str | None) -> str:
    if not outcome:
        return "–"
    spec = ins.outcomes.get(decision, {}).get(outcome) or ins.outcomes.get("common", {}).get(outcome, {})
    return spec.get("label", outcome.replace("_", " "))


def flip_sentence(flip: dict, decision: str, ins: Instrument) -> str:
    label = signal_label(flip["signal"], ins)
    threshold = flip["threshold"]
    if isinstance(threshold, str):           # a reference to another signal
        threshold = f"{signal_label(threshold, ins).lower()} ({fmt(flip['threshold_value'])})"
    else:
        threshold = fmt(threshold)
    op = OPS.get(flip["op"], flip["op"])
    return (f"{outcome_label(ins, decision, flip['outcome'])} would apply if {label[0].lower() + label[1:]} were "
            f"{op + ' ' if op else ''}{threshold} (currently {fmt(flip['current'])}).")


def condition_label(name: str, ins: Instrument) -> str:
    """Unmet capability names are signals or any(...)/all(...) groups."""
    if name.startswith(("any(", "all(")):
        inner = [signal_label(s.strip(), ins) for s in name[4:-1].split(",")]
        return " or ".join(inner)
    return signal_label(name, ins)
