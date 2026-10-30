"""Build the synthetic TechCo engagement in examples/techco (re-run to regenerate).

A mid-size e-commerce company: one monolith shared by eight teams, real coupling but heavily shared data;
own bare-metal hosting with steady load and room to right-size; a technology lead who favours microservices
and the cloud, and an operations team that favours keeping what it runs. Baseline metrics have not been
measured, so one precondition is missing.
"""

from pathlib import Path

import yaml

from mra.cases import STRONG_CAPABILITY, STRONG_CAPABILITY_FACTS
from mra.scenario import Scenario, build

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def stakes(role, index, rng, labels):
    arch, host = labels["architecture"], labels["hosting"]
    split, keep, modular = arch["broad_decomposition"], arch["stay_and_improve"], arch["modular_monolith"]
    cloud, stay = host["move_to_cloud"], host["stay_as_is"]
    if role == "TEC" and index < 4:
        return {"S01": split, "S02": cloud, f"S04[{split}]": "Increases it", f"S04[{modular}]": "No real change",
                f"S04[{keep}]": "Reduces it", f"S05[{split}]": "Helps", f"S05[{modular}]": "No real effect",
                f"S05[{keep}]": "No real effect", "AA02": "Strongly agree", "AA03": "Strongly agree"}
    if role == "OPS":
        return {"S01": keep, "S02": stay, f"S04[{split}]": "Reduces it", f"S04[{modular}]": "No real change",
                f"S04[{keep}]": "No real change", f"S05[{split}]": "Makes it harder", f"S05[{modular}]": "No real effect",
                f"S05[{keep}]": "No real effect", "S06": "Very much" if index % 2 else "Moderately",
                "AA02": "Disagree", "AA03": "Strongly disagree"}
    # everyone else: mostly mild concern and mixed, plausible preferences
    mild = {"S06": "A little" if index % 3 else "Not at all", "S06P": "A little" if index % 2 else "Moderately"}
    spread = [modular, keep, modular, "No preference", split][index % 5]
    host_spread = [host["improve_current"], stay, "No preference", host["hybrid"]][index % 4]
    if role == "ENG":
        return {**mild, "S01": spread, "S02": host_spread, "AA02": "Disagree", "AA03": "Disagree"}
    if role == "EXE":
        return {**mild, "S01": keep if index % 2 else modular, "S02": host["improve_current"],
                "AA02": "Agree", "AA03": "Strongly agree"}
    return {**mild, "S01": spread, "S02": host_spread}


TECHCO = Scenario(
    "techco", {"architecture": "modular_monolith", "hosting": "improve_current"},
    targets={**STRONG_CAPABILITY, "need.architecture.coupling": 3.8, "need.architecture.business_impact": 3.4,
             "need.architecture.cognitive_load": 3.6, "capability.architecture.data": 2.4, "fit.domain_ownership": 2.9,
             "fit.distributed_operations": 3.1, "locality.concentration": 2.2,
             "need.hosting.elasticity": 1.5, "need.hosting.capacity_lead_time": 2.0, "need.hosting.managed_services": 1.2,
             "capability.hosting.automation": 3.4, "capability.hosting.operations": 3.6,
             "capability.hosting.cloud_skills": 1.8, "capability.architecture.delivery_pipeline": 3.4},
    labels={"AN01": "Coordinating with other teams' changes"},
    facts={**STRONG_CAPABILITY_FACTS, "teams_per_deployable": 8, "cross_team_change_pct": 28, "blast_radius_pct": 22,
           "shared_tables_pct": 38, "cross_module_transactions": 9, "provision_days": 6, "domain_map": "outdated",
           "module_single_owner_pct": 55, "friction_concentration_index": 1.4,
           "peak_to_median_load": 1.6, "rightsized_share_pct": 55, "single_node_sufficient": "no",
           "cloud_compute_baseline_annual": {"low": 520000, "likely": 600000, "high": 720000, "grade": "calculator_export"}},
    governance={"GV06": {"answer": "No", "evidence": "", "attested_by": "CTO"},
                "GV07": {"answer": "Partly", "evidence": "Draft measures only", "attested_by": "Sponsor"}},
    sizes={"ENG": 18, "PRD": 9, "BUS": 6, "TEC": 6, "EXE": 5, "OPS": 7, "SEC": 4, "FIN": 3},
    respondent_fn=stakes,
)

if __name__ == "__main__":
    target = HERE / "techco"
    path = build(TECHCO, target, ROOT / "instrument", seed=11)
    cfg = yaml.safe_load(path.read_text())
    cfg["instrument"] = "../../instrument"
    cfg["report"] = {"organisation": "TechCo", "title": "Architecture and Hosting Assessment",
                     "subtitle": "Recommended direction for the Order Platform", "prepared_for": "Executive Leadership Team",
                     "prepared_by": "Platform Advisory", "sample_data": True}
    path.write_text(yaml.safe_dump(cfg, sort_keys=False))
    print(f"Wrote {path}")
