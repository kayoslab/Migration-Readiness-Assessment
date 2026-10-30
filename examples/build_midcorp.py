"""Build the synthetic MidCorp engagement in examples/midcorp (re-run to regenerate).

A deliberately messy case, to see how the report reads when the evidence does not line up: a regional insurer's
policy administration system, one deployable shared by five teams, with a need for change right at the threshold
between keeping it and restructuring it; own hosting with a hardware refresh eight months away and an invoiced run cost far above what the cost
model accounts for; decision rules signed off after the fact sheet was frozen; small groups for Operations,
Security, Finance and Executives; low response rates; funding not committed; no estimate for the restructuring; and
three build-or-buy candidates — one differentiating, one whose data cannot be exported, one at the coverage bar.
"""

from pathlib import Path

import yaml

from mra.cases import BILLING
from mra.scenario import Scenario, build

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

TEXT = {
    "OPS": {
        "S08": ["Approvals are the real bottleneck; the change board meets once a fortnight.",
                "Show me the outage numbers first; the system is stable."],
        "S09": ["The hardware contract runs out soon and we have to decide this quarter.",
                "Nothing breaks if we keep it; we just need the refresh approved."],
    },
    "ENG": {
        "S08": ["If we could release our module without waiting for the others, I would stop asking for a split.",
                "Fewer shared tables would change my mind more than any new platform."],
        "S09": ["Every quarterly release is a negotiation between six teams.",
                "We keep adding workarounds because the policy tables belong to everyone."],
    },
    "PRD": {
        "S09": ["New products take two quarters to launch because every change touches the core.",
                "Brokers keep asking for features the competitors already have."],
    },
    "EXE": {
        "S08": ["A credible cost for the restructuring would let me decide; today I have none.",
                "If the cloud really were cheaper for us, I would want to see the numbers."],
        "S09": ["We will keep paying for a system nobody wants to touch."],
    },
    "FIN": {
        "S09": ["The run cost keeps rising and nobody can tell me what is in it.",
                "The refresh budget is not approved; we cannot fund a migration on top."],
    },
}


def respondents(role, index, rng, labels):
    answers = {k: v[index % len(v)] for k, v in TEXT.get(role, {}).items()}
    arch, host = labels["architecture"], labels["hosting"]
    split, keep, modular = arch["broad_decomposition"], arch["stay_and_improve"], arch["modular_monolith"]
    cloud, stay, improve = host["move_to_cloud"], host["stay_as_is"], host["improve_current"]
    if role == "TEC":
        answers.update({"S01": [split, split, modular, split, modular][index % 5],
                        "S02": [cloud, cloud, improve, cloud, improve][index % 5]})
    elif role == "OPS":
        answers.update({"S01": keep, "S02": stay, "S06": "Very much" if index % 2 else "Moderately"})
    elif role == "PRD":                                   # split evenly: a tie
        answers.update({"S01": [modular, split][index % 2], "S02": [improve, cloud][index % 2]})
    elif role == "EXE":
        answers.update({"S01": [modular, keep][index % 2], "S02": [cloud, improve][index % 2]})
    else:
        answers.update({"S01": [modular, keep, split, "No preference"][index % 4],
                        "S02": [improve, stay, "No preference", cloud][index % 4]})
    return answers


DOCUMENTS = {**BILLING, "part_maintain_fte": {"low": 2, "likely": 2.5, "high": 3, "grade": "estimate"},
             "product_coverage_pct": {"low": 68, "likely": 80, "high": 90, "grade": "estimate"},
             "product_licence_annual": {"value": 70000, "grade": "quote"}}

MIDCORP = Scenario(
    "midcorp", {},
    system="the Policy Administration System",
    targets={"need.architecture.coupling": 3.1, "need.architecture.business_impact": 2.9,
             "need.architecture.cognitive_load": 2.8, "capability.architecture.delivery_pipeline": 2.9,
             "capability.architecture.data": 2.2, "fit.domain_ownership": 2.6, "fit.distributed_operations": 2.7,
             "need.hosting.elasticity": 2.2, "need.hosting.capacity_lead_time": 3.0, "need.hosting.managed_services": 2.0,
             "capability.hosting.automation": 2.6, "capability.hosting.operations": 3.2,
             "capability.hosting.cloud_skills": 2.2},
    facts={"teams_per_deployable": 5, "cross_team_change_pct": 18, "blast_radius_pct": 14, "shared_tables_pct": 44,
           "cross_module_transactions": 12, "provision_days": 15, "domain_map": "none", "module_single_owner_pct": 40,
           "friction_concentration_index": 1.3, "deploys_per_week": 0.25, "lead_time_hours": 900,
           "change_failure_pct": 18, "restore_hours": 30, "deploy_automation": "manual_steps", "rollback_minutes": 45,
           "run_cost_annual": {"low": 1800000, "likely": 2000000, "high": 2400000, "grade": "invoice"},
           "hw_refresh_due_months": 8, "hw_refresh_capex": 600000, "contract_end_months": 14,
           "rightsized_share_pct": 75, "iac_pct": 25, "infra_bus_factor": 2, "capacity_lead_time_weeks": 9,
           "cloud_compute_baseline_annual": {"low": 380000, "likely": 450000, "high": 600000, "grade": "calculator_export"}},
    sourcing={
        "rating": {"name": "Policy rating engine", "differentiation": 4.4,
                   "facts": {**BILLING, "part_maintain_fte": {"low": 5, "likely": 6, "high": 8, "grade": "estimate"},
                             "product_licence_annual": {"value": 260000, "grade": "quote"},
                             "product_coverage_pct": {"value": 60, "grade": "quote"}}},
        "claims": {"name": "Claims portal", "differentiation": 1.8,
                   "facts": {**BILLING, "part_maintain_fte": {"low": 2.5, "likely": 3, "high": 4, "grade": "estimate"},
                             "product_licence_annual": {"value": 110000, "grade": "quote"},
                             "product_data_export": "no"}},
        "documents": {"name": "Document management", "differentiation": 1.7, "facts": DOCUMENTS},
    },
    governance={"GV03": {"answer": "No", "evidence": "", "attested_by": "CFO"},
                "GV06": {"answer": "Partly", "evidence": "Lead time only", "attested_by": "CTO"},
                "GV07": {"answer": "No", "evidence": "", "attested_by": "Sponsor"},
                "GV13": {"answer": "Partly", "evidence": "Export not yet tested", "attested_by": "Risk and compliance"}},
    sizes={"ENG": 12, "PRD": 6, "BUS": 5, "TEC": 5, "EXE": 4, "OPS": 4, "SEC": 2, "FIN": 3},
    respondent_fn=respondents,
)

if __name__ == "__main__":
    target = HERE / "midcorp"
    path = build(MIDCORP, target, ROOT / "instrument", seed=23)
    cfg = yaml.safe_load(path.read_text())
    cfg["instrument"] = "../../instrument"
    cfg["invited"] = {"ENG": 35, "PRD": 14, "BUS": 18, "TEC": 7, "EXE": 8, "OPS": 9, "SEC": 6, "FIN": 7}
    cfg["report"] = {"organisation": "MidCorp Insurance", "title": "Architecture and Hosting Assessment",
                     "subtitle": "Recommended direction for the Policy Administration System",
                     "prepared_for": "Management Board", "prepared_by": "Internal Transformation Office",
                     "sample_data": True}
    cfg["benchmark"] = {"industry": "insurance", "organisation_size": "fewer_than_5000"}
    cfg["people"] = {**cfg.get("people", {}), "sponsor": "Chief Operating Officer", "technology_lead": "CIO",
                     "fact_sheet_owner": "Head of IT Architecture"}
    # rules signed off after the fact sheet was frozen (2026-10-01): the report must stay a draft
    import re
    rules = (ROOT / "instrument" / "decision_rules.yaml").read_text()
    rules = re.sub(r"^signed_off_by: .*$", 'signed_off_by: "Management Board (sample)"', rules, count=1, flags=re.M)
    rules = re.sub(r"^signed_off_on: .*$", "signed_off_on: 2026-10-12", rules, count=1, flags=re.M)
    (path.parent / "decision_rules.yaml").write_text(rules)
    cfg["rules"] = "decision_rules.yaml"
    path.write_text(yaml.safe_dump(cfg, sort_keys=False))
    print(f"Wrote {path}")
