"""Engagement configuration loaded from assessment.yaml."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class DecisionRules:
    signed_off_by: str | None = None
    role_weights: dict[str, float] = field(default_factory=dict)
    essential_roles: list[str] = field(default_factory=list)
    role_veto_domains: list[str] = field(default_factory=list)
    red_below: float = 3.0
    green_from: float = 4.0
    proceed_from: float = 3.5
    confidence: float = 0.80
    min_role_n: int = 5
    min_role_items: int = 3
    strong_evidence_role_n: int = 15
    min_item_coverage: float = 0.6
    min_reliability: float = 0.70

    def weight(self, role: str) -> float:
        return float(self.role_weights.get(role, 1.0))


@dataclass
class StatisticsSettings:
    bootstrap_iterations: int = 2000
    permutation_iterations: int = 2000
    seed: int = 42


@dataclass
class LLMSettings:
    enabled: bool = False
    model: str = "anthropic/claude-opus-5.5"
    redact: bool = True
    redact_terms: list[str] = field(default_factory=list)
    max_quotes: int = 3


@dataclass
class Config:
    root: Path
    engagement: dict
    questionnaire: Path
    responses: list[dict]
    scale: dict[str, int]
    dont_know_labels: list[str]
    rules: DecisionRules
    stats: StatisticsSettings
    llm: LLMSettings
    report_template: Path
    report_output: Path

    @property
    def roles(self) -> list[str]:
        return [r["role"] for r in self.responses]

    @property
    def report_date(self) -> dt.date:
        value = self.engagement.get("date")
        if value is None:
            return dt.date.today()
        return value if isinstance(value, dt.date) else dt.date.fromisoformat(str(value))


def load_config(path: str | Path = "assessment.yaml") -> Config:
    path = Path(path).resolve()
    raw = yaml.safe_load(path.read_text())
    root = path.parent
    report = raw.get("report", {})
    return Config(
        root=root,
        engagement=raw.get("engagement", {}),
        questionnaire=root / raw["questionnaire"],
        responses=[{"role": r["role"], "file": root / r["file"]} for r in raw["responses"]],
        scale=raw.get("scale", {}),
        dont_know_labels=raw.get("dont_know_labels", []),
        rules=DecisionRules(**raw.get("decision_rules", {})),
        stats=StatisticsSettings(**raw.get("statistics", {})),
        llm=LLMSettings(**raw.get("llm", {})),
        report_template=root / report.get("template", "report/templates/default"),
        report_output=root / report.get("output", "Output/report.pdf"),
    )
