"""Simulator: validity and reliability of the decision engine on synthetic engagements (M5).

Two questions, kept separate:

1. Validity — `grid`: the expert walk-through cases (mra/cases.py) across group sizes, response noise and seeds.
   Truth is the experts' expected outcome.
2. Reliability near thresholds — `sweep`: a scenario family moved continuously across a threshold. Truth at
   each point is what the rules give for the whole population: the same answering process (including noise and
   rounding to answer options) with 100 respondents per group. The question is how often a realistic sample
   reproduces it, says "insufficient evidence", or gives a different (wrong) outcome. This measures sampling
   behaviour, not whether the rules are right — the grid covers that.

Each run stores its full outcome distribution, so other confidence levels can be evaluated afterwards
(`at_confidence`) without re-running.
"""

from __future__ import annotations

import copy
import shutil
import tempfile
from collections.abc import Callable, Iterable
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .cases import ALL_CASES, expected
from .scenario import Scenario, build

ROOT = Path(__file__).resolve().parents[1]
INSTRUMENT = ROOT / "instrument"


@dataclass(frozen=True)
class Run:
    case: str
    decision: str
    truth: str
    truth_status: str
    group_size: int
    noise: float
    seed: int
    t: float | None = None          # sweep position
    instrument: str = str(INSTRUMENT)
    truth_leaning: str | None = None   # when the truth itself is "insufficient evidence", the outcome it leans to


def _execute(args) -> dict:
    run, scenario, draws = args
    from .assess import assess
    work = Path(tempfile.mkdtemp(prefix="mra-sim-"))
    try:
        path = build(scenario, work, run.instrument, seed=run.seed, group_size=run.group_size)
        a = assess(path, decisions=(run.decision,), draws=draws, seed=run.seed)
        r = a.results[run.decision]
        return {**run.__dict__, "verdict": r.verdict, "status": r.status, "probability": r.probability,
                "distribution": r.distribution, "leaning": r.leaning}
    finally:
        shutil.rmtree(work, ignore_errors=True)


def run_all(jobs: list[tuple[Run, Scenario]], draws: int = 300, workers: int | None = None) -> pd.DataFrame:
    tasks = [(run, scenario, draws) for run, scenario in jobs]
    if workers == 1:
        rows = [_execute(t) for t in tasks]
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            rows = list(pool.map(_execute, tasks, chunksize=2))
    return classify(pd.DataFrame(rows))


def classify(df: pd.DataFrame) -> pd.DataFrame:
    """correct · right outcome, wrong status · insufficient evidence · overconfident · wrong outcome.

    "overconfident": the truth is itself insufficient evidence and the run asserts the outcome it leans to."""
    def kind(r):
        if r["verdict"] == r["truth"] == "insufficient_evidence":
            return "correct"
        if r["verdict"] == "insufficient_evidence":
            return "insufficient"
        if r["truth"] == "insufficient_evidence" and r["verdict"] == r.get("truth_leaning"):
            return "overconfident"
        if r["verdict"] != r["truth"]:
            return "wrong"
        return "correct" if r["status"] == r["truth_status"] else "status_differs"
    return df.assign(result=df.apply(kind, axis=1))


def at_confidence(df: pd.DataFrame, confidence: float) -> pd.DataFrame:
    """Verdicts under a stricter confidence level, re-derived from the stored distributions.

    Only levels at or above the one the runs used are supported: a looser level would promote runs whose
    status (go / prepare first) was never computed."""
    out = df.copy()
    for i, r in out.iterrows():
        dist = {k: v for k, v in r["distribution"].items() if k != "unresolved"}
        p = max(dist.values()) if dist else 0.0
        if p < confidence:
            out.at[i, "verdict"] = "insufficient_evidence"
            out.at[i, "status"] = "insufficient"
    return classify(out.drop(columns=["result"]))


# ====================================================================================== validity grid

def grid(cases: Iterable[str] | None = None, sizes=(5, 10, 15, 30), noises=(0.3, 0.6, 0.9), seeds=range(5),
         draws: int = 300, workers: int | None = None) -> pd.DataFrame:
    jobs = []
    for case in cases or ALL_CASES:
        decision, outcome, status = expected(case)
        for n in sizes:
            for noise in noises:
                for seed in seeds:
                    scenario = _with(ALL_CASES[case], noise=noise)
                    jobs.append((Run(case, decision, outcome, status, n, noise, seed), scenario))
    return run_all(jobs, draws, workers)


def _with(scenario: Scenario, **changes) -> Scenario:
    s = copy.copy(scenario)
    for k, v in changes.items():
        setattr(s, k, v)
    return s


# ====================================================================================== threshold sweeps

def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def architecture_need_family(t: float) -> Scenario:
    """From a small, loosely coupled organisation (t=0) to a large, tightly coupled one (t=1), strong platform,
    data not yet separable: the truth moves from 'stay and improve' to 'modular monolith'."""
    from .cases import STRONG_CAPABILITY, STRONG_CAPABILITY_FACTS
    need = _lerp(1.2, 4.2, t)
    return Scenario(f"need@{t:.2f}", {},
                    targets={**STRONG_CAPABILITY, "need.architecture.coupling": need,
                             "need.architecture.business_impact": need, "need.architecture.cognitive_load": need,
                             "capability.architecture.data": 2.5, "locality.concentration": 2.0},
                    labels={"AN01": "Coordinating with other teams' changes"},
                    facts={**STRONG_CAPABILITY_FACTS, "teams_per_deployable": round(_lerp(1, 12, t)),
                           "cross_team_change_pct": _lerp(2, 45, t), "blast_radius_pct": _lerp(5, 40, t),
                           "shared_tables_pct": 35, "friction_concentration_index": 1.2})


def hosting_cost_family(t: float) -> Scenario:
    """Own infrastructure, no specific need; the cloud estimate (compute and operations staff) falls until a
    cost-motivated move pays back within the pre-registered 24 months: the truth moves from 'stay' to 'move to cloud'."""
    from .cases import GOOD_OPS, STEADY
    baseline = _lerp(600000, 20000, t)
    return Scenario(f"cloudcost@{t:.2f}", {},
                    targets={**STEADY, **GOOD_OPS, "capability.hosting.cloud_skills": 3.5},
                    facts={"ops_fte": 6, "infra_share_pct": 100, "rightsized_share_pct": 95,
                           "cloud_ops_fte": _lerp(3.0, 1.0, t),
                           "cloud_compute_baseline_annual": {"low": baseline * 0.85, "likely": baseline,
                                                             "high": baseline * 1.25, "grade": "calculator_export"}})


def extraction_pain_family(t: float) -> Scenario:
    """A component in its own compliance scope whose share of incidents rises from 0 % to 60 %: the pain test
    (25 %) decides whether separating it out applies."""
    from .cases import ARCHITECTURE_CASES
    base = ARCHITECTURE_CASES["d_pci_component"]
    targets = {**base.targets, "need.architecture.coupling": 3.1, "need.architecture.business_impact": 3.1}
    # general need set clearly inside "restructure" so that the sweep crosses only the pain threshold
    return Scenario(f"pain@{t:.2f}", {}, targets=targets, labels=dict(base.labels),
                    facts={**base.facts, "teams_per_deployable": 7, "cross_team_change_pct": 22,
                           "candidate_incident_share_pct": _lerp(0, 60, t),
                           "candidate_scope_in_main_deployable": "no", "candidate_scaling_cost_share_pct": 5})


def consolidation_family(t: float) -> Scenario:
    """A distributed estate (four services per team) whose share of lockstep releases rises from 0 % to 60 %:
    the truth moves from realigning services to consolidating them (trigger 30 %)."""
    return Scenario(f"lockstep@{t:.2f}", {}, targets={"need.architecture.coupling": 3.8},
                    facts={"deployables_in_scope": 24, "core_code_share_pct": 15, "services_per_team": 4,
                           "lockstep_deploy_pct": _lerp(0, 60, t), "cross_service_change_pct": 20,
                           "teams_per_deployable": 2, "cross_team_change_pct": 25, "blast_radius_pct": 30})


def repatriation_family(t: float) -> Scenario:
    """A SaaS company in the cloud with steady load, managed dedicated servers as the alternative; the cloud bill
    rises until moving back pays off within the pre-registered criteria."""
    from .cases import HOSTING_CASES
    base = HOSTING_CASES["c_saas_cloud_overpaying"]
    bill = _lerp(150000, 900000, t)
    return Scenario(f"cloudbill@{t:.2f}", {}, targets=dict(base.targets), current_hosting="cloud",
                    facts={**base.facts, "infra_oncall_people": 4,
                           "cloud_compute_baseline_annual": {"low": bill * 0.92, "likely": bill, "high": bill * 1.1,
                                                             "grade": "invoice"}})


FAMILIES: dict[str, tuple[str, Callable[[float], Scenario]]] = {
    "architecture_need": ("architecture", architecture_need_family),
    "hosting_cost": ("hosting", hosting_cost_family),
    "extraction_pain": ("architecture", extraction_pain_family),
    "consolidation": ("architecture", consolidation_family),
    "repatriation": ("hosting", repatriation_family),
}


def truth_of(family: str, t: float, draws: int = 200, instrument: str | Path = INSTRUMENT, noise: float = 0.6,
             population: int = 100) -> tuple[str, str, str | None]:
    """The rules' outcome for the population: the same answering process with many respondents per group, so
    that only the sampling error of a realistic group size is left to measure."""
    from .assess import assess
    decision, make = FAMILIES[family]
    scenario = _with(make(t), noise=noise)
    work = Path(tempfile.mkdtemp(prefix="mra-truth-"))
    try:
        a = assess(build(scenario, work, instrument, seed=0, group_size=population), decisions=(decision,), draws=draws)
        r = a.results[decision]
        return r.verdict, r.status, r.leaning
    finally:
        shutil.rmtree(work, ignore_errors=True)


def sweep(family: str, ts=np.linspace(0, 1, 21), sizes=(5, 15), noise: float = 0.6, seeds=range(5),
          draws: int = 300, workers: int | None = None, instrument: str | Path = INSTRUMENT) -> pd.DataFrame:
    decision, make = FAMILIES[family]
    jobs = []
    for t in ts:
        truth, status, leaning = truth_of(family, float(t), instrument=instrument, noise=noise)
        for n in sizes:
            for seed in seeds:
                jobs.append((Run(family, decision, truth, status, n, noise, seed, float(t), str(instrument), leaning),
                             _with(make(float(t)), noise=noise)))
    return run_all(jobs, draws, workers)


# ====================================================================================== summaries

RESULTS = ["correct", "status_differs", "insufficient", "overconfident", "wrong"]


def summary(df: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    table = pd.crosstab([df[c] for c in by], df["result"], normalize="index").reindex(columns=RESULTS, fill_value=0)
    table["runs"] = df.groupby(by).size()
    return table


def to_markdown(table: pd.DataFrame, pct: bool = True) -> str:
    t = table.copy()
    if pct:
        for c in RESULTS:
            if c in t:
                t[c] = (t[c] * 100).round(0).astype(int).astype(str) + "%"
    return t.reset_index().to_markdown(index=False)


# ====================================================================================== command line

def main(quick: bool = False, out: Path | None = None, workers: int | None = None) -> dict[str, pd.DataFrame]:
    """Run the validity grid and the threshold sweeps; write pickles and a markdown summary to `out`."""
    out = Path(out or ROOT / "Output" / "sim")
    out.mkdir(parents=True, exist_ok=True)
    if quick:
        results = {"grid": grid(sizes=(15,), noises=(0.6,), seeds=range(2), workers=workers)}
    else:
        results = {"grid": grid(workers=workers),
                   **{f"sweep_{f}": sweep(f, workers=workers) for f in FAMILIES}}
    lines = ["# Simulation results", ""]
    for name, df in results.items():
        df.to_pickle(out / f"{name}.pkl")
        by = ["group_size"] if name == "grid" else ["group_size", "t"]
        lines += [f"## {name}", "", to_markdown(summary(df, by)), ""]
        if name == "grid":
            lines += ["### by case (all sizes and noise levels)", "", to_markdown(summary(df, ["case"])), ""]
    (out / "summary.md").write_text("\n".join(lines))
    return results
