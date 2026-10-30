"""Next steps assembled from the action library (instrument/recommendations.yaml) and the assessment's findings."""

from __future__ import annotations

from pathlib import Path

import yaml

from .explain import condition_label, outcome_label


def load_library(instrument_root: Path) -> dict:
    path = Path(instrument_root) / "recommendations.yaml"
    return yaml.safe_load(path.read_text()) if path.exists() else {}


def _capability_key(name: str, library: dict) -> str | None:
    return next((k for k in library.get("capabilities", {}) if k in name), None)


def next_steps(assessment) -> list[dict]:
    """Ordered actions: [{phase, phase_label, decision, action, owner, reason}]."""
    eng = assessment.engagement
    ins = eng.instrument
    lib = load_library(ins.root)
    phases = lib.get("phases", {})
    steps, seen = [], set()

    def add(phase, decision, action, owner, reason=""):
        if action in seen:
            return
        seen.add(action)
        steps.append({"phase": phase, "phase_label": phases.get(phase, phase), "decision": decision,
                      "action": action, "owner": owner, "reason": reason})

    for decision, r in assessment.results.items():
        path = outcome_label(ins, decision, r.verdict if r.verdict != "insufficient_evidence" else r.leaning)
        for gate, info in r.gates.get("required", {}).items():
            if info["status"] != "pass" and gate in lib.get("gates", {}):
                g = lib["gates"][gate]
                state = "not met" if info["status"] == "fail" else "unresolved"
                add("before_commitment", decision, g["action"], g["owner"],
                    f"Precondition for \u201c{path}\u201d is {state}.")
        for stop in r.hard_stops:
            h = lib.get("hard_stops", {}).get(stop)
            if h:
                add("before_commitment", decision, h["action"], h["owner"], f"Blocks “{path}”.")
        for e in r.excluded:
            stop = e.split("(")[-1].rstrip(")")
            h = lib.get("hard_stops", {}).get(stop)
            if h:
                add("before_commitment", decision, h["action"], h["owner"], "Excludes an option permanently.")
        for name in r.unmet_capabilities:
            key = _capability_key(name, lib)
            if key:
                c = lib["capabilities"][key]
                add("capability", decision, c["action"], c["owner"],
                    f"Needed for “{path}”: {condition_label(name, ins)}.")
        if r.verdict == "insufficient_evidence":
            inputs = ", ".join(r.unresolved_at) or "the inputs listed in the appendix"
            e = lib.get("evidence", {}).get("insufficient")
            if e:
                add("evidence", decision, e["action"].format(inputs=inputs), e["owner"])
        target = r.verdict if r.verdict != "insufficient_evidence" else None
        if target:
            for step in ins.outcomes[decision][target].get("first_steps", []):
                add("first_steps", decision, step, "Sponsor", f"For “{path}”.")

    missing = [p.split(": ", 1)[1] for p in assessment.problems if p.startswith("required fact missing")]
    if missing and (e := lib.get("evidence", {}).get("missing_fact")):
        add("evidence", None, e["action"].format(facts=", ".join(missing)), e["owner"])

    div = lib.get("divergence")
    for d in assessment.evidence.divergences[:3]:
        area = d["sub_area"].split(".")[-1].replace("_", " ")
        add("people", None, div["action"].format(area=area, survey=f"{d['survey']:.1f}", fact=f"{d['fact_band']:.1f}"),
            div["owner"])

    st, people = assessment.stakes, lib.get("people", {})
    if st:
        for p in st.preference_vs_evidence:
            if p["differs"] and p["share"] >= 0.5:
                add("people", p["decision"], people["preference_differs"]["action"].format(group=p["group"]),
                    people["preference_differs"]["owner"])
        for a in st.stake_alignment:
            if a["notable"]:
                add("people", a["decision"], people["stake_alignment"]["action"].format(group=a["group"]),
                    people["stake_alignment"]["owner"])
        if st.watermelon:
            add("people", None, people["watermelon"]["action"], people["watermelon"]["owner"])
        if st.leadership_disagreement:
            add("people", None, people["leadership_disagreement"]["action"], people["leadership_disagreement"]["owner"])
        for g, c in st.concern.items():
            if c.get("self", 0) >= 0.4:
                add("people", None, people["concern"]["action"].format(group=g), people["concern"]["owner"])

    order = list(phases)
    return sorted(steps, key=lambda s: order.index(s["phase"]) if s["phase"] in order else len(order))
