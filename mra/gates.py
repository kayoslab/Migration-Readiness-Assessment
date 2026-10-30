"""Gates: preconditions attested with evidence (governance.yaml), checked after the verdict for one outcome.

Yes with an evidence reference = pass · Partly, or Yes without evidence, or no answer = unresolved · No = fail.
Checks within a gate combine by minimum (a sponsor who is leaving fails the sponsor gate). Survey items that
"corroborate" a gate are compared with the attestation; disagreement is reported, never decisive.
"""

from __future__ import annotations

RANK = {"fail": 0, "unresolved": 1, "pass": 2}


def check_status(answer: dict | None) -> str:
    if not answer:
        return "unresolved"
    a = str(answer.get("answer", "")).strip().lower()
    if a == "no":
        return "fail"
    if a == "yes":
        return "pass" if str(answer.get("evidence") or "").strip() else "unresolved"
    return "unresolved"


def gate_status(gate: str, rules: dict, governance: dict, evidence) -> dict:
    spec = rules["gates"][gate]
    checks = {c: check_status(governance.get(c)) for c in spec["checks"]}
    status = min(checks.values(), key=RANK.get)
    low, high = [], []                                   # survey questions that contradict the attestation
    for item in spec.get("corroborated_by", []):
        score = evidence.at(0).get(f"item.{item}")
        if score is None:
            continue
        if status == "pass" and score < 3.0:
            low.append(f"{score:.1f}")
        elif status == "fail" and score >= 4.0:
            high.append(f"{score:.1f}")
    corroboration = []
    if low:
        corroboration.append(f"Attested, but respondents rate it low ({' and '.join(low)} of 5 on the related survey "
                             f"question{'s' if len(low) > 1 else ''}).")
    if high:
        corroboration.append(f"Attested as not in place, but respondents rate it high ({' and '.join(high)} of 5).")
    return {"label": spec["label"], "status": status, "checks": checks, "corroboration": corroboration}


def check_gates(outcome_spec: dict, rules: dict, governance: dict, evidence) -> dict:
    required = list(outcome_spec.get("requires_gates", []))
    if evidence.flags.get("track_record_concern") and required and "stop_criteria" not in required:
        required.append("stop_criteria")
    return {
        "required": {g: gate_status(g, rules, governance, evidence) for g in required},
        "conditions": {g: gate_status(g, rules, governance, evidence) for g in outcome_spec.get("reports_conditions", [])},
        "stop_criteria_mandatory": bool(evidence.flags.get("track_record_concern")),
    }
