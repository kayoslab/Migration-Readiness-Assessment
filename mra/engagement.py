"""A v3 engagement: configuration, survey exports, fact sheet and governance attestations.

engagement.yaml
    system: Order Platform
    current_hosting: own_infrastructure        # own_infrastructure | cloud | hybrid
    consistency_example: "an order shows as paid before stock is reserved"
    instrument: instrument                     # folder with items/facts/governance/outcomes
    rules: decision_rules.yaml                 # the engagement's signed-off copy (default: instrument's)
    responses: {ENG: Responses/ENG.csv, ...}   # one form export per stakeholder group
    facts: facts.yaml
    governance: governance.yaml                # optional until after the verdict

facts.yaml — one entry per fact:
    teams_per_deployable: {value: 7, source: tools/git_coupling.py, date: 2026-10-01, attester: Platform lead}
    migration_cost: {low: 200000, likely: 300000, high: 600000, grade: estimate, source: ..., date: ...}
    deploy_automation: {value: team_triggered, source: CD config}
    cloud_compute_baseline_annual:            # two independent estimators: the model uses the union of their ranges
      estimates:
        - {estimator: Platform team, low: 250000, likely: 300000, high: 380000, grade: calculator_export}
        - {estimator: Finance, low: 280000, likely: 340000, high: 420000, grade: quote}
    Optional per fact: scripted (true when produced by `mra coupling`), attester, second_attester,
    justification (required for very wide ranges).

engagement.yaml may also name `people: {sponsor: ..., fact_sheet_owner: ...}` and `fact_sheet_frozen_on: <date>`
(see decision_rules.yaml → fact_discipline).

governance.yaml — one entry per check in governance.csv:
    GV01: {answer: "Yes", evidence: "Board minute 2026-09-12", attested_by: CTO}
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from .instrument import DONT_KNOW, Instrument, load_instrument


GRADE_ORDER = ["invoice", "quote", "calculator_export", "benchmark", "estimate"]   # most to least certain


@dataclass
class Fact:
    value: object = None          # number or category
    low: float | None = None
    likely: float | None = None
    high: float | None = None
    grade: str | None = None
    source: str | None = None
    attester: str | None = None
    second_attester: str | None = None
    scripted: bool = False
    justification: str | None = None
    estimators: list[str] = field(default_factory=list)
    disagreement: float | None = None   # spread of the estimators' likely values relative to their mean

    @property
    def is_range(self) -> bool:
        return self.likely is not None

    @property
    def point(self):
        return self.likely if self.is_range else self.value


@dataclass
class Engagement:
    root: Path
    config: dict
    instrument: Instrument
    default_rules: dict
    answers: pd.DataFrame                     # long: respondent_id, role, item_id, row, label, score, dont_know, not_applicable
    respondents: pd.DataFrame                 # respondent_id, role, involvement
    facts: dict[str, Fact]
    governance: dict[str, dict] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)

    @property
    def system(self) -> str:
        return self.config.get("system", "the system")

    def current_states(self, architecture_state: str) -> dict[str, str]:
        return {"architecture": architecture_state, "hosting": self.config.get("current_hosting", "own_infrastructure")}


def load_facts(path: Path | None) -> dict[str, Fact]:
    if not path or not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text()) or {}
    facts = {}
    keys = ("value", "low", "likely", "high", "grade", "source", "attester", "second_attester", "justification")
    for fid, spec in raw.items():
        if not isinstance(spec, dict):
            spec = {"value": spec}
        fact = Fact(**{k: spec.get(k) for k in keys}, scripted=bool(spec.get("scripted", False)))
        if spec.get("estimates"):
            est = spec["estimates"]
            likelies = [float(x["likely"]) for x in est]
            fact.low = min(float(x["low"]) for x in est)
            fact.high = max(float(x["high"]) for x in est)
            fact.likely = sum(likelies) / len(likelies)
            fact.grade = max((x.get("grade", "estimate") for x in est), key=GRADE_ORDER.index)
            fact.estimators = [x.get("estimator", f"estimate {i + 1}") for i, x in enumerate(est)]
            mean = abs(fact.likely) or 1.0
            fact.disagreement = (max(likelies) - min(likelies)) / mean
            fact.source = fact.source or "; ".join(str(x.get("source", x.get("estimator", ""))) for x in est)
        facts[fid] = fact
    return facts


def _score_answer(ins: Instrument, item_id: str, label: str, options: list[str]) -> tuple[float, bool, bool]:
    """(score, dont_know, not_applicable) for a single (non-grid) answer."""
    it = ins.items.loc[item_id]
    if label == DONT_KNOW:
        return np.nan, True, False
    if it["not_applicable"] and label == it["not_applicable"]:
        return np.nan, False, True
    scores = ins.scores(item_id)
    if isinstance(scores, dict):
        return scores.get(label, np.nan), False, False
    return np.nan, False, False


def load_engagement(path: str | Path) -> Engagement:
    path = Path(path).resolve()
    root = path.parent
    cfg = yaml.safe_load(path.read_text())
    instrument_dir = root / cfg.get("instrument", "instrument")
    rules_path = root / cfg["rules"] if cfg.get("rules") else None
    ins = load_instrument(instrument_dir, rules_path)
    default_rules = yaml.safe_load((instrument_dir / "decision_rules.yaml").read_text())
    facts = load_facts(root / cfg["facts"]) if cfg.get("facts") else {}
    governance = yaml.safe_load((root / cfg["governance"]).read_text()) if cfg.get("governance") and \
        (root / cfg["governance"]).exists() else {}
    problems = [f"fact {f}: not in facts.csv" for f in facts if f not in ins.facts.index]

    # The architecture state is derived from facts (see rules.signals.current_state); the form needs it to offer
    # the right preference options, so derive it here the same way.
    from .axes import derive_current_state
    arch_state = derive_current_state(ins, facts)
    current = {"architecture": arch_state, "hosting": cfg.get("current_hosting", "own_infrastructure")}

    rows, people = [], []
    for role, file in (cfg.get("responses") or {}).items():
        spec = ins.form_spec(role, cfg.get("system", "the system"), current, cfg.get("consistency_example", ""))
        by_header = {q["header"]: q for q in spec}
        df = pd.read_csv(root / file, dtype=str, keep_default_na=False)
        unknown = [c for c in df.columns if c not in by_header and c.lower() != "timestamp"]
        if unknown:
            problems.append(f"{role}: {len(unknown)} column(s) do not match the form, e.g. {unknown[0][:70]!r}")
        for n, (_, r) in enumerate(df.iterrows(), start=1):
            rid = f"{role}-{n:03d}"
            involvement = r.get(by_header_text(spec, "CX02"), "")
            people.append({"respondent_id": rid, "role": role, "involvement": involvement})
            for header, q in by_header.items():
                label = str(r.get(header, "")).strip()
                if not label or q["format"] == "text":
                    if label and q["format"] == "text":
                        rows.append((rid, role, q["item_id"], None, label, np.nan, False, False))
                    continue
                if q["row"] is None:
                    score, dk, na = _score_answer(ins, q["item_id"], label, q["options"])
                    if label not in q["options"]:
                        problems.append(f"{rid} {q['item_id']}: answer {label!r} is not an option")
                        continue
                else:
                    score, dk, na = np.nan, label == DONT_KNOW, False
                rows.append((rid, role, q["item_id"], q["row"], label, score, dk, na))
    answers = pd.DataFrame(rows, columns=["respondent_id", "role", "item_id", "row", "label", "score",
                                          "dont_know", "not_applicable"])
    return Engagement(root, cfg, ins, default_rules, answers, pd.DataFrame(people), facts, governance or {}, problems)


def by_header_text(spec: list[dict], item_id: str) -> str:
    return next((q["header"] for q in spec if q["item_id"] == item_id), "")


def write_form_exports(eng_root: Path, ins: Instrument, system: str, current: dict[str, str],
                       answers_by_role: dict[str, list[dict[str, str]]], consistency_example: str = "") -> dict:
    """Write CSVs shaped like Google Forms exports (used by tests and the simulator)."""
    files = {}
    for role, people in answers_by_role.items():
        spec = ins.form_spec(role, system, current, consistency_example)
        headers = ["Timestamp"] + [q["header"] for q in spec]
        records = []
        for person in people:
            rec = {"Timestamp": "2026-11-01 09:00:00"}
            for q in spec:
                key = q["item_id"] if q["row"] is None else f"{q['item_id']}[{q['row']}]"
                rec[q["header"]] = person.get(key, "")
            records.append(rec)
        path = eng_root / "Responses" / f"{role}.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(records, columns=headers).to_csv(path, index=False)
        files[role] = str(path.relative_to(eng_root))
    return files
