"""Cross-source integrity: read the fact sheet, governance answers, survey and free text against each other.

Each source is processed correctly on its own elsewhere; this module finds where they contradict each other, so
the report never states something its own inputs contradict. Checks and severities are declared in
instrument/integrity.yaml:

- block  — the report is a draft (the cover and executive summary say why); `mra report --final` fails;
- caveat — printed beside every exhibit, decision, measure, step and free-text finding that uses the input;
- note   — listed in the basis of preparation.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .tco import OWN_RUN

GROUP_NAMES = {"ENG": "Engineering", "PRD": "Product", "BUS": "Business", "TEC": "Technology leadership",
               "EXE": "Executive", "OPS": "Operations", "SEC": "Security", "FIN": "Finance"}


@dataclass
class Issue:
    id: str
    severity: str                      # block | caveat | note
    title: str
    message: str
    exhibits: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    facts: list[str] = field(default_factory=list)
    key_messages: list[int] = field(default_factory=list)     # indices into the free-text key messages
    themes: list[int] = field(default_factory=list)           # indices into the free-text themes
    step_rewrite: dict | None = None                          # {"starts_with": ..., "action": ...}

    def as_dict(self) -> dict:
        return {k: v for k, v in vars(self).items()}


def load_config(instrument_root: Path) -> dict:
    path = Path(instrument_root) / "integrity.yaml"
    return (yaml.safe_load(path.read_text()) or {}).get("checks", {}) if path.exists() else {}


def _eur(x: float) -> str:
    return f"€{x / 1e6:.2f}M" if abs(x) >= 1e6 else f"€{x / 1e3:,.0f}k"


def _date(value) -> dt.date | None:
    if value in (None, ""):
        return None
    if isinstance(value, dt.date):
        return value
    try:
        return dt.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _point(eng, fid):
    f = eng.facts.get(fid)
    return None if f is None or f.point is None else f.point


# ---------------------------------------------------------------------------------------- checks

def _rules_signed_off(a, cfg) -> list[Issue]:
    rules, eng = a.engagement.instrument.rules, a.engagement
    by, on = rules.get("signed_off_by"), _date(rules.get("signed_off_on"))
    frozen = _date(eng.config.get("fact_sheet_frozen_on"))
    version = rules.get("version", "?")
    if not by:
        return [Issue("rules_signed_off", cfg["severity"], "Decision rules not signed off",
                      f"The decision rules (version {version}) are not recorded as signed off. The recommendation "
                      "follows them, so it cannot be relied on until the stakeholders who agreed the rules have "
                      "signed them off — before seeing these results.")]
    if on and frozen and on > frozen:
        return [Issue("rules_signed_off", cfg["severity"], "Decision rules signed off after the fact sheet was frozen",
                      f"The decision rules were signed off on {on:%d %B %Y}, after the fact sheet was frozen on "
                      f"{frozen:%d %B %Y}; they may have been adjusted with the evidence in view.")]
    return []


_ANSWER = {"No": "not measured", "Partly": "only partly measured", None: "not confirmed"}


def _baseline_unverified(a, cfg) -> list[Issue]:
    eng = a.engagement
    present = {f: _point(eng, f) for f in cfg["facts"] if _point(eng, f) is not None}
    answer = (eng.governance.get(cfg["governance"]) or {}).get("answer")
    if not present or answer in cfg.get("verified_answers", ["Yes"]):
        return []
    words = {"lead_time_hours": "lead time {v:g} h", "deploys_per_week": "{v:g} deployments a week",
             "change_failure_pct": "{v:g}% change failure", "restore_hours": "{v:g} h to restore"}
    listed = ", ".join(words[f].format(v=v) for f, v in present.items() if f in words)
    return [Issue("baseline_unverified", cfg["severity"], "Delivery measures not verified",
                  f"The delivery measures in the fact sheet ({listed}) are not backed by a measurement in the last six "
                  f"months: the governance checklist records them as {_ANSWER.get(answer, 'not confirmed')}. Comparisons and "
                  "baselines that use them are provisional until they are verified.",
                  exhibits=["readiness.benchmark"], facts=list(present),
                  step_rewrite={"starts_with": "Measure lead time",
                                "action": "Verify the delivery measures in the fact sheet against system data — they are "
                                          "not yet backed by a recent measurement — and define two or three outcome "
                                          "measures with baseline, target and business owner."})]


def _point_hosting_verdict(a, extra: dict[str, float]) -> str | None:
    """The hosting path at the point estimate if `extra` facts were added (used to test what a cost gap could do)."""
    import numpy as np

    from .decision import Context, _check_outcome
    from .tco import compute
    eng, ev = a.engagement, a.evidence
    rules = eng.instrument.rules
    facts = {k: np.array([float(v)]) for k, v in ev.fact_point.items() if isinstance(v, (int, float))}
    facts.update({k: np.array([float(v)]) for k, v in extra.items()})
    current = eng.config.get("current_hosting", "own_infrastructure")
    signals, problems = compute(facts, current, rules["decisions"]["hosting"].get("horizon_years", 5))
    if problems:
        return None
    values = dict(ev.at(0))
    values.update({k: float(v[0]) for k, v in signals.items()})
    ctx = Context(values, rules, ev.current_state, "hosting")
    for spec in rules["decisions"]["hosting"]["outcomes"]:
        allowed = spec.get("only_if_current")
        if allowed and ev.current_state["hosting"] not in (allowed if isinstance(allowed, list) else [allowed]):
            continue
        applies, status, _, _ = _check_outcome(spec, ctx, rules)
        if applies and status in ("go", "prepare_first"):
            return spec["id"]
    return None


def _run_cost_reconciliation(a, cfg) -> list[Issue]:
    eng = a.engagement
    if eng.config.get("current_hosting", "own_infrastructure") != "own_infrastructure":
        return []
    invoice = _point(eng, "run_cost_annual")
    parts = {k: _point(eng, k) for k in OWN_RUN}
    ops, share, fte = (_point(eng, k) for k in ("ops_fte", "infra_share_pct", "fte_cost_annual"))
    if invoice is None or None in parts.values() or None in (ops, share, fte):
        return []
    allocated = (_point(eng, "unallocated_infra_annual") or 0) + (_point(eng, "unallocated_common_annual") or 0)
    infra = sum(parts.values())
    staff = ops * share / 100 * fte
    model = infra + staff + allocated
    if not model or abs(invoice / model - 1) * 100 <= cfg["tolerance_pct"]:
        return []
    gap = invoice - model
    facts = ["run_cost_annual", *OWN_RUN, "ops_fte", "infra_share_pct", "unallocated_infra_annual",
             "unallocated_common_annual"]
    message = (f"The fact sheet's annual run cost ({_eur(invoice)}, infrastructure and operations) is "
               f"{invoice / model:.1f}× what the cost model accounts for ({_eur(model)}: infrastructure {_eur(infra)}, "
               f"operations staff {_eur(staff)} at {share:g}% of {ops:g} FTE"
               + (f", allocated difference {_eur(allocated)}" if allocated else "") + "). ")
    verdict = a.results["hosting"].verdict if "hosting" in a.results else None
    if gap > 0 and verdict and verdict != "insufficient_evidence":
        as_infra = _point_hosting_verdict(a, {"unallocated_infra_annual": (_point(eng, "unallocated_infra_annual") or 0) + gap})
        as_common = _point_hosting_verdict(a, {"unallocated_common_annual": (_point(eng, "unallocated_common_annual") or 0) + gap})
        changed = [w for w, v in (("if it is infrastructure cost", as_infra), ("if it remains in every option", as_common))
                   if v and v != verdict]
        if changed:
            return [Issue("run_cost_reconciliation", "block", "Run cost not reconciled — the recommendation depends on it",
                          message + f"If the remaining {_eur(gap)} a year is real cost, the hosting recommendation "
                          f"changes {' or '.join(changed)}. Finance should allocate it before the report is final.",
                          exhibits=["hosting.tco", "hosting.tornado"], decisions=["hosting"], facts=facts)]
    return [Issue("run_cost_reconciliation", cfg["severity"], "Run cost not reconciled",
                  message + "The comparison of options uses what the model accounts for. Whether the remaining "
                  f"{_eur(abs(gap))} a year is infrastructure cost or remains in every option, the recommendation "
                  "stays the same; the absolute figures should be confirmed once Finance has allocated it.",
                  exhibits=["hosting.tco", "hosting.tornado"], decisions=["hosting"], facts=facts)]


def _texts(a) -> tuple[list[str], list[str]]:
    t = a.text
    if t is None:
        return [], []
    quotes = {q["id"]: q["text"] for q in t.quotes}
    themes = [" ".join([th.get("finding", "")] + [quotes.get(i, "") for i in th.get("quote_ids", [])])
              for th in t.synthesis.get("themes", [])]
    return list(t.synthesis.get("key_messages", [])), themes


def _hits(texts: list[str], keywords: list[str], also: list[str] | None = None) -> list[int]:
    out = []
    for i, text in enumerate(texts):
        low = text.lower()
        if any(re.search(rf"\b{re.escape(k.lower())}", low) for k in keywords) and \
                (also is None or any(w in low for w in also)):
            out.append(i)
    return out


def _urgency_vs_dates(a, cfg) -> list[Issue]:
    eng = a.engagement
    messages, themes = _texts(a)
    dates = {"hardware refresh": _point(eng, "hw_refresh_due_months"), "contract end": _point(eng, "contract_end_months")}
    dates = {k: v for k, v in dates.items() if v is not None}
    if not dates or min(dates.values()) < cfg["min_months"]:
        return []
    topic = ["refresh", "hardware", "contract", "renewal"]
    km, th = _hits(messages, cfg["keywords"], topic), _hits(themes, cfg["keywords"], topic)
    if not km and not th:
        return []
    when = " and ".join(f"the {k} {v:g} months away" for k, v in dates.items())
    return [Issue("urgency_vs_dates", cfg["severity"], "Urgency not supported by the dates",
                  f"Respondents describe the decision as due; the fact sheet puts {when}. On these dates the hosting "
                  "decision is not time-critical, though it should be taken before the refresh is ordered.",
                  decisions=["hosting"], facts=list({"hardware refresh": "hw_refresh_due_months",
                                                     "contract end": "contract_end_months"}[k] for k in dates),
                  key_messages=km, themes=th)]


def _critical_groups(a, cfg) -> list[Issue]:
    eng = a.engagement
    sizes = eng.respondents["role"].value_counts() if not eng.respondents.empty else {}
    min_n = eng.instrument.rules.get("evidence", {}).get("min_role_n", 5)
    out = []
    for d, groups in cfg["groups"].items():
        if d not in a.results:
            continue
        short = [(g, int(sizes.get(g, 0))) for g in groups if int(sizes.get(g, 0)) < min_n]
        if not short:
            continue
        parts = [f"{GROUP_NAMES.get(g, g)} ({n}{' respondents' if i == 0 else ''})" for i, (g, n) in enumerate(short)]
        listed = parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]
        out.append(Issue(f"critical_groups.{d}", cfg["severity"], f"Perspectives missing from the {d} assessment",
                         f"{listed} {'is' if len(short) == 1 else 'are'} below the minimum group size of {min_n}. "
                         f"{'Its' if len(short) == 1 else 'Their'} answers are pooled with other small groups and do "
                         f"not count separately towards the {d} assessment, although the decision depends on "
                         f"{'this perspective' if len(short) == 1 else 'these perspectives'}.",
                         decisions=[d], exhibits=["people.map"]))
    return out


def _disputed_claims(a, cfg) -> list[Issue]:
    messages, themes = _texts(a)
    if not messages and not themes:
        return []
    point = a.evidence.at(0)
    out = []
    for claim in cfg["claims"]:
        km, th = _hits(messages, claim["keywords"]), _hits(themes, claim["keywords"])
        if not km and not th:
            continue
        if "signal" in claim:
            value = point.get(claim["signal"])
            if value is None or value >= claim["contradicted_below"]:
                continue
            evidence = claim["evidence"].format(waiting=value, coordination=point.get("coordination_share") or 0)
        else:
            value = _point(a.engagement, claim["fact"])
            if value is None or value <= claim["contradicted_above"]:
                continue
            evidence = claim["evidence"].format(value=value)
        out.append(Issue(f"disputed_claims.{claim['id']}", cfg["severity"], "A view the survey does not support",
                         f"Some respondents attribute the problem differently, but {evidence.strip()}. The view is "
                         "reported as a view, not as a finding.", key_messages=km, themes=th,
                         exhibits=["architecture.leadtime"]))
    return out


def _attestation(a, cfg) -> list[Issue]:
    eng = a.engagement
    unattested = sorted(f for f, v in eng.facts.items() if not v.attester)
    if not unattested:
        return []
    return [Issue("attestation", cfg["severity"], "Facts without an attester",
                  f"{len(unattested)} fact(s) have no named attester, e.g. {', '.join(unattested[:4])}.",
                  facts=unattested)]


CHECKS = {"rules_signed_off": _rules_signed_off, "baseline_unverified": _baseline_unverified,
          "run_cost_reconciliation": _run_cost_reconciliation, "urgency_vs_dates": _urgency_vs_dates,
          "critical_groups": _critical_groups, "disputed_claims": _disputed_claims, "attestation": _attestation}


def run(assessment) -> list[Issue]:
    config = load_config(assessment.engagement.instrument.root)
    issues = []
    for name, check in CHECKS.items():
        if name in config:
            issues += check(assessment, config[name])
    order = {"block": 0, "caveat": 1, "note": 2}
    return sorted(issues, key=lambda i: order[i.severity])
