"""Cross-reference check for instrument/ (items, facts, governance, rules, outcomes). Usage: python tools/check_instrument.py .

Interim tool for M0; superseded by schema validation in mra/instrument.py (M1)."""
import csv, yaml, sys
root = sys.argv[1]
items = {r["id"]: r for r in csv.DictReader(open(f"{root}/instrument/items.csv"))}
facts = {r["id"]: r for r in csv.DictReader(open(f"{root}/instrument/facts.csv"))}
gov = {r["id"]: r for r in csv.DictReader(open(f"{root}/instrument/governance.csv"))}
rules = yaml.safe_load(open(f"{root}/instrument/decision_rules.yaml"))
outs = yaml.safe_load(open(f"{root}/instrument/outcomes.yaml"))
errs, warn = [], []

areas = {}
for r in items.values():
    if r["scored"] == "true": areas.setdefault((r["block"], r["decision"]), set()).add(r["area"])
for r in facts.values():
    if r["direction"] != "none" or r["kind"] == "category" and r["category_scores"]:
        areas.setdefault((r["axis"], r["decision"]), set()).add(r["area"])
def has(block, dec, area=None):
    s = areas.get((block, dec), set()) | areas.get((block, "both"), set())
    return bool(s) if area is None else area in s

sigs = set(rules["signals"])
def check_signal(s, where):
    p = s.split(".")
    ok = (s in sigs or (p[0] == "fact" and p[1] in facts) or (p[0] == "band" and p[1] in facts)
          or (p[0] == "item" and p[1] in items)
          or (p[0] in ("need", "capability") and (has(p[0], p[1]) if len(p) == 2 else has(p[0], p[1], p[2])))
          or (p[0] == "locality" and (len(p) == 1 or has("locality", "architecture", p[1])))
          or (p[0] == "fit" and has("fit", "architecture", p[1]))
          or (p[0] == "requirement" and any(i["block"] == "requirement" and i["area"] == p[1] for i in items.values()))
          or p[0] in ("tco_ratio", "payback_months", "tco_saving_fte") or (p[0] == "outcome" and p[1] in rules["decisions"]))
    if not ok: errs.append(f"{where}: unknown signal {s}")
    if p[0] == "item" and p[1] in items and items[p[1]]["core"] != "true":
        errs.append(f"{where}: rule references non-core item {p[1]}")
    if p[0] == "fact" and p[1] in facts and facts[p[1]]["required"] == "false":
        warn.append(f"{where}: rule uses optional fact {p[1]} (missing → unresolved)")
def walk(c, where):
    if isinstance(c, dict):
        for k in ("signal", "ref", "premium"):
            if isinstance(c.get(k), str): check_signal(c[k], where)
        for v in c.values(): walk(v, where)
    elif isinstance(c, list):
        for v in c: walk(v, where)
    elif isinstance(c, str) and c.count(".") >= 1 and c.split(".")[0] in ("need", "capability", "fact", "locality", "fit"):
        check_signal(c, where)

for name, s in rules["signals"].items():
    walk(s, f"signal {name}")
    if "item" in s:
        if items[s["item"]]["core"] != "true": errs.append(f"signal {name}: non-core item")
        for o in s.get("share_of", []):
            if o not in items[s["item"]]["options"].split("|"): errs.append(f"signal {name}: option not in {s['item']}: {o}")
for name, h in rules["hard_stops"].items():
    walk(h["when"], f"hard stop {name}")
    pc = h.get("perception_check")
    if pc and pc not in items: errs.append(f"hard stop {name}: unknown perception item {pc}")
    c = h["when"]
    if "signal" in c and c["signal"].startswith("fact.") and facts[c["signal"][5:]]["kind"] == "category":
        if c["value"] not in facts[c["signal"][5:]]["categories"].split("|"): errs.append(f"hard stop {name}: bad category {c['value']}")
for g, spec in rules["gates"].items():
    for c in spec["checks"]:
        if c not in gov: errs.append(f"gate {g}: unknown check {c}")
        elif gov[c]["gate"] != g: errs.append(f"gate {g}: check {c} declares gate {gov[c]['gate']}")
    for c in spec.get("corroborated_by", []):
        if c not in items: errs.append(f"gate {g}: unknown corroborating item {c}")
        elif items[c]["core"] != "true": errs.append(f"gate {g}: corroborating item {c} not core")
    if "mandatory_if" in spec: walk(spec["mandatory_if"], f"gate {g}")
for c in gov.values():
    if c["gate"] not in rules["gates"]: errs.append(f"governance {c['id']}: gate {c['gate']} not in rules")
for d, spec in rules["decisions"].items():
    for o in spec["outcomes"]:
        where = f"{d}.{o['id']}"
        if o["id"] not in outs[d]: errs.append(f"{where}: no outcome definition")
        walk(o.get("when"), where); walk(o.get("requires_capability"), where)
        for g in o.get("requires_gates", []) + o.get("reports_conditions", []):
            if g not in rules["gates"]: errs.append(f"{where}: unknown gate {g}")
        for h in o.get("blocked_by", []):
            if h not in rules["hard_stops"]: errs.append(f"{where}: unknown hard stop {h}")
    for oid in outs[d]:
        if oid not in [o["id"] for o in spec["outcomes"]]: errs.append(f"{d}.{oid}: defined but no rule")
for i in items.values():
    if i["options"].startswith("@preference:") or "@preference:" in i["rows"]:
        for ref in [x for x in (i["options"] + "|" + i["rows"]).split("|") if x.startswith("@preference:")]:
            if ref.split(":")[1] not in outs: errs.append(f"item {i['id']}: bad preference ref {ref}")
for d in ("architecture", "hosting"):
    for oid, o in outs[d].items():
        if "preference_label" not in o: errs.append(f"{d}.{oid}: no preference_label")
print("\n".join(["ERROR " + e for e in errs] + ["warn  " + w for w in sorted(set(warn))]) or "")
print(f"{'FAILED' if errs else 'OK'}: {len(items)} items, {len(facts)} facts, {len(gov)} governance checks, "
      f"{len(rules['gates'])} gates, {len(rules['hard_stops'])} hard stops, "
      f"{sum(len(s['outcomes']) for s in rules['decisions'].values())} outcome rules")
