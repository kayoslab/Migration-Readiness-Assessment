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


TEXT = {
    "TEC": {
        "S08": ["A proof of concept showing that one service cannot be deployed independently would change my mind.",
                "If the cost of running many services clearly outweighed the delivery gains, I would reconsider.",
                "Evidence that teams already deploy independently today would make me less keen to split."],
        "S09": ["We will lose engineers who want to work with modern architectures, and features will keep slipping.",
                "Coordination overhead will grow with every team we add; the release train will get slower.",
                "Our competitors ship weekly; we ship monthly. Doing nothing means falling further behind."],
        "AL02": ["Checkout and pricing: every change touches the same tables and needs three teams to agree.",
                 "The order module: it is shared by everyone and nobody really owns it."],
    },
    "OPS": {
        "S08": ["Show me that the current platform cannot handle the load. It can, with room to spare.",
                "If the on-call burden of many services were properly staffed, I would be more open to it.",
                "A cost comparison that includes our time, not just licences, might change my view."],
        "S09": ["Nothing would break. The platform is stable; the problems are in how releases are approved.",
                "We would keep running a reliable system at a fraction of what a cloud setup would cost.",
                "Hardware gets old, but a planned refresh is cheaper than a migration."],
    },
    "ENG": {
        "S08": ["If we enforced module boundaries first and still could not deliver faster, splitting would make sense.",
                "Clear data ownership per team would change my view more than any new technology.",
                "Seeing how much time we lose waiting for other teams' changes would settle it."],
        "S09": ["The release train will keep getting slower as more teams pile onto the same codebase.",
                "Shared tables will keep causing incidents nobody owns.",
                "We will keep firefighting merge conflicts instead of building features."],
        "AL02": ["The shared order tables: three teams write to them and every schema change is a negotiation.",
                 "The pricing code, because nobody knows who owns it and changes break checkout.",
                 "Release coordination: our changes wait for unrelated fixes from other teams."],
    },
    "PRD": {
        "S08": ["If delivery dates stopped slipping because of other teams' changes, I would be happy to keep it.",
                "Proof that a restructuring pays back within a year would convince me."],
        "S09": ["Roadmap items will keep slipping and we will miss the peak season again.",
                "Customers will keep waiting for features our competitors already have."],
    },
    "BUS": {
        "S09": ["We cannot plan campaigns when release dates move every month.",
                "Reporting will stay manual because the data is locked in the platform."],
        "S10": ["Please explain the decision in terms of what changes for customers, not technology.",
                "We need a timeline we can plan around, whatever the decision."],
    },
    "FIN": {
        "S09": ["Running costs are predictable today; a move would make them less so.",
                "The hardware refresh is due; we need a decision before committing that budget."],
        "S10": ["Any business case must include the cost of running old and new side by side."],
    },
    "EXE": {
        "S08": ["If the team could show faster delivery without a large programme, that would be the better option."],
        "S09": ["We will keep missing commitments to the business, and that erodes trust in technology."],
    },
}


def stakes(role, index, rng, labels):
    answers = {k: v[index % len(v)] for k, v in TEXT.get(role, {}).items()}
    return {**answers, **_stakes(role, index, rng, labels)}


def _stakes(role, index, rng, labels):
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
    cfg["invited"] = {"ENG": 22, "PRD": 11, "BUS": 9, "TEC": 6, "EXE": 6, "OPS": 8, "SEC": 6, "FIN": 4}
    cfg["report"] = {"organisation": "TechCo", "title": "Architecture and Hosting Assessment",
                     "subtitle": "Recommended direction for the Order Platform", "prepared_for": "Executive Leadership Team",
                     "prepared_by": "Platform Advisory", "sample_data": True, "stakeholder_map": True}
    cfg["benchmark"] = {"industry": "technology", "organisation_size": "fewer_than_1000"}
    cfg["influence"] = {"EXE": "high", "TEC": "high", "FIN": "high", "PRD": "medium", "ENG": "medium",
                        "OPS": "medium", "BUS": "medium", "SEC": "medium"}
    path.write_text(yaml.safe_dump(cfg, sort_keys=False))
    print(f"Wrote {path}")
