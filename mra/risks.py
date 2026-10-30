"""Risks, assumptions and dependencies, derived from what the assessment found.

Every entry traces back to a finding in the report — an open precondition, a hard stop, a capability gap, an input
close to a threshold, a fact-sheet finding, a stakeholder pattern — so the register is consistent with the verdict
and changes when the evidence changes. Likelihood and impact are rated high / medium / low by rule, not by judgement
of the analyst; owners and mitigations come from the action library (instrument/recommendations.yaml).
"""

from __future__ import annotations

from .explain import outcome_label, signal_label
from .recommend import load_library

RANK = {"high": 3, "medium": 2, "low": 1}


def _risk(title, cause, likelihood, impact, owner, mitigation, decision=None, kind="delivery"):
    return {"title": title, "cause": cause, "likelihood": likelihood, "impact": impact, "owner": owner,
            "mitigation": mitigation, "decision": decision, "kind": kind,
            "score": RANK[likelihood] * RANK[impact]}


def register(assessment) -> dict:
    eng, ev = assessment.engagement, assessment.evidence
    ins, rules = eng.instrument, eng.instrument.rules
    lib = load_library(ins.root)
    gates_lib, stops_lib, caps_lib, people_lib = (lib.get(k, {}) for k in ("gates", "hard_stops", "capabilities", "people"))
    risks, assumptions, dependencies = [], [], []

    for d, r in assessment.results.items():
        path = outcome_label(ins, d, r.verdict if r.verdict != "insufficient_evidence" else r.leaning)
        title = d.title()
        for g, info in r.gates.get("required", {}).items():
            if info["status"] == "pass":
                continue
            entry = gates_lib.get(g, {})
            risks.append(_risk(f"{title}: committing without “{info['label'].lower()}”",
                               f"Precondition {'not met' if info['status'] == 'fail' else 'unresolved'} for “{path}”.",
                               "high" if info["status"] == "fail" else "medium", "high",
                               entry.get("owner", "Sponsor"), entry.get("action", "Resolve before committing."), d, "governance"))
            dependencies.append({"decision": d, "dependency": info["label"], "owner": entry.get("owner", "Sponsor"),
                                 "status": info["status"]})
        for h in r.hard_stops:
            entry = stops_lib.get(h, {})
            risks.append(_risk(f"{title}: {rules['hard_stops'][h]['label'].lower()}", f"Blocks “{path}”.",
                               "high", "high", entry.get("owner", "Engineering"), entry.get("action", ""), d, "technical"))
        for c in r.unmet_capabilities:
            key = next((k for k in caps_lib if k in c), None)
            if key:
                risks.append(_risk(f"{title}: capability gap — {signal_label(c, ins).lower() if '(' not in c else key.replace('_', ' ')}",
                                   f"Needed for “{path}”.", "medium", "high", caps_lib[key]["owner"],
                                   caps_lib[key]["action"], d, "capability"))
        for u in r.uncertain_inputs[:3]:
            risks.append(_risk(f"{title}: verdict sensitive to {signal_label(u['signal'], ins).lower()}",
                               "The input is close to a decision threshold or partly missing.",
                               "medium", "high" if r.verdict == "insufficient_evidence" else "medium",
                               "Analyst", "Firm up the input and re-run the assessment before committing.", d, "evidence"))
        if r.interim:
            dependencies.append({"decision": d, "dependency": f"Interim step: {outcome_label(ins, d, r.interim)}",
                                 "owner": "Sponsor", "status": "planned"})
        if d == "hosting" and r.economics.get("tornado"):
            words = {"cloud": "moving to the cloud", "hybrid": "a hybrid setup", "repatriate": "moving back",
                     "improve_current": "improving the current setup"}
            option = r.economics.get("tornado_option", "")
            base, drivers = r.economics["tornado"][0]["base"], r.economics["tornado"][1:]
            flips = [t for t in drivers if min(t["low"], t["high"]) < 1.0 < max(t["low"], t["high"])]
            for t in flips[:2]:
                risks.append(_risk(f"Hosting: cost case depends on {signal_label('fact.' + t['input'], ins).split(',')[0].lower()}",
                                   f"Within its estimated range the input moves the comparison across today's cost ({t['low']:.2f}–{t['high']:.2f}).",
                                   "medium", "high", "Finance with platform team",
                                   "Replace the estimate with a quote or measured value.", d, "cost"))
            for t in drivers[:5]:
                fact = eng.facts.get(t["input"])
                if fact and fact.grade in ("estimate", "benchmark"):
                    assumptions.append({"assumption": f"{signal_label('fact.' + t['input'], ins)}: {fact.low:,.0f}–{fact.high:,.0f} "
                                                      f"(likely {fact.likely:,.0f})",
                                        "basis": f"{fact.grade}; {fact.source or 'no source'}",
                                        "sensitivity": f"moves the cost of {words.get(option, option)} between "
                                                       f"{min(t['low'], t['high']):.2f} and {max(t['low'], t['high']):.2f} "
                                                       "of an improved current setup"})

    rules_sourcing = rules.get("sourcing") or {}
    for part in getattr(assessment, "sourcing", []) or []:
        name = part["name"]
        if part["verdict"] == "replace_with_product":
            risks.append(_risk(f"Build or buy: dependence on the product that replaces {name}",
                               "Once replaced, the part's data, prices and roadmap sit with the vendor.", "medium", "medium",
                               "Risk and compliance", "Keep the exit plan current: test the export yearly and review the "
                               "contract at each renewal.", "sourcing", "technical"))
            lo, hi = part.get("coverage_range") or (None, None)
            bar = (rules_sourcing.get("replace_when") or {}).get("coverage_at_least", 80)
            if lo is not None and lo < bar:
                risks.append(_risk(f"Build or buy: the product may cover less of {name} than estimated",
                                   f"Within its estimated range, coverage falls below {bar:g}% ({lo:.0f}–{hi:.0f}%).",
                                   "medium", "high", "Technology lead",
                                   "Confirm coverage in the proof of concept before the contract is signed.",
                                   "sourcing", "evidence"))
        elif part["verdict"] == "insufficient_evidence":
            risks.append(_risk(f"Build or buy: no decision yet on {name}", "The evidence does not reach the agreed "
                               "confidence either way.", "medium", "medium", "Technology lead",
                               "Firm up the product's coverage and the cost estimates, then re-run the assessment.",
                               "sourcing", "evidence"))

    from .integrity import run as run_integrity       # what keeps the report a draft is a risk to the decision
    owners = {"run_cost_reconciliation": "Finance", "rules_signed_off": "Sponsor"}
    for issue in run_integrity(assessment):
        if issue.severity == "block":
            risks.append(_risk(f"Basis of the decision: {issue.title[0].lower() + issue.title[1:]}", issue.message,
                               "high", "high", owners.get(issue.id, "Sponsor"),
                               "Resolve before the report is issued as final; see the next steps.",
                               (issue.decisions or [None])[0], "governance"))

    if ev.flags.get("track_record_concern"):
        risks.append(_risk("Programme history: past large technology programmes overran or under-delivered",
                           "At least 30% of informed respondents in a group reported it.", "medium", "high", "Sponsor",
                           "Make checkpoints and stop criteria binding, and review progress against them.", None, "governance"))

    for fc in assessment.fact_checks:
        if fc.severity == "problem":
            risks.append(_risk("Evidence independence: " + fc.message.split(";")[0].rstrip("."), fc.message, "high", "high",
                               "Sponsor", "Have the affected facts re-attested by someone without a stake in the outcome.",
                               None, "evidence"))
        elif "estimators differ" in fc.message or "only one estimator" in fc.message:
            assumptions.append({"assumption": fc.message, "basis": "fact-sheet check", "sensitivity": "see cost case"})

    st = assessment.stakes
    if st:
        for a in st.stake_alignment:
            if a["notable"]:
                risks.append(_risk(f"People: support from {a['group']} depends on how the change affects their roles",
                                   f"Preferences in {a['group']} track expected personal impact ({a['decision']}).",
                                   "medium", "medium", people_lib.get("stake_alignment", {}).get("owner", "HR"),
                                   people_lib.get("stake_alignment", {}).get("action", "").format(group=a["group"]), a["decision"], "people"))
        for g, c in st.concern.items():
            if c.get("self", 0) >= 0.4:
                risks.append(_risk(f"People: role concern in {g} ({c['self']:.0%} moderately or very concerned)",
                                   "Unaddressed concern reduces engagement and raises attrition risk among people with critical knowledge.",
                                   "high" if c["self"] >= 0.7 else "medium", "medium",
                                   people_lib.get("concern", {}).get("owner", "HR"),
                                   people_lib.get("concern", {}).get("action", "").format(group=g), None, "people"))
        if st.leadership_disagreement:
            risks.append(_risk("Leadership: technology and business leadership prefer different directions",
                               "A divided leadership weakens sponsorship and invites re-litigation of the decision.",
                               "high", "high", people_lib.get("leadership_disagreement", {}).get("owner", "Executive committee"),
                               people_lib.get("leadership_disagreement", {}).get("action", ""), None, "people"))
        if st.watermelon:
            risks.append(_risk("Alignment: leadership rates alignment much higher than engineering and operations",
                               f"{len(st.watermelon)} statement(s) differ by a point or more.", "medium", "medium",
                               people_lib.get("watermelon", {}).get("owner", "Sponsor"),
                               people_lib.get("watermelon", {}).get("action", ""), None, "people"))
    for div in ev.divergences[:2]:
        risks.append(_risk(f"Perception: {signal_label(div['sub_area'], ins).lower()} is perceived differently from its measurement",
                           f"Survey {div['survey']:.1f} vs measured {div['fact_band']:.1f}.", "medium", "low",
                           "Technology lead", "Share the measurement and discuss the difference before decisions are communicated.",
                           None, "evidence"))

    evcfg = rules.get("evidence", {})
    assumptions += [
        {"assumption": f"A path is recommended only if it applies in at least {evcfg.get('confidence', 0.8):.0%} of draws",
         "basis": "decision rules (pre-registered)", "sensitivity": "see the calibration report"},
        {"assumption": "Facts count twice as much as survey perception; every group counts equally",
         "basis": "decision rules (pre-registered)", "sensitivity": "–"},
        {"assumption": f"Hosting costs over {rules['decisions'].get('hosting', {}).get('horizon_years', 5)} years, discounted",
         "basis": "decision rules; 3- and 7-year results in the economics", "sensitivity": "–"},
    ]
    risks.sort(key=lambda x: (-x["score"], x["kind"]))
    for i, x in enumerate(risks, 1):
        x["id"] = f"R{i}"
    return {"risks": risks, "assumptions": assumptions, "dependencies": dependencies}
