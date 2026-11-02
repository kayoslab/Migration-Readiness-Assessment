"""`mra stress`: generated organisations, each built into a report and checked.

The calibration grid asks whether verdicts are right; this asks whether every report holds together across
organisations nobody designed by hand: group sizes from absent to large (so small groups are pooled or dropped),
the three hosting states, one or many deployables, signed and unsigned rules, missing or late intent sheets, risks of
staying, hosting constraints with and without a citation, build-or-buy parts, mixed governance answers. Each report
context is checked against the board-readiness rubric and against invariants the instrument promises; with --pdf
some are rendered and the decision page must fit on one page.
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
import traceback
from collections import Counter
from pathlib import Path

import numpy as np
import yaml

from .cases import BILLING
from .scenario import Scenario, build

ROOT = Path(__file__).resolve().parents[1]
INSTRUMENT = ROOT / "instrument"
ROLES = ["ENG", "PRD", "BUS", "TEC", "EXE", "OPS", "SEC", "FIN"]
SUB_AREAS = ["need.architecture.coupling", "need.architecture.business_impact", "need.architecture.cognitive_load",
             "capability.architecture.delivery_pipeline", "capability.architecture.platform_basics",
             "capability.architecture.platform_distribution", "capability.architecture.operations",
             "capability.architecture.data", "fit.domain_ownership", "fit.distributed_operations",
             "requirement.consistency_tolerance", "locality.concentration", "need.hosting.elasticity",
             "need.hosting.capacity_lead_time", "need.hosting.managed_services", "need.hosting.ops_burden",
             "capability.hosting.automation", "capability.hosting.operations", "capability.hosting.cloud_skills",
             "capability.hosting.onprem_ops"]
MOVES = ("move_to_cloud", "hybrid", "repatriate")


def _range(rng, likely, spread=0.3, grade="estimate"):
    return {"low": round(likely * (1 - spread * rng.random())), "likely": round(likely),
            "high": round(likely * (1 + spread * (1 + rng.random()))), "grade": grade}


def organisation(i: int, rng: np.random.Generator) -> tuple[Scenario, dict]:
    """One generated organisation and what was varied (for the log)."""
    hosting = rng.choice(["own_infrastructure", "cloud", "hybrid"], p=[0.5, 0.3, 0.2])
    shape = rng.choice(["monolith", "core_with_satellites", "distributed"], p=[0.5, 0.2, 0.3])
    sizes = {r: int(rng.choice([0, 2, 3, 4, 5, 6, 8, 12, 20, 30], p=[.04, .08, .1, .1, .14, .14, .14, .12, .08, .06]))
             for r in ROLES}
    sizes["ENG"] = max(sizes["ENG"], int(rng.choice([3, 6, 12, 25, 40])))
    targets = {k: round(float(rng.uniform(1, 5)), 1) for k in SUB_AREAS if rng.random() < 0.8}
    run_cost = float(rng.choice([300e3, 800e3, 1.5e6, 3e6]))
    facts = {
        "teams_per_deployable": int(rng.integers(1, 12)), "cross_team_change_pct": int(rng.integers(2, 50)),
        "blast_radius_pct": int(rng.integers(3, 45)), "shared_tables_pct": int(rng.integers(5, 60)),
        "deploys_per_week": float(rng.choice([0.25, 1, 3, 10])), "lead_time_hours": float(rng.choice([8, 72, 300, 900])),
        "change_failure_pct": int(rng.integers(3, 30)), "restore_hours": float(rng.choice([1, 4, 24])),
        "rollback_minutes": int(rng.choice([5, 30, 45, 120])),
        "run_cost_annual": _range(rng, run_cost, 0.15, "invoice"),
        "peak_to_median_load": float(rng.choice([1.2, 1.8, 4, 15])),
        "capacity_lead_time_weeks": int(rng.choice([1, 4, 10])), "regions_required": int(rng.choice([1, 1, 2, 4])),
        "hw_refresh_due_months": int(rng.integers(3, 48)), "hw_refresh_capex": float(rng.choice([200e3, 600e3, 1.2e6])),
        "cloud_compute_baseline_annual": _range(rng, run_cost * float(rng.uniform(0.15, 0.9)), 0.2, "calculator_export"),
        "migration_cost": _range(rng, float(rng.choice([150e3, 400e3, 900e3]))),
        "migration_months": _range(rng, float(rng.choice([6, 12, 18]))),
        "past_programme_overrun_pct": int(rng.choice([0, 20, 40, 80])),
        "critical_function": str(rng.choice(["yes", "no"])),
        "status_quo_compliance_findings": int(rng.choice([0, 0, 0, 1, 3])),
        "dr_test_result": str(rng.choice(["met", "met", "met_with_deviations", "partial_scope", "failed", "never_tested"])),
        "compensating_controls": str(rng.choice(["no", "no", "no", "yes"])),
        "past_savings_verified": str(rng.choice(["achieved", "partly", "not_achieved", "never_checked", "no_such_programme"])),
        "onprem_hw_ops_people": int(rng.integers(0, 6)), "cloud_oncall_experienced_people": int(rng.integers(0, 6)),
    }
    constraint = rng.choice(["any", "any", "any", "eu_region", "own_premises_only", "own_premises_only_cited"])
    facts["hosting_constraint"] = ({"value": "own_premises_only", "citation": "Sector regulation §4 (legal opinion)"}
                                   if constraint == "own_premises_only_cited" else str(constraint))
    if shape == "monolith":
        facts.update({"deployables_in_scope": 1, "core_code_share_pct": 100})
    elif shape == "core_with_satellites":
        facts.update({"deployables_in_scope": 4, "core_code_share_pct": 80})
    else:
        facts.update({"deployables_in_scope": int(rng.integers(8, 60)), "core_code_share_pct": 10,
                      "services_per_team": float(rng.uniform(1, 8)), "lockstep_deploy_pct": int(rng.integers(0, 50)),
                      "cross_service_change_pct": int(rng.integers(5, 50))})
    if hosting == "cloud":
        facts.update({"target_model": str(rng.choice(["colocation", "managed_dedicated"])), "sunk_commitment_cost": 0,
                      "cloud_commitment_end_months": int(rng.choice([0, 12, 30])), "cloud_ops_fte": 3})
    if hosting == "hybrid":
        facts["current_cloud_share_pct"] = int(rng.integers(10, 80))
    if rng.random() < 0.5:                                         # an architecture estimate, sometimes
        facts.update({"arch_effort_person_months": _range(rng, float(rng.choice([20, 60, 150]))),
                      "arch_external_cost": _range(rng, float(rng.choice([0, 100e3, 400e3])) + 1),
                      "arch_duration_months": _range(rng, float(rng.choice([6, 12, 24])))})
    gov = {f"GV{k:02d}": ({"answer": "Yes", "evidence": "Reference", "attested_by": "Sponsor"} if u < 0.7 else
                          {"answer": "Partly", "evidence": "", "attested_by": "Sponsor"} if u < 0.85 else
                          {"answer": "No", "evidence": "", "attested_by": "Sponsor"})
           for k, u in zip(range(1, 15), rng.random(14))}
    intent_kind = rng.choice(["full", "full", "full", "missing", "late"])
    intent = {"business_horizon": str(rng.choice(["grow", "hold", "shrink", "may_be_sold_or_closed"])),
              "stop_triggers": [{"trigger": "cost_overrun_pct", "value": int(rng.choice([20, 50, 100]))},
                                {"trigger": "sponsor_leaves"}],
              "funded_parallel_running_months": int(rng.choice([0, 3, 6, 12])),
              "spending_constraint": {"type": str(rng.choice(["none", "none", "capital_capped", "operating_capped", "both"])),
                                      "expires_on": "2027-12-31"},
              "prior_commitment": {"status": str(rng.choice(["none", "informal", "formal", "contractual"])),
                                   "detail": "A cloud migration announced to staff"},
              "committed_dates": [{"date": "2027-06-30", "what": "a regulatory reporting change"}] if rng.random() < 0.4 else []}
    if intent_kind == "late":
        intent["signed_on"] = "2026-10-20"
    labels = {}
    for item, options in {"PC01": ["No", "Yes, for hosting"], "BP02": ["No", "Yes, towards a change"],
                          "ABS": ["6–12 months", "Up to 1 month", "Not at all"], "LF01": ["5–10 years", "Less than 2 years"]}.items():
        if rng.random() < 0.25:
            labels[item] = str(rng.choice(options))
    sourcing = {}
    for k in range(int(rng.choice([0, 0, 1, 2, 3]))):
        sourcing[f"part{k}"] = {"name": ["Billing", "Search", "Document management"][k],
                                "differentiation": round(float(rng.uniform(1, 5)), 1),
                                "facts": {**BILLING, "product_coverage_pct": {"value": int(rng.choice([55, 80, 95])), "grade": "quote"},
                                          "product_data_export": str(rng.choice(["yes", "yes", "no"])),
                                          "part_shared_tables_pct": int(rng.choice([5, 30]))}}
    scenario = Scenario(f"org{i:03d}", {}, targets=targets, facts=facts, governance=gov, sizes=sizes, sourcing=sourcing,
                        labels=labels, current_hosting=str(hosting),
                        intent={} if intent_kind == "missing" else intent, system="the Core Platform")
    varied = {"hosting": str(hosting), "shape": str(shape), "sizes": sizes, "intent": str(intent_kind),
              "constraint": str(constraint), "parts": len(sourcing),
              "rules": "signed" if rng.random() < 0.75 else "unsigned"}
    return scenario, varied


def _finish(path: Path, varied: dict) -> None:
    """Sign the rules (or not), drop the intent sheet when missing, name people and a reviewer."""
    cfg = yaml.safe_load(path.read_text())
    if varied["intent"] == "missing":
        cfg.pop("intent", None)
    if varied["rules"] == "signed":
        rules = (INSTRUMENT / "decision_rules.yaml").read_text()
        rules = re.sub(r"^signed_off_by: .*$", 'signed_off_by: "Leadership team"', rules, count=1, flags=re.M)
        rules = re.sub(r"^signed_off_on: .*$", "signed_off_on: 2026-09-10", rules, count=1, flags=re.M)
        (path.parent / "decision_rules.yaml").write_text(rules)
        cfg["rules"] = "decision_rules.yaml"
    cfg["people"] = {"sponsor": "Chief Operating Officer", "fact_sheet_owner": "Head of Architecture",
                     "technology_lead": "CTO"}
    cfg["report"] = {"organisation": varied.get("name", "Generated"), "reviewed_by": "Reviewer", "reviewed_on": "2026-11-01"}
    path.write_text(yaml.safe_dump(cfg, sort_keys=False))


def invariants(a, ctx: dict) -> list[str]:
    """Promises the instrument makes, checked on one finished report context."""
    from .groups import for_engagement
    eng = a.engagement
    out = []
    min_n = eng.instrument.rules.get("evidence", {}).get("min_role_n", 5)
    sizes = for_engagement(eng).value_counts()
    shown = set()
    st = a.stakes
    if st:
        for d in st.preferences.values():
            shown |= set(d["by_group"])
        shown |= set(st.concern)
        for d in st.stakes_by_option.values():
            shown |= set(d)
    for side in (ctx.get("reported") or {}).get("sides", []):
        for row in side["rows"]:
            shown |= {x["group"] for x in row["answers"]}
            if any(x["n"] < min_n for x in row["answers"]):
                out.append("anonymity: a reported answer from fewer than the minimum")
    small = [g for g in shown - {"All respondents"} if sizes.get(g, 0) < min_n]
    if small:
        out.append(f"anonymity: group shown with fewer than {min_n} people")
    f = {k: v.point for k, v in eng.facts.items()}
    risky = (f.get("status_quo_compliance_findings") or 0) >= 1 or f.get("compensating_controls") == "yes" or \
        f.get("dr_test_result") in ("failed", "never_tested")
    host = a.results.get("hosting")
    if risky and host and host.verdict == "stay_as_is":
        out.append("risk of staying, yet hosting stays as it is")
    whichever = [s for s in ctx["steps"] if s["phase"] == "whichever_path"]
    expect = risky or f.get("dr_test_result") == "partial_scope"
    if expect and not whichever:
        out.append("risk of staying without a step required on every path")
    if whichever and not (expect or f.get("critical_function") == "yes"):
        out.append("a step required on every path without a risk behind it")
    brief = ctx.get("brief") or {}
    if not eng.intent and (brief.get("intent") or brief.get("intent_flags")):
        out.append("intent lines without an intent sheet")
    for r in ctx["risks"]["risks"]:
        if "can absorb" in r["title"]:
            res = a.results.get(r["decision"])
            if not res or not (res.verdict in MOVES or res.verdict not in ("insufficient_evidence", "stay_and_improve", "stay_as_is", "improve_current")):
                out.append("absorption risk without a programme")
    if f.get("past_savings_verified") in ("not_achieved", "never_checked"):
        for d, res in a.results.items():
            req = res.gates.get("required", {})
            if req and "savings" not in req:
                out.append(f"savings never verified, yet the savings gate is not required ({d})")
    nos = [s["no"] for s in ctx["steps"] if "no" in s]
    if len(nos) != len(set(nos)):
        out.append("step numbers repeat")
    integrity = ctx["integrity"]
    if a.engagement.config.get("rules") is None and not integrity["draft"]:
        out.append("unsigned rules, yet the report is final")
    return out


def _decision_page_fits(pdf: Path) -> bool | None:
    """True when the page after "Decision requested" opens with the executive summary (needs pdftotext)."""
    try:
        text = subprocess.run(["pdftotext", str(pdf), "-"], capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    pages = text.split("\f")
    start = next((i for i, p in enumerate(pages) if "Decision requested" in p and "Contents" not in p), None)
    if start is None or start + 1 >= len(pages):
        return None
    return any(line.strip() == "Executive summary" for line in pages[start + 1].split("\n")[:10])


def run(n: int = 40, seed: int = 1, pdf: int = 0, out: Path | None = None) -> dict:
    from .assess import assess
    from .report_v3 import build_context, build_report
    from .rubric import failures, run as rubric
    rng = np.random.default_rng(seed)
    out = Path(out or ROOT / "Output" / "stress")
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for i in range(n):
        scenario, varied = organisation(i, rng)
        varied["name"] = scenario.name
        row = {"org": scenario.name, **{k: v for k, v in varied.items() if k != "sizes"},
               "sizes": " ".join(f"{k}{v}" for k, v in varied["sizes"].items()), "problems": []}
        try:
            with tempfile.TemporaryDirectory() as tmp:
                path = build(scenario, Path(tmp) / "e", INSTRUMENT, seed=seed + i)
                _finish(path, varied)
                a = assess(path, draws=300)
                ctx = build_context(a, Path(tmp) / "o", ROOT)
                row["verdicts"] = {d: r.verdict for d, r in a.results.items()}
                row["draft"] = ctx["integrity"]["draft"]
                row["problems"] += [f"rubric: {x}" for x in failures(rubric(ctx))]
                row["problems"] += invariants(a, ctx)
                if i < pdf:
                    target = out / f"{scenario.name}.pdf"
                    build_report(a, target)
                    fits = _decision_page_fits(target)
                    row["decision_page_fits"] = fits
                    if fits is False:
                        row["problems"].append("decision page longer than one page")
        except Exception as exc:                        # a crash is a finding, with where it happened
            tb = traceback.extract_tb(exc.__traceback__)[-1]
            row["problems"].append(f"crash: {type(exc).__name__}: {exc} ({Path(tb.filename).name}:{tb.lineno})")
        rows.append(row)
    counts = Counter(re.sub(r"\d+(\.\d+)?", "#", p) for r in rows for p in r["problems"])
    (out / "stress.json").write_text(json.dumps(rows, indent=1, default=str))
    return {"rows": rows, "counts": counts}
