"""Instrument v3: item bank, fact sheet, governance checklist, decision rules and outcome definitions.

`load_instrument` reads `instrument/`; `validate` cross-checks every reference (items, facts, gates, hard stops,
signals, outcomes) and enforces that anything a rule depends on is a core item; `form_spec` produces the
questions exactly as respondents see them, which is also how survey exports are mapped back to item IDs.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import yaml

ROLES = ["ENG", "PRD", "BUS", "TEC", "EXE", "OPS", "SEC", "FIN"]
DONT_KNOW = "Don't know"
TECHNICAL_BLOCKS = {"need", "locality", "capability", "fit"}   # weighted by involvement (CX02)
SIGNAL_FAMILIES = ("tco_ratio", "payback_months", "payback_after_cutover", "tco_saving_fte")


@dataclass
class Instrument:
    items: pd.DataFrame        # indexed by id
    facts: pd.DataFrame        # indexed by id
    governance: pd.DataFrame   # indexed by id
    rules: dict
    outcomes: dict
    root: Path

    # ------------------------------------------------------------------ item helpers
    def roles_for(self, item_id: str) -> list[str]:
        return self.items.at[item_id, "roles"].split("|")

    def options(self, item_id: str, current: dict[str, str] | None = None) -> list[str]:
        return self._expand(self.items.at[item_id, "options"], current)

    def rows(self, item_id: str, current: dict[str, str] | None = None) -> list[str]:
        raw = self.items.at[item_id, "rows"]
        return self._expand(raw, current) if raw else []

    def scores(self, item_id: str) -> dict[str, float] | str | None:
        """Label -> score, the raw `count:` spec for grids, or None for unscored items."""
        raw = self.items.at[item_id, "scores"]
        if not raw:
            return None
        if raw.startswith("count:"):
            return raw
        return dict(zip(self.items.at[item_id, "options"].split("|"), map(float, raw.split("|"))))

    def preference_options(self, decision: str, current_state: str) -> list[tuple[str, str]]:
        """(outcome_id, label) offered for a decision given its current state."""
        out = []
        for oid, spec in self.outcomes[decision].items():
            if current_state not in spec.get("offered_when_current", []):
                continue
            label = spec["preference_label"]
            out.append((oid, label[current_state] if isinstance(label, dict) else label))
        return out

    def _expand(self, raw: str, current: dict[str, str] | None) -> list[str]:
        result = []
        for part in raw.split("|"):
            if part.startswith("@preference:"):
                decision = part.split(":", 1)[1]
                state = (current or {}).get(decision)
                if state is None:
                    raise ValueError(f"current state for {decision!r} is needed to expand {part}")
                result += [label for _, label in self.preference_options(decision, state)]
            else:
                result.append(part)
        return result

    # ------------------------------------------------------------------ fact helpers
    def fact_band(self, fact_id: str, value) -> float | None:
        """Map a value to its 1–5 band (numbers via cuts/direction, categories via category_scores)."""
        f = self.facts.loc[fact_id]
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None
        if f["kind"] == "category":
            if not f["category_scores"]:
                return None
            scores = dict(zip(f["categories"].split("|"), map(float, f["category_scores"].split("|"))))
            return scores.get(str(value))
        if f["direction"] == "none" or not f["cuts"]:
            return None
        cuts = [float(c) for c in f["cuts"].split("|")]
        band = 1 + sum(float(value) >= c for c in cuts)
        return float(band if f["direction"] == "up" else 6 - band)

    def form_spec(self, role: str, system: str, current: dict[str, str],
                  consistency_example: str = "{consistency_example}") -> list[dict]:
        """Questions for one stakeholder group, in page order, with the exact header used in exports."""
        rows = []
        for item_id, it in self.items.sort_values("page", kind="stable").iterrows():
            if role not in it["roles"].split("|"):
                continue
            text = it["text"].replace("{system}", system).replace("{consistency_example}", consistency_example)
            options = [o.replace("{system}", system) for o in self.options(item_id, current)]
            extra = ([DONT_KNOW] if it["dont_know"] == "true" else []) + \
                    ([it["not_applicable"].replace("{system}", system)] if it["not_applicable"] else [])
            grid_rows = self.rows(item_id, current)
            base = {"item_id": item_id, "page": int(it["page"]), "format": it["format"], "text": text,
                    "options": options + extra}
            if grid_rows:
                for r in grid_rows:
                    rows.append({**base, "row": r, "header": f"{text} [{r}]"})
            else:
                rows.append({**base, "row": None, "header": text})
        return rows


def _read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, keep_default_na=False).set_index("id")


def load_instrument(directory: str | Path = "instrument", rules_path: str | Path | None = None) -> Instrument:
    directory = Path(directory)
    rules = yaml.safe_load(Path(rules_path or directory / "decision_rules.yaml").read_text())
    return Instrument(
        items=_read_csv(directory / "items.csv"),
        facts=_read_csv(directory / "facts.csv"),
        governance=_read_csv(directory / "governance.csv"),
        rules=rules,
        outcomes=yaml.safe_load((directory / "outcomes.yaml").read_text()),
        root=directory,
    )


# ====================================================================================== validation

def _conditions(node, where):
    """Yield (where, condition-dict) for every leaf condition in a rule tree."""
    if isinstance(node, dict):
        if "signal" in node:
            yield where, node
        for key, value in node.items():
            if key in ("all", "any", "not", "when", "derive", "then") or isinstance(value, (dict, list)):
                yield from _conditions(value, where)
    elif isinstance(node, list):
        for value in node:
            yield from _conditions(value, where)


def known_areas(ins: Instrument) -> set[tuple[str, str, str]]:
    areas = set()
    for _, r in ins.items.iterrows():
        if r["scored"] == "true":
            for d in (["architecture", "hosting"] if r["decision"] == "both" else [r["decision"]]):
                areas.add((r["block"], d, r["area"]))
    for _, f in ins.facts.iterrows():
        if f["direction"] != "none" or (f["kind"] == "category" and f["category_scores"]):
            areas.add((f["axis"], f["decision"], f["area"]))
    return areas


def signal_known(ins: Instrument, signal: str, areas: set) -> bool:
    p = signal.split(".")
    head = p[0]
    if signal in ins.rules.get("signals", {}):
        return True
    if head in ("fact", "band"):
        return len(p) == 2 and p[1] in ins.facts.index
    if head == "item":
        return len(p) == 2 and p[1] in ins.items.index
    if head in ("need", "capability"):
        return any(a[0] == head and a[1] == p[1] and (len(p) == 2 or a[2] == p[2]) for a in areas)
    if head == "locality":
        return len(p) == 1 or ("locality", "architecture", p[1]) in areas
    if head in ("fit", "requirement"):
        return len(p) == 2 and any(a[0] == head and a[2] == p[1] for a in areas)
    if head == "outcome":
        return len(p) == 2 and p[1] in ins.rules.get("decisions", {})
    return head in SIGNAL_FAMILIES


def validate(ins: Instrument) -> list[str]:
    """Return a list of human-readable errors; empty means the instrument is consistent."""
    errs: list[str] = []
    items, facts, gov, rules = ins.items, ins.facts, ins.governance, ins.rules
    areas = known_areas(ins)

    for item_id, it in items.iterrows():
        roles = it["roles"].split("|")
        if bad := [r for r in roles if r not in ROLES]:
            errs.append(f"item {item_id}: unknown roles {bad}")
        scores = it["scores"]
        if scores and not scores.startswith("count:") and not it["options"].startswith("@"):
            if len(scores.split("|")) != len(it["options"].split("|")):
                errs.append(f"item {item_id}: {len(it['options'].split('|'))} options but {len(scores.split('|'))} scores")
        if it["format"] == "grid" and not it["rows"]:
            errs.append(f"item {item_id}: grid without rows")
        for ref in [x for x in f"{it['options']}|{it['rows']}".split("|") if x.startswith("@preference:")]:
            if ref.split(":", 1)[1] not in ins.outcomes:
                errs.append(f"item {item_id}: unknown reference {ref}")

    def check(signal: str, where: str):
        if not signal_known(ins, signal, areas):
            errs.append(f"{where}: unknown signal {signal}")
        p = signal.split(".")
        if p[0] == "item" and p[1] in items.index and items.at[p[1], "core"] != "true":
            errs.append(f"{where}: rule depends on non-core item {p[1]}")

    def check_tree(node, where: str):
        for w, c in _conditions(node, where):
            for key in ("signal", "ref", "premium"):
                if isinstance(c.get(key), str):
                    check(c[key], w)
            value = c.get("value")
            if isinstance(value, str) and c["signal"].startswith("fact."):
                fid = c["signal"][5:]
                if fid in facts.index and facts.at[fid, "kind"] == "category" \
                        and value not in facts.at[fid, "categories"].split("|"):
                    errs.append(f"{w}: {value!r} is not a category of {fid}")

    for name, spec in rules.get("signals", {}).items():
        check_tree(spec, f"signal {name}")
        for member in spec.get("max_of", []) + spec.get("min_of", []):
            check(member, f"signal {name}")
        if "item" in spec:
            if items.at[spec["item"], "core"] != "true":
                errs.append(f"signal {name}: depends on non-core item {spec['item']}")
            for option in spec.get("share_of", []):
                if option not in items.at[spec["item"], "options"].split("|"):
                    errs.append(f"signal {name}: {option!r} is not an option of {spec['item']}")
    for name, stop in rules.get("hard_stops", {}).items():
        check_tree(stop["when"], f"hard stop {name}")
        if stop.get("perception_check") and stop["perception_check"] not in items.index:
            errs.append(f"hard stop {name}: unknown perception item {stop['perception_check']}")
    for gate, spec in rules.get("gates", {}).items():
        for c in spec["checks"]:
            if c not in gov.index:
                errs.append(f"gate {gate}: unknown governance check {c}")
            elif gov.at[c, "gate"] != gate:
                errs.append(f"gate {gate}: check {c} belongs to gate {gov.at[c, 'gate']}")
        for c in spec.get("corroborated_by", []):
            if c not in items.index:
                errs.append(f"gate {gate}: unknown corroborating item {c}")
            elif items.at[c, "core"] != "true":
                errs.append(f"gate {gate}: corroborating item {c} is not core")
    for c, row in gov.iterrows():
        if row["gate"] not in rules.get("gates", {}):
            errs.append(f"governance {c}: gate {row['gate']} is not defined in the rules")
    for axis, spec in rules.get("axes", {}).items():
        for area in spec.get("areas", []):
            block, decision = axis.split(".")
            if (block, decision, area) not in areas:
                errs.append(f"axes {axis}: unknown sub-area {area}")
    for decision, spec in rules.get("decisions", {}).items():
        ids = [o["id"] for o in spec["outcomes"]]
        for o in spec["outcomes"]:
            where = f"{decision}.{o['id']}"
            if o["id"] not in ins.outcomes.get(decision, {}):
                errs.append(f"{where}: no definition in outcomes.yaml")
            check_tree(o.get("when"), where)
            check_tree(o.get("requires_capability"), where)
            for g in o.get("requires_gates", []) + o.get("reports_conditions", []):
                if g not in rules.get("gates", {}):
                    errs.append(f"{where}: unknown gate {g}")
            for h in o.get("blocked_by", []):
                if h not in rules.get("hard_stops", {}):
                    errs.append(f"{where}: unknown hard stop {h}")
        for oid, definition in ins.outcomes.get(decision, {}).items():
            if oid not in ids:
                errs.append(f"{decision}.{oid}: defined in outcomes.yaml but has no rule")
            if "preference_label" not in definition:
                errs.append(f"{decision}.{oid}: no preference_label")
    return errs
