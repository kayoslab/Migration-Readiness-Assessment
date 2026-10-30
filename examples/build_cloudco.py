"""Build the synthetic CloudCo engagement in examples/cloudco (re-run to regenerate).

A software-as-a-service scale-up that split early: about 40 services run by seven teams on a public cloud. Releases
often need several services deployed together and many changes cross service boundaries; the cloud bill is high for
a steady load, mostly on demand. One part — search — is a commodity a product covers well. Evidence is sound, the
rules were signed off in time and the report has been reviewed: this is the clean counterpart to MidCorp, on the
paths TechCo does not take (distributed architecture, cloud hosting).
"""

import re
from pathlib import Path

import yaml

from mra.cases import BILLING
from mra.scenario import Scenario, build

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

TEXT = {
    "ENG": {
        "S08": ["If each team could deploy its services without coordinating with three others, I would keep them.",
                "Fewer services with clear owners would change my mind about another split."],
        "S09": ["Every release train needs a war room because twelve services move together.",
                "We spend more time on service plumbing than on the product."],
    },
    "OPS": {
        "S08": ["Committed-use discounts and right-sizing would change the cost picture before any move."],
        "S09": ["The bill keeps growing while the load is flat.", "On-call for forty services is wearing people out."],
    },
    "FIN": {
        "S09": ["Cloud spend grew faster than revenue for two years.", "Nobody owns the cloud bill line by line."],
    },
    "TEC": {
        "S08": ["Evidence that teams already deploy independently would make me less keen to merge services."],
        "S09": ["Merging services is a step backwards for a cloud-native company."],
    },
}


def respondents(role, index, rng, labels):
    answers = {k: v[index % len(v)] for k, v in TEXT.get(role, {}).items()}
    arch, host = labels["architecture"], labels["hosting"]
    merge = arch.get("consolidate")
    realign = arch.get("realign_services")
    optimise, stay = host["improve_current"], host["stay_as_is"]
    back = host.get("repatriate")
    if role == "TEC":
        answers.update({"S01": [realign, realign, merge][index % 3], "S02": [stay, optimise][index % 2]})
    elif role in ("ENG", "OPS"):
        answers.update({"S01": [merge, merge, realign][index % 3], "S02": [optimise, optimise, back][index % 3]})
    elif role == "FIN":
        answers.update({"S01": "No preference", "S02": [back, optimise][index % 2]})
    else:
        answers.update({"S01": [merge, realign, "No preference"][index % 3], "S02": [optimise, stay][index % 2]})
    return answers


CLOUDCO = Scenario(
    "cloudco", {"architecture": "consolidate", "hosting": "improve_current"},
    system="the CloudCo platform",
    current_hosting="cloud",
    targets={"need.architecture.coupling": 3.9, "need.architecture.cognitive_load": 4.0,
             "capability.architecture.delivery_pipeline": 4.0, "fit.distributed_operations": 3.6,
             "need.hosting.elasticity": 1.6, "need.hosting.capacity_lead_time": 1.2, "need.hosting.managed_services": 2.4,
             "capability.hosting.automation": 4.3, "capability.hosting.operations": 3.8, "capability.hosting.cloud_skills": 4.2,
             "capability.hosting.onprem_ops": 1.4},
    labels={"AN01": "Waiting for a release window or release train"},
    facts={"deployables_in_scope": 40, "core_code_share_pct": 9, "services_per_team": 5.7, "lockstep_deploy_pct": 38,
           "cross_service_change_pct": 34, "teams_per_deployable": 3, "deploys_per_week": 12, "lead_time_hours": 30,
           "change_failure_pct": 9, "restore_hours": 2, "deploy_automation": "automatic_on_merge",
           "peak_to_median_load": 1.5, "need_share_pct": 15, "rightsized_share_pct": 65, "ops_fte": 5,
           "infra_share_pct": 40, "infra_oncall_people": 6, "target_model": "colocation",
           "cloud_compute_baseline_annual": {"low": 900000, "likely": 980000, "high": 1080000, "grade": "invoice"},
           "cloud_committed_share_pct": 15, "cloud_commit_discount_pct": 35, "cloud_ops_fte": 3,
           "hw_maintenance_annual": 60000, "dc_cost_annual": 140000, "network_transit_annual": 40000,
           "dr_site_annual": 60000, "licence_cost_annual": 30000, "hw_refresh_capex": 700000, "residual_value": 150000,
           "migration_cost": {"low": 400000, "likely": 500000, "high": 800000, "grade": "estimate"},
           "migration_months": {"low": 10, "likely": 12, "high": 18, "grade": "estimate"},
           "sunk_commitment_cost": 0, "cloud_commitment_end_months": 0,
           "run_cost_annual": {"low": 1350000, "likely": 1450000, "high": 1550000, "grade": "invoice"}},
    sourcing={"search": {"name": "Search", "differentiation": 1.7,
                         "facts": {**BILLING, "part_maintain_fte": {"low": 2.5, "likely": 3, "high": 3.5, "grade": "estimate"},
                                   "product_licence_annual": {"value": 70000, "grade": "quote"},
                                   "product_coverage_pct": {"value": 90, "grade": "quote"},
                                   "part_shared_tables_pct": 5}}},
    sizes={"ENG": 24, "PRD": 10, "BUS": 8, "TEC": 6, "EXE": 5, "OPS": 8, "SEC": 6, "FIN": 5},
    respondent_fn=respondents,
)

if __name__ == "__main__":
    target = HERE / "cloudco"
    path = build(CLOUDCO, target, ROOT / "instrument", seed=31)
    cfg = yaml.safe_load(path.read_text())
    cfg["instrument"] = "../../instrument"
    cfg["invited"] = {"ENG": 28, "PRD": 11, "BUS": 9, "TEC": 6, "EXE": 5, "OPS": 9, "SEC": 6, "FIN": 6}
    cfg["report"] = {"organisation": "CloudCo", "title": "Architecture and Hosting Assessment",
                     "subtitle": "Recommended direction for the CloudCo platform", "prepared_for": "Leadership team",
                     "prepared_by": "Platform Advisory", "sample_data": True, "stakeholder_map": True,
                     "reviewed_by": "Engagement quality reviewer (sample)", "reviewed_on": "2026-10-29"}
    cfg["benchmark"] = {"industry": "technology", "organisation_size": "fewer_than_500"}
    cfg["people"] = {**cfg.get("people", {}), "sponsor": "Chief Executive Officer", "technology_lead": "CTO",
                     "platform_lead": "Head of Platform", "fact_sheet_owner": "Head of Engineering"}
    rules = (ROOT / "instrument" / "decision_rules.yaml").read_text()
    rules = re.sub(r"^signed_off_by: .*$", 'signed_off_by: "Leadership team (sample)"', rules, count=1, flags=re.M)
    rules = re.sub(r"^signed_off_on: .*$", "signed_off_on: 2026-09-20", rules, count=1, flags=re.M)
    (path.parent / "decision_rules.yaml").write_text(rules)
    cfg["rules"] = "decision_rules.yaml"
    path.write_text(yaml.safe_dump(cfg, sort_keys=False))
    print(f"Wrote {path}")
