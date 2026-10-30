"""The expert panel's walk-through cases with known correct outcomes (shared by tests and the simulator).

Architecture cases come from the architecture / organisational-change review, hosting cases from the
hosting / FinOps review (docs/phase-2-plan.md, M0). Each expected outcome is the experts' judgement, not the
engine's output.
"""

from .scenario import Scenario

# ---------------------------------------------------------------------------------------- shared scenario parts
STRONG_CAPABILITY = {
    "capability.architecture.delivery_pipeline": 4.3, "capability.architecture.platform_basics": 4.5,
    "capability.architecture.platform_distribution": 4.5, "capability.architecture.operations": 4.5,
    "capability.architecture.data": 4.0, "fit.domain_ownership": 4.5, "fit.distributed_operations": 4.4,
    "requirement.consistency_tolerance": 4.0,
}
STRONG_CAPABILITY_FACTS = {
    "deploy_automation": "automatic_on_merge", "test_automation_pct": 88, "change_failure_pct": 6, "rollback_minutes": 5,
    "platform_basics_count": 4, "provision_days": 0.5, "oncall_model": "owning_team", "module_single_owner_pct": 90,
    "domain_map": "current", "degraded_mode_features": "yes", "acceptable_run_cost_increase_pct": 35,
}
HIGH_DIFFUSE_NEED = {"need.architecture.coupling": 4.5, "need.architecture.business_impact": 4.0,
                     "need.architecture.cognitive_load": 4.0, "locality.concentration": 2.0}
HIGH_DIFFUSE_NEED_FACTS = {"teams_per_deployable": 15, "cross_team_change_pct": 40, "blast_radius_pct": 30,
                           "friction_concentration_index": 1.2}
LOW_NEED = {"need.architecture.coupling": 1.5, "need.architecture.business_impact": 1.6,
            "need.architecture.cognitive_load": 1.5, "locality.concentration": 2.0}
LOW_NEED_FACTS = {"teams_per_deployable": 2, "cross_team_change_pct": 5, "blast_radius_pct": 8}

ARCHITECTURE_CASES = {
    # (a) 25 engineers, 3 teams, CAB approvals, manual QA, little contention
    "a_small_team_process_waits": Scenario(
        "a", {"architecture": "stay_and_improve"},
        targets={**LOW_NEED, "capability.architecture.delivery_pipeline": 1.8},
        labels={"AN01": "Approvals (e.g. change advisory board)"},
        facts={**LOW_NEED_FACTS, "teams_per_deployable": 3, "deploy_automation": "manual_steps",
               "rollback_minutes": 180, "test_automation_pct": 20, "change_failure_pct": 28}),
    # (b) 15 teams on one deployable, strong platform, but 45% shared tables
    "b_coupled_shared_data": Scenario(
        "b", {"architecture": "modular_monolith"},
        targets={**HIGH_DIFFUSE_NEED, **STRONG_CAPABILITY, "capability.architecture.data": 2.0},
        labels={"AN01": "Waiting for a release window or release train"},
        facts={**HIGH_DIFFUSE_NEED_FACTS, **STRONG_CAPABILITY_FACTS, "shared_tables_pct": 45,
               "cross_module_transactions": 15}),
    # (c) as (b) with separable data, self-service platform, team-owned on-call, cost within tolerance
    "c_ready_to_decompose": Scenario(
        "c", {"architecture": "broad_decomposition"},
        targets={**HIGH_DIFFUSE_NEED, **STRONG_CAPABILITY},
        labels={"AN01": "Coordinating with other teams' changes"},
        facts={**HIGH_DIFFUSE_NEED_FACTS, **STRONG_CAPABILITY_FACTS, "shared_tables_pct": 12,
               "cross_module_transactions": 2}),
    # (d) payment component in PCI scope causing incidents; otherwise healthy
    "d_pci_component": Scenario(
        "d", {"architecture": "targeted_extraction"},
        targets={"need.architecture.coupling": 2.6, "need.architecture.business_impact": 2.5,
                 "capability.architecture.delivery_pipeline": 3.8, "capability.architecture.platform_basics": 4.0,
                 "fit.distributed_operations": 3.6},
        facts={"teams_per_deployable": 6, "cross_team_change_pct": 14, "components_distinct_compliance": 1,
               "components_distinct_load": 1, "candidate_scope_in_main_deployable": "yes",
               "candidate_incident_share_pct": 45, "candidate_scaling_cost_share_pct": 30,
               "candidate_shared_tables_pct": 4, "rollback_minutes": 8, "platform_basics_count": 4}),
    # (e) 8 engineers running 35 services that are mostly released together
    "e_over_split": Scenario(
        "e", {"architecture": "consolidate"},
        targets={"need.architecture.coupling": 4.0},
        facts={"deployables_in_scope": 35, "core_code_share_pct": 8, "services_per_team": 17,
               "lockstep_deploy_pct": 60, "cross_service_change_pct": 45, "teams_per_deployable": 2},
        sizes={"ENG": 8}),
    # (g) head of platform wants change; the platform fits on one machine; an SLO tier exists but causes no pain
    "g_enthusiasm_without_need": Scenario(
        "g", {"architecture": "stay_and_improve"},
        targets={**LOW_NEED, "need.architecture.business_impact": 4.2,           # leadership enthusiasm
                 "capability.architecture.delivery_pipeline": 3.5},
        facts={**LOW_NEED_FACTS, "single_node_sufficient": "yes", "components_distinct_load": 1,
               "components_distinct_availability": 1, "candidate_incident_share_pct": 3,
               "candidate_scope_in_main_deployable": "not_applicable", "candidate_scaling_cost_share_pct": 2,
               "candidate_shared_tables_pct": 30}),
}


GOOD_OPS = {"capability.hosting.automation": 4.0, "capability.hosting.operations": 4.0,
            "capability.hosting.cost_discipline": 3.5, "need.hosting.ops_burden": 1.5}
STEADY = {"need.hosting.elasticity": 1.3, "need.hosting.capacity_lead_time": 1.5, "need.hosting.managed_services": 1.0}

HOSTING_CASES = {
    # (a) head of platform wants the cloud; load is steady, one machine would do, cloud ~3x, team against
    "a_steady_load_one_machine": Scenario(
        "a", {"hosting": "improve_current"},
        targets={**STEADY, **GOOD_OPS, "capability.hosting.cloud_skills": 2.0},
        facts={"peak_to_median_load": 1.3, "rightsized_share_pct": 30, "iac_pct": 70, "single_node_sufficient": "yes",
               "cloud_compute_baseline_annual": {"low": 800000, "likely": 900000, "high": 1100000, "grade": "calculator_export"}}),
    # (b) e-commerce with 15x seasonal peaks, hardware end of life in 9 months, little infrastructure as code
    "b_peaks_eol_low_iac": Scenario(
        "b", {"hosting": "move_to_cloud"},
        targets={"need.hosting.elasticity": 4.8, "need.hosting.capacity_lead_time": 4.5,
                 "capability.hosting.automation": 2.0, "capability.hosting.operations": 2.8,
                 "capability.hosting.cloud_skills": 2.0},
        # a need-motivated move: leadership pre-registers that it accepts up to 10% more cost for elasticity
        facts={"peak_to_median_load": 15, "capacity_lead_time_weeks": 10, "iac_pct": 20, "need_share_pct": 75,
               "hw_refresh_due_months": 9, "rightsized_share_pct": 95, "accepted_premium_pct": 10,
               "hw_maintenance_annual": 180000, "dc_cost_annual": 240000, "dr_site_annual": 120000,
               "hw_refresh_capex": 1200000, "residual_value": 300000,
               "cloud_compute_baseline_annual": {"low": 220000, "likely": 250000, "high": 300000, "grade": "calculator_export"},
               "cloud_peak_cost_annual": 150000, "migration_months": {"low": 12, "likely": 14, "high": 20, "grade": "estimate"}}),
    # (c) SaaS already in the cloud, steady load, cloud bill several times colocation, three platform engineers
    "c_saas_cloud_overpaying": Scenario(
        "c", {"hosting": "repatriate"},
        targets={**STEADY, "capability.hosting.automation": 4.2, "capability.hosting.onprem_ops": 1.2},
        current_hosting="cloud",
        facts={"peak_to_median_load": 1.4, "need_share_pct": 10, "rightsized_share_pct": 70, "infra_oncall_people": 3,
               "target_model": "managed_dedicated", "ops_fte": 3, "infra_share_pct": 50,
               "cloud_compute_baseline_annual": {"low": 550000, "likely": 600000, "high": 680000, "grade": "invoice"},
               "cloud_committed_share_pct": 20, "cloud_ops_fte": 2,
               "hw_maintenance_annual": 30000, "dc_cost_annual": 60000, "network_transit_annual": 15000,
               "dr_site_annual": 25000, "licence_cost_annual": 10000, "hw_refresh_capex": 250000, "residual_value": 80000,
               "migration_cost": {"low": 120000, "likely": 150000, "high": 250000, "grade": "estimate"},
               "migration_months": {"low": 5, "likely": 6, "high": 9, "grade": "estimate"},
               "sunk_commitment_cost": 0, "cloud_commitment_end_months": 0}),
    # (d) regulated bank: in-country residency, mixed load, strong operations, cloud dearer
    "d_regulated_strong_ops": Scenario(
        "d", {"hosting": "stay_as_is"},
        targets={"need.hosting.elasticity": 2.5, "need.hosting.capacity_lead_time": 2.0, **GOOD_OPS,
                 "capability.hosting.onprem_ops": 4.5},
        facts={"hosting_constraint": "in_country", "peak_to_median_load": 2.5, "iac_pct": 85, "infra_bus_factor": 5,
               "rightsized_share_pct": 95}),
    # (e) media company: global low-latency delivery for a small part of the estate, steady core
    "e_global_reach_partial": Scenario(
        "e", {"hosting": "hybrid"},
        targets={**STEADY, **GOOD_OPS, "need.hosting.managed_services": 4.0},
        # global delivery is bought as CDN/edge capacity: no compute moves, so no interconnect, little migration
        facts={"regions_required": 4, "managed_services_required": 2, "need_share_pct": 10, "accepted_premium_pct": 15,
               "rightsized_share_pct": 95, "peak_to_median_load": 1.5, "hybrid_interconnect_annual": 0,
               "hybrid_overhead_fte": 0.2, "training_hiring_cost": 10000}),
    # symmetry: no specific need, but the cloud is clearly cheaper and pays back quickly → cost-motivated move
    "f_cloud_clearly_cheaper": Scenario(
        "f", {"hosting": "move_to_cloud"},
        targets={**STEADY, **GOOD_OPS, "capability.hosting.cloud_skills": 3.5},
        facts={"ops_fte": 6, "infra_share_pct": 100, "hw_maintenance_annual": 200000, "dc_cost_annual": 260000,
               "dr_site_annual": 140000, "hw_refresh_capex": 900000, "hw_refresh_due_months": 14, "rightsized_share_pct": 95,
               "cloud_compute_baseline_annual": {"low": 180000, "likely": 200000, "high": 240000, "grade": "quote"},
               "cloud_ops_fte": 2, "migration_cost": {"low": 150000, "likely": 180000, "high": 260000, "grade": "quote"},
               "migration_months": {"low": 5, "likely": 6, "high": 9, "grade": "estimate"}}),
}

HOSTING_STATUS = {"b_peaks_eol_low_iac": "prepare_first", "c_saas_cloud_overpaying": "prepare_first"}


ARCHITECTURE_STATUS: dict[str, str] = {}


def expected(case: str) -> tuple[str, str, str]:
    """(decision, outcome, status) expected for a case."""
    if case in ARCHITECTURE_CASES:
        return "architecture", ARCHITECTURE_CASES[case].expected["architecture"], ARCHITECTURE_STATUS.get(case, "go")
    return "hosting", HOSTING_CASES[case].expected["hosting"], HOSTING_STATUS.get(case, "go")


ALL_CASES = {**ARCHITECTURE_CASES, **HOSTING_CASES}
