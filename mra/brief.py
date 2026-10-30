"""The decision page: what the leadership team is asked to decide, on one page, from the findings of the report.

Built only from the verdicts, their status and the findings already in the report context — never from
preferences — so it stays neutral: with insufficient evidence it requests the work that settles the evidence, not a
path. Sections: decision requested (per decision), situation – complication – resolution, the money, conditions,
and when the decision is taken again.
"""

from __future__ import annotations

from .recommend import FIRST_STEP_OWNER


BLOCK_REASON = {
    "run_cost_reconciliation": "the invoiced run cost is not yet reconciled with what the cost model accounts for",
    "rules_signed_off": "the decision rules were not signed off before the facts were frozen",
}


def _named(role: str, people: dict) -> str:
    name = people.get(role.lower().replace(" ", "_"))
    return f"{role} ({name})" if name else role


def _lower(text: str) -> str:
    return text[0].lower() + text[1:] if text else text


def _join(words: list[str]) -> str:
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


def build(assessment, ctx: dict) -> dict:
    eng = assessment.engagement
    people = {k: v for k, v in (eng.config.get("people") or {}).items() if v}
    decs = {d["id"]: d for d in ctx["decisions"]}
    triggers = {t["decision"]: t for t in ctx.get("triggers", [])}
    requests = []
    for d, dec in decs.items():
        owner = _named(FIRST_STEP_OWNER.get(d, "Sponsor"), people)
        open_items = [g["label"] for g in dec.get("gates", []) if g["status"] != "pass"] + dec.get("hard_stops", []) + \
            [f"build {_lower(c)}" for c in dec.get("capabilities", [])]
        blocked = [i for i in (ctx.get("integrity") or {}).get("blocks", []) if d in (i.get("decisions") or [])]
        if dec["verdict"] == "insufficient_evidence":
            inputs = [u["text"].split(":")[0] for u in dec.get("uncertain", [])][:3]
            leaning = f" It leans towards “{dec['leaning_label']}”." if dec.get("leaning_label") else ""
            ask = ("Do not choose a path yet. Approve the work that settles the evidence"
                   + (f" — firm up {_join([_lower(s) for s in inputs])} — and re-run the assessment by checkpoint C1 "
                      "(month 3)" if inputs else "")
                   + "." + leaning)
            not_yet = f"Any {d} programme, until the assessment is re-run."
        elif blocked:
            why = BLOCK_REASON.get(blocked[0]["id"], _lower(blocked[0]["title"]))
            ask = (f"Do not approve a {d} path yet: the evidence supports “{dec['verdict_label']}” today, but "
                   f"{why}, and that could change it.")
            not_yet = f"Any {d} programme, until the issue is resolved and the assessment re-run."
        elif dec["status"] == "prepare_first":
            ask = (f"Approve the preparation for “{dec['verdict_label']}”, led by {owner}: "
                   f"{_join([_lower(i) for i in open_items])}. No programme budget yet; the time it takes must be "
                   "protected" + (" (see the capacity note)." if (ctx.get("roadmap") or {}).get("load") else "."))
            not_yet = "Budget and timeline for the path itself; decided at checkpoint C1 (month 3)."
        else:
            missing = next((i for i in (ctx.get("integrity") or {}).get("caveats", [])
                            if i["id"] == f"critical_groups.{d}"), None)
            names = _join(missing["groups"]) if missing and missing.get("groups") else None
            ask = f"Approve “{dec['verdict_label']}” and mandate {owner} to start" + \
                (f", once {names} have been heard directly." if names else ".")
            not_yet = None
        alt = triggers.get(d)
        if alt:
            reopen = f"“{alt['alternative']}” is not pursued; it is reopened only under the agreed criteria."
            not_yet = f"{not_yet} {reopen}" if not_yet else reopen
        budget = _budget(assessment, d, dec)
        if blocked and dec["verdict"] != "insufficient_evidence":
            budget = f"Once approved — {budget[0].lower() + budget[1:]}" if budget else None
        requests.append({"decision": dec["title"], "path": dec["verdict_label"],
                         "status": "On hold" if blocked and dec["verdict"] != "insufficient_evidence" else dec["status_label"],
                         "tone": "neutral" if blocked else dec["tone"], "ask": ask, "not_yet": not_yet, "budget": budget})
    requests += _sourcing_requests(assessment, ctx, people)
    return {"requests": requests, "scr": _scr(assessment, ctx, decs), "money": _money(assessment, decs) + _sourcing_money(ctx),
            "conditions": _conditions(ctx, decs), "again": _again(ctx, triggers)}


def _sourcing_requests(assessment, ctx: dict, people: dict) -> list[dict]:
    block = ctx.get("sourcing") or {}
    owner = _named("Technology lead", people)
    out = []
    for p in block.get("parts", []):
        name, status = p["name"], p["status"]
        budget = not_yet = None
        if p["verdict"] == "insufficient_evidence":
            ask = f"Do not decide yet whether to build or buy {name}; approve the work that settles it."
        elif p["verdict"] == "keep_building" and status == "excluded":
            ask = f"Keep building {name}: replacing it is ruled out — {_lower(p['hard_stops'][0])}."
        elif p["verdict"] == "keep_building":
            ask = f"Keep building {name}. No approval is needed."
        elif status == "prepare_first":
            ask = (f"Approve the preparation for replacing {name} with a product, led by {owner}: separate its data "
                   "from the other parts first.")
            not_yet = "Choosing and contracting the product; decided after the proof of concept."
        else:
            ask = (f"Approve replacing {name} with a product, led by {owner}: start with a proof of concept and an "
                   "export test.")
            not_yet = "Signing the product contract, until the proof of concept confirms coverage and the exit plan."
        if p["verdict"] == "replace_with_product" and p.get("costs") and p.get("show_amounts"):
            saving = (p["build_eur"] - p["buy_eur"]) / 5
            budget = (f"One-off integration and migration: {p['costs']['integration']}; saves about "
                      f"€{saving / 1e3:,.0f}k a year over five years once switched.")
        out.append({"decision": f"Build or buy · {name}", "path": p["label"], "status": p["status_label"],
                    "tone": p["tone"], "ask": ask, "not_yet": not_yet, "budget": budget})
    return out


def _sourcing_money(ctx: dict) -> list[str]:
    out = []
    for p in (ctx.get("sourcing") or {}).get("parts", []):
        if p["verdict"] == "replace_with_product" and p.get("costs") and p.get("show_amounts"):
            out.append(f"Replacing {p['name'].lower()} costs {p['costs']['buy']} over five years against "
                       f"{p['costs']['build']} for keeping it.")
    return out


def _budget(assessment, d: str, dec: dict) -> str | None:
    eng = assessment.engagement
    show = (eng.config.get("report") or {}).get("show_amounts", True)
    if d == "hosting" and dec["verdict"] == "improve_current":
        inv = eng.facts.get("automation_investment")
        if inv and inv.point and show:
            refresh = next((c for c in (dec.get("calendar") or []) if c["event"].startswith("Hardware refresh")), None)
            later = (f" The hardware refresh (month {refresh['month']:g}) is not part of this approval; it is decided "
                     "at the hosting review." if refresh else "")
            return f"First phase: €{inv.point / 1e3:,.0f}k one-off for automation.{later}"
    if d == "architecture" and dec["verdict"] not in ("insufficient_evidence", "stay_and_improve"):
        inv = dec.get("investment") or {}
        if not inv.get("estimated"):
            return ("Investment not yet estimated: the technology lead and a second estimator provide it before "
                    "checkpoint C1.")
        amount = (f"€{inv['cost'] / 1e3:,.0f}k (€{inv['cost_low'] / 1e3:,.0f}k–€{inv['cost_high'] / 1e3:,.0f}k), "
                  if show else "")
        when = "for decision at checkpoint C1" if dec["status"] == "prepare_first" else "from now"
        return (f"Estimated cost of the first steps: {amount}about {inv['fte']:.0f} FTE for {inv['months']:.0f} months, "
                f"{when}.")
    return None


def _scr(assessment, ctx: dict, decs: dict) -> dict:
    eng, ev = assessment.engagement, assessment.evidence
    arch, host = decs.get("architecture"), decs.get("hosting")
    system = eng.system[0].upper() + eng.system[1:]
    situation = [f"{system} runs as {arch['current'] if arch else 'one system'}"
                 + (f" on {host['current']}" if host else "") + "."]
    bm = (ctx["readiness"].get("benchmark") or {}).get("rows", [])
    speed = [r for r in bm if r["metric"] in ("leadtime", "deployfreq") and r["score"] is not None]
    if speed and not any(r["position"] == "below" for r in speed):
        provisional = any(i["id"] == "baseline_unverified" for i in ctx["integrity"]["issues"])
        situation.append("Its delivery pipeline performs around the industry average"
                         + (" (on measures still to be verified)." if provisional else "."))
    complication = []
    lead = next((e["data"]["by_group"]["All respondents asked"] for e in ctx["exhibits"]
                 if e["insight"]["id"] == "architecture.leadtime"), None)
    cross = eng.facts.get("cross_team_change_pct")
    if lead and lead.get("Waiting on process", 0) > lead.get("Coordination between teams", 0):
        complication.append(f"Lead time goes mainly to waiting on approvals, testing or environments "
                            f"({lead['Waiting on process']:.0%} of the answers), not to coordination between teams.")
    if lead and lead.get("Coordination between teams", 0) >= 0.5:
        complication.append(f"Changes wait on each other across teams: {lead['Coordination between teams']:.0%} of the "
                            "answers on lead time name coordination"
                            + (f", and {cross.point:g}% of changes need more than one team" if cross and cross.point else "")
                            + ".")
    refresh = eng.facts.get("hw_refresh_due_months")
    if host and refresh and refresh.point is not None:
        complication.append(f"The hardware refresh falls due in month {refresh.point:g}.")
    if any(i["id"] == "disputed_claims.process_not_coupling" for i in ctx["integrity"]["issues"]) or \
            any("leadership" in r["title"].lower() for r in ctx["risks"]["risks"]):
        complication.append("Groups disagree on the cause and the cure, including within leadership.")
    resolution = [f"{d['title']}: {_lower(d['verdict_label'])}"
                  + (" — once the preconditions are in place" if d["status"] == "prepare_first" else "") + "."
                  if d["verdict"] != "insufficient_evidence" else
                  f"{d['title']}: not yet decided" + (f"; the evidence leans towards {_lower(d['leaning_label'])}"
                                                      if d.get("leaning_label") else "") + "."
                  for d in decs.values()]
    parts = (ctx.get("sourcing") or {}).get("parts", [])
    replace = [p["name"].lower() + (" (after separating its data)" if p["status"] == "prepare_first" else "")
               for p in parts if p["verdict"] == "replace_with_product"]
    keep = [p["name"].lower() for p in parts if p["verdict"] == "keep_building"]
    if replace or keep:
        resolution.append("Build or buy: " + "; ".join(
            ([f"replace {_join(replace)} with a product"] if replace else []) +
            ([f"keep building {_join(keep)}"] if keep else [])) + ".")
    return {"situation": " ".join(situation), "complication": " ".join(complication), "resolution": " ".join(resolution)}


def _money(assessment, decs: dict) -> list[str]:
    host = decs.get("hosting")
    if not host or not host.get("economics") or not host.get("show_amounts"):
        return []
    rows = {r["option"]: r for r in host["economics"]}
    keep = rows.get("Keep as is")
    verdict = next((r for r in host["economics"] if r["option"] != "Keep as is" and r["ratio"] ==
                    min(x["ratio"] for x in host["economics"])), None)
    out = []
    if keep:
        out.append(f"Doing nothing on hosting costs {keep['eur']} over five years.")
    if verdict and keep and host["verdict"] != "stay_as_is" and verdict["saving_eur"]:
        out.append(f"{verdict['option']} costs {verdict['eur']} ({verdict['eur_range']}), a saving of "
                   f"{verdict['saving_eur'].lstrip('+')} a year.")
    for c in host.get("calendar", []):
        if c["event"].startswith("Hardware refresh") and "less" in c["action"]:
            out.append("Right-sizing before the refresh lowers it by " + c["action"].split("about ")[1].split(" less")[0] + ".")
    arch = decs.get("architecture")
    if arch and arch["verdict"] not in ("insufficient_evidence", "stay_and_improve"):
        inv = arch.get("investment") or {}
        out.append(f"The restructuring's first steps cost about €{inv['cost'] / 1e3:,.0f}k "
                   f"(€{inv['cost_low'] / 1e3:,.0f}k–€{inv['cost_high'] / 1e3:,.0f}k)." if inv.get("estimated") else
                   "The restructuring is not yet costed.")
    return out


def _conditions(ctx: dict, decs: dict) -> list[str]:
    out = []
    integrity = ctx["integrity"]
    if integrity["draft"]:
        out += [f"Draft: {b['title'].lower()}." for b in integrity["blocks"]]
    out += [f"{c['title']}." for c in integrity["caveats"]]
    return out


def _again(ctx: dict, triggers: dict) -> list[str]:
    out = [f"Checkpoint C{i + 1} (month {g['month']}): {_lower(g['label'])}." for i, g in enumerate(ctx["roadmap"]["gates"])]
    host = next((d for d in ctx["decisions"] if d["id"] == "hosting"), {})
    out += [f"Month {c['month']:g}: {_lower(c['event'])}." for c in host.get("calendar", []) if c["month"] > 0
            and c["event"] != "Colocation contract ends"]
    reopen = list(triggers.values()) + [t for t in ctx.get("triggers", []) if t["decision"].startswith("sourcing:")]
    if reopen:
        out.append(f"Each decision is reopened only under criteria agreed now ({len(reopen)} in the plan), at the "
                   "checkpoint or date set for it.")
    return out
