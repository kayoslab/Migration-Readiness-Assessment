"""Fact-sheet discipline (decision_rules.yaml → fact_discipline), checked rather than merely stated.

Findings are reported in the CLI and the report appendix. They never change the verdict: they tell the reader
how much to trust the inputs, and what to fix before the next run.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FactCheck:
    severity: str        # "problem" (undermines independence) | "warning" (weakens the evidence)
    fact: str | None
    message: str


def check(eng) -> list[FactCheck]:
    rules = eng.instrument.rules
    disc = rules.get("fact_discipline", {}) or {}
    facts, spec = eng.facts, eng.instrument.facts
    people = eng.config.get("people", {}) or {}
    sponsor, owner = people.get("sponsor"), people.get("fact_sheet_owner")
    out: list[FactCheck] = []

    def names(fids: list[str], n: int) -> str:                 # readable labels, not field names
        words = [spec.at[f, "label"].split(" (")[0] for f in fids[:n] if f in spec.index]
        words = [w[0].lower() + w[1:] for w in words]
        return "; ".join(words)

    if disc.get("fact_sheet_owner_must_not_be_sponsor"):
        if not owner:
            out.append(FactCheck("warning", None, "The fact-sheet owner is not named."))
        elif sponsor and owner.strip().lower() == sponsor.strip().lower():
            out.append(FactCheck("problem", None, f"The fact-sheet owner ({owner}) is also the sponsor of the change; "
                                                  "the facts are not independent of the proposal."))
        if sponsor:
            by_sponsor = [f for f, v in facts.items() if v.attester and v.attester.strip().lower() == sponsor.strip().lower()]
            if by_sponsor:
                out.append(FactCheck("problem", None, f"{len(by_sponsor)} fact(s) are attested by the sponsor: "
                                                      f"{names(by_sponsor, 6)}."))

    if disc.get("freeze_before_survey_results") and not eng.config.get("fact_sheet_frozen_on"):
        out.append(FactCheck("warning", None, "No freeze date is recorded for the fact sheet; facts should be fixed "
                                              "before survey results are seen."))

    for fid in disc.get("scripted_metrics", []):
        if fid in facts and not facts[fid].scripted:
            out.append(FactCheck("warning", fid, f"{spec.at[fid, 'label']} should be produced by the coupling "
                                                 "analysis of the code repository, not entered by hand."))

    for fid in disc.get("second_attester_for", []):
        if fid in facts and not facts[fid].second_attester:
            out.append(FactCheck("warning", fid, f"{spec.at[fid, 'label']} needs a second attester."))

    max_ratio = disc.get("max_range_ratio")
    unsourced = [fid for fid, f in facts.items()
                 if fid in spec.index and f.point is not None and not f.source and not f.scripted]
    if unsourced:
        out.append(FactCheck("warning", None, f"{len(unsourced)} fact(s) have no source, e.g. {names(unsourced, 3)}."))
    for fid, f in facts.items():
        if fid not in spec.index:
            continue
        if max_ratio and f.is_range and f.low and f.low > 0 and f.high / f.low > max_ratio and not f.justification:
            out.append(FactCheck("warning", fid, f"{spec.at[fid, 'label']}: the range {f.low:,.0f}–{f.high:,.0f} is "
                                                 f"wider than {max_ratio:g}x without a written justification."))

    flag = disc.get("estimator_disagreement_flag", 0.25)
    needs_two = [fid for fid in spec.index if _needs_two(fid, spec, disc.get("two_estimators_for", []))]
    single = [fid for fid in needs_two if fid in facts and facts[fid].is_range and len(facts[fid].estimators) < 2]
    if single:
        out.append(FactCheck("warning", None, f"{len(single)} cost input(s) have only one estimator "
                                              f"(two independent estimates are expected): {names(single, 4)}."))
    for fid in needs_two:
        f = facts.get(fid)
        if f and f.disagreement is not None and f.disagreement > flag:
            out.append(FactCheck("warning", fid, f"{spec.at[fid, 'label']}: estimators differ by {f.disagreement:.0%} "
                                                 f"({' vs '.join(f.estimators)}); the model uses the union of their ranges."))
    return out


def _needs_two(fid: str, spec, targets: list[str]) -> bool:
    row = spec.loc[fid]
    for t in targets:
        if t == fid:
            return True
        if "." in t:
            decision, axis = t.split(".", 1)
            if row["decision"] == decision and row["axis"] == axis and row["range"] == "true":
                return True
    return False
