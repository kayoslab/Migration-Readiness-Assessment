"""Synthetic engagements with a known correct outcome (seed of the M5 simulator).

A scenario sets target scores per survey sub-area ("need.architecture.coupling": 4.2), labels for unscored items
(AN01 lead-time driver), fact values, governance answers and group sizes. Each simulated respondent answers
every item in their group's form by picking the option whose score is nearest to the target plus personal noise,
and the result is written exactly like a Google Forms export.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import yaml

from .axes import derive_current_state
from .engagement import Fact, write_form_exports
from .instrument import DONT_KNOW, Instrument, load_instrument

DEFAULT_SIZES = {"ENG": 15, "PRD": 8, "BUS": 6, "TEC": 5, "EXE": 5, "OPS": 6, "SEC": 5, "FIN": 5}

HEALTHY_FACTS = {
    "deployables_in_scope": 1, "core_code_share_pct": 100, "single_node_sufficient": "no",
    "teams_per_deployable": 4, "cross_team_change_pct": 12, "blast_radius_pct": 15,
    "components_distinct_load": 0, "components_distinct_availability": 0, "components_distinct_compliance": 0,
    "friction_concentration_index": 1.3,
    "deploy_automation": "team_triggered", "rollback_minutes": 10, "test_automation_pct": 70, "change_failure_pct": 12,
    "restore_hours": 4, "deploys_per_week": 3, "lead_time_hours": 72, "logs_and_metrics": "yes",
    "platform_basics_count": 3, "provision_days": 5, "oncall_model": "sre_escalating",
    "shared_tables_pct": 25, "cross_module_transactions": 4,
    "module_single_owner_pct": 60, "domain_map": "outdated", "degraded_mode_features": "partly",
    "run_cost_annual": {"low": 800000, "likely": 1000000, "high": 1300000, "grade": "invoice"},
    "acceptable_run_cost_increase_pct": 20,
    "target_run_cost_increase_pct": {"low": 15, "likely": 25, "high": 40, "grade": "estimate"},
}

# A mid-size own estate (~0.5 M/yr) where a like-for-like cloud setup costs moderately more.
HOSTING_FACTS = {
    "fte_cost_annual": 100000, "growth_pct_annual": 5, "own_price_change_pct_annual": 3,
    "cloud_price_change_pct_annual": 2, "discount_rate_pct": 6, "ops_fte": 4, "infra_share_pct": 60,
    "hw_maintenance_annual": 60000, "dc_cost_annual": 80000, "network_transit_annual": 20000,
    "dr_site_annual": 40000, "licence_cost_annual": 50000,
    "hw_refresh_capex": 400000, "hw_refresh_due_months": 30, "residual_value": 120000,
    "rightsized_share_pct": 90, "automation_investment": 50000, "toil_reduction_pct": 15,
    "cloud_compute_baseline_annual": {"low": 260000, "likely": 300000, "high": 380000, "grade": "calculator_export"},
    "cloud_committed_share_pct": 60, "cloud_commit_discount_pct": 35, "cloud_peak_cost_annual": 30000,
    "cloud_egress_annual": 30000, "cloud_network_internal_annual": 25000, "cloud_support_tooling_annual": 30000,
    "cloud_managed_annual": 20000, "cloud_dr_annual": 30000, "cloud_ops_fte": 3,
    "migration_cost": {"low": 250000, "likely": 300000, "high": 500000, "grade": "estimate"},
    "migration_months": {"low": 10, "likely": 12, "high": 18, "grade": "estimate"},
    "dual_run_months": {"low": 2, "likely": 3, "high": 6, "grade": "estimate"},
    "training_hiring_cost": 50000, "exit_cost": 100000, "bridge_cost": 80000,
    "need_share_pct": 30, "hybrid_interconnect_annual": 30000, "hybrid_overhead_fte": 0.5,
    "accepted_premium_pct": 0, "peak_hours_per_year": 200, "average_utilisation_pct": 40,
    "peak_to_median_load": 1.8, "capacity_lead_time_weeks": 4, "infra_toil_pct": 12, "regions_required": 1,
    "managed_services_required": 0, "hosting_constraint": "any",
    "iac_pct": 60, "infra_bus_factor": 3, "dr_restore_tested_months": 4, "infra_oncall_people": 5,
    "contract_end_months": 36,
}

ALL_YES = {f"GV{i:02d}": {"answer": "Yes", "evidence": "Reference document", "attested_by": "Sponsor"} for i in range(1, 13)}


@dataclass
class Scenario:
    name: str
    expected: dict[str, str | set]                       # decision -> outcome id (or set of acceptable ids)
    targets: dict[str, float] = field(default_factory=dict)
    labels: dict[str, str] = field(default_factory=dict)   # item id -> fixed label for every respondent
    facts: dict = field(default_factory=dict)
    governance: dict = field(default_factory=dict)
    sizes: dict[str, int] = field(default_factory=dict)
    noise: float = 0.5
    system: str = "the Order Platform"
    current_hosting: str = "own_infrastructure"
    # per-respondent overrides: fn(role, index, rng, labels) -> {"S01": label, "S04[<row>]": label, ...}
    # `labels` maps decision -> outcome id -> the preference label offered for the current state
    respondent_fn: Callable | None = None


def _area_key(ins: Instrument, item_id: str) -> list[str]:
    it = ins.items.loc[item_id]
    if it["block"] in ("fit", "requirement", "locality"):
        return [f"{it['block']}.{it['area']}"]
    decisions = ["architecture", "hosting"] if it["decision"] == "both" else [it["decision"]]
    return [f"{it['block']}.{d}.{it['area']}" for d in decisions] + [f"{it['block']}.{it['area']}"]


def _answer(ins: Instrument, q: dict, target: float | None, fixed: str | None, rng) -> str:
    if fixed is not None:
        return fixed
    if q["format"] == "text":
        return ""
    choices = [o for o in q["options"] if o != DONT_KNOW and o != ins.items.at[q["item_id"], "not_applicable"]]
    if q["row"] is not None:                                  # grids
        if ins.items.at[q["item_id"], "scored"] != "true":
            return choices[rng.integers(len(choices))]
        if target is None:
            return "No"
        return "Yes" if rng.random() < np.clip((target - 1) / 4, 0, 1) else "No"
    scores = ins.scores(q["item_id"])
    if not isinstance(scores, dict):
        return choices[rng.integers(len(choices))]
    if target is None:
        target = 3.0
    wanted = target + rng.normal(0, 0.5)
    return min(scores, key=lambda label: (abs(scores[label] - wanted), rng.random()))


def build(scenario: Scenario, root: Path, instrument_dir: str | Path, seed: int = 7) -> Path:
    """Write the scenario as an engagement folder and return the path of its engagement.yaml."""
    rng = np.random.default_rng(seed)
    root.mkdir(parents=True, exist_ok=True)
    ins = load_instrument(instrument_dir)
    facts = {**HEALTHY_FACTS, **HOSTING_FACTS, **scenario.facts}
    fact_objs = {k: Fact(**(v if isinstance(v, dict) else {"value": v})) for k, v in facts.items() if v is not None}
    current = {"architecture": derive_current_state(ins, fact_objs), "hosting": scenario.current_hosting}

    labels = {d: {oid: label for oid, label in ins.preference_options(d, current[d])} for d in ("architecture", "hosting")}
    answers = {}
    for role, n in {**DEFAULT_SIZES, **scenario.sizes}.items():
        spec = ins.form_spec(role, scenario.system, current)
        people = []
        for index in range(n):
            offset = rng.normal(0, scenario.noise)            # each person's general optimism
            person = {}
            for q in spec:
                keys = _area_key(ins, q["item_id"]) + [f"item.{q['item_id']}"]
                target = next((scenario.targets[k] for k in keys if k in scenario.targets), None)
                fixed = scenario.labels.get(q["item_id"])
                if q["item_id"] == "CX02" and fixed is None:
                    fixed = q["options"][0] if role in ("ENG", "OPS", "TEC") else q["options"][1]
                if q["item_id"] == "G14" and fixed is None:
                    fixed = "No"
                key = q["item_id"] if q["row"] is None else f"{q['item_id']}[{q['row']}]"
                person[key] = _answer(ins, q, None if target is None else target + offset, fixed, rng)
            if scenario.respondent_fn:
                person.update(scenario.respondent_fn(role, index, rng, labels))
            people.append(person)
        answers[role] = people
    files = write_form_exports(root, ins, scenario.system, current, answers)

    (root / "facts.yaml").write_text(yaml.safe_dump({k: (v if isinstance(v, dict) else {"value": v})
                                                     for k, v in facts.items() if v is not None}, sort_keys=False))
    (root / "governance.yaml").write_text(yaml.safe_dump({**ALL_YES, **scenario.governance}, sort_keys=False))
    config = {"system": scenario.system, "current_hosting": scenario.current_hosting,
              "instrument": str(Path(instrument_dir).resolve()), "responses": files,
              "facts": "facts.yaml", "governance": "governance.yaml"}
    path = root / "engagement.yaml"
    path.write_text(yaml.safe_dump(config, sort_keys=False))
    return path
