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
    "citations.hosting_constraint": "the hosting constraint that rules options out does not yet cite the external "
                                    "requirement behind it",
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
            unestimated = d == "architecture" and not (dec.get("investment") or {}).get("estimated", True)
            if unestimated:                              # going ahead, but nobody knows what it costs yet
                ask = (f"Approve “{dec['verdict_label']}” in principle and mandate {owner} to estimate it; the budget is "
                       "decided at checkpoint C1 (month 3)" + (f", once {names} have been heard directly." if names else "."))
                not_yet = "Budget and timeline, until the estimate exists."
            else:
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
    brief = {"requests": requests, "scr": _scr(assessment, ctx, decs), "money": _money(assessment, decs) + _sourcing_money(ctx),
             "conditions": _conditions(ctx, decs), "again": _again(ctx, triggers), **_intent(assessment, decs)}
    return _fit(brief, bool(ctx["integrity"]["draft"]))


PAGE_BUDGET = 56      # estimated lines, a first guess only: rendered pages between 53 and 58 fit or not


def _lines(text: str | None, width: int) -> float:
    return -(-len(text) // width) if text else 0


def _fullness(b: dict, draft: bool) -> float:
    """Rough line count of the decision page: full-width requests and situation, then the taller of two columns."""
    full = 0.0
    for q in b["requests"]:
        if q["status"] == "No change":
            full += _lines(q["ask"], 110)
            continue
        full += 1.2 + 1.25 * _lines(q["ask"], 80) + _lines(q.get("not_yet"), 110) + _lines(q.get("budget"), 110)
    full += sum(_lines(b["scr"][k], 85) for k in ("situation", "complication", "resolution"))
    left = 1 + sum(_lines(x, 48) for x in b["money"]) + \
        (1 + sum(_lines(x, 48) for x in b["conditions"]) if b["conditions"] else 0)
    right = 1 + sum(_lines(x, 48) for x in b["again"]) + \
        (1.5 + sum(_lines(x, 48) for x in b["intent_flags"]) if b.get("intent_flags") else 0)
    return full + max(left, right) + (1.5 if draft else 0)


def _pointer(items: list[str], what: str, where: str) -> list[str]:
    return [f"{len(items)} {what} — see {where}."] if len(items) > 1 else items


def _shorter_not_yet(q: dict) -> None:
    text = q.get("not_yet") or ""
    head = text.split(" “")[0].strip()
    if " is not pursued" in text and head:          # the reopen criteria are listed in full in the plan
        q["not_yet"] = head.rstrip(". ") + "."


# Shortening the decision page, least important first; each step is repeated in full elsewhere in the report.
COMPACTION = [
    lambda b: b.update(conditions=_pointer(b["conditions"], "conditions, drafts first", "the Important notice")),
    lambda b: b.update(intent_flags=_pointer(b.get("intent_flags", []), "points where the evidence meets leadership's "
                                             "intent", "Preconditions")),
    lambda b: b.update(again=[g for g in b["again"] if not g.startswith("Month ")]),
    lambda b: b.update(money=b["money"][:3]),
    lambda b: [_shorter_not_yet(q) for q in b["requests"]],
]


def compact(full: dict, steps: int) -> dict:
    import copy
    b = copy.deepcopy(full)
    for step in COMPACTION[:steps]:
        step(b)
    return b


def _fit(b: dict, draft: bool) -> dict:
    """A first guess at how much to shorten; the report build measures the rendered page and shortens further."""
    steps = 0
    while steps < len(COMPACTION) and _fullness(compact(b, steps), draft) > PAGE_BUDGET:
        steps += 1
    out = compact(b, steps)
    out["_full"], out["_steps"] = b, steps
    return out


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
                    "tone": p["tone"], "ask": ask, "not_yet": not_yet, "budget": budget, "_merge": (
                        p["verdict"], status) if p["verdict"] == "insufficient_evidence" or
                    (p["verdict"] == "keep_building" and status != "excluded") else None})
    merged = []                                     # parts with the same outcome and no money: one request
    for r in out:
        key = r.pop("_merge")
        same = next((m for m in merged if key and m.get("_key") == key), None)
        if same:
            same["_names"].append(r["decision"].split(" · ", 1)[1])
            continue
        merged.append({**r, "_key": key, "_names": [r["decision"].split(" · ", 1)[1]]})
    for m in merged:
        names = m.pop("_names")
        key = m.pop("_key")
        if len(names) > 1:
            listed = _join(names)
            m["decision"] = f"Build or buy · {listed}"
            m["ask"] = (f"Do not decide yet whether to build or buy {listed}; approve the work that settles it."
                        if key[0] == "insufficient_evidence" else f"Keep building {listed}. No approval is needed.")
    return merged


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
    distributed = ev.current_state.get("architecture") == "distributed"
    cross = eng.facts.get("cross_service_change_pct" if distributed else "cross_team_change_pct")
    unit = "need edits in more than one service" if distributed else "need more than one team"
    if lead and lead.get("Waiting on process", 0) > lead.get("Coordination between teams", 0):
        complication.append(f"Lead time goes mainly to waiting on approvals, testing or environments "
                            f"({lead['Waiting on process']:.0%} of the answers), not to coordination between teams.")
    if lead and lead.get("Coordination between teams", 0) >= 0.5:
        complication.append(f"Changes wait on each other across teams: {lead['Coordination between teams']:.0%} of the "
                            "answers on lead time name coordination"
                            + (f", and {cross.point:g}% of changes {unit}" if cross and cross.point else "") + ".")
    refresh = eng.facts.get("hw_refresh_due_months")
    if host and refresh and refresh.point is not None and eng.config.get("current_hosting") != "cloud":
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
    words = {"improve_current": "Improve / right-size", "move_to_cloud": "Move to cloud", "hybrid": "Hybrid",
             "repatriate": "Move back from cloud"}
    verdict = rows.get(words.get(host["verdict"], ""))   # the recommended path, not merely the cheapest
    out = []
    run = assessment.engagement.facts.get("run_cost_annual")
    if run is not None and run.point:
        out.append(f"Today's run cost: about €{run.point / 1e6:.2f}M a year (invoiced).")
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


MAX_CONDITIONS, MAX_INTENT_FLAGS = 3, 2     # the decision page stays one page; the full lists are elsewhere


def _conditions(ctx: dict, decs: dict) -> list[str]:
    out = []
    integrity = ctx["integrity"]
    if integrity["draft"]:
        out += [f"Draft: {b['title'].lower()}." for b in integrity["blocks"]]
    out += [f"{c['title']}." for c in integrity["caveats"]]
    if len(out) > MAX_CONDITIONS:                    # drafts first, then the caveats; all are in the notice
        out = out[:MAX_CONDITIONS - 1] + [f"And {len(out) - MAX_CONDITIONS + 1} more in the Important notice."]
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


HORIZON = {"grow": "the business area is expected to grow", "hold": "the business area is expected to hold steady",
           "shrink": "the business area is expected to shrink", "may_be_sold_or_closed": "the business area may be sold or closed"}
OUTCOMES = {"lower_run_cost": "lower running cost", "faster_delivery": "faster delivery", "fewer_outages": "fewer outages",
            "regulatory": "meeting regulatory demands", "scale": "scale or new markets",
            "less_dependence": "less dependence on key people or vendors", "free_money": "freeing money for other priorities"}
TRIGGERS = {"cost_overrun_pct": "cost overrun above {value:g}%", "delay_months": "delay of more than {value:g} months",
            "customer_outage": "a visible customer-facing outage", "initiative_delayed": "a key business initiative delayed",
            "sponsor_leaves": "loss of the sponsor"}
CONSTRAINT = {"capital_capped": "capital spending is capped", "operating_capped": "operating spending is capped",
              "both": "capital and operating spending are capped"}
MOVES = ("move_to_cloud", "hybrid", "repatriate")


def _intent(assessment, decs: dict) -> dict:
    """What leadership set before the results (intent.yaml): `intent` lists it all (Preconditions section),
    `intent_flags` only where the evidence meets it (decision page). Never changes a verdict."""
    eng = assessment.engagement
    intent = eng.intent or {}
    if not intent:
        return {"intent": [], "intent_flags": []}
    from .integrity import _date
    out, flags = [], []
    on = _date(intent.get("signed_on"))
    head = [HORIZON[intent["business_horizon"]]] if intent.get("business_horizon") in HORIZON else []
    tops = [OUTCOMES.get(o, o.replace("_", " ")) for o in intent.get("top_outcomes") or []][:3]
    if tops:
        head.append(f"priorities: {_join(tops)}")
    if head:
        out.append(f"Set {f'on {on.day} {on:%B %Y} ' if on else ''}by {intent.get('signed_by', 'the sponsor')}: "
                   + "; ".join(head) + ".")
    host, arch = decs.get("hosting") or {}, decs.get("architecture") or {}
    programme = host.get("verdict") in MOVES or arch.get("verdict") not in (None, "insufficient_evidence", "stay_and_improve")
    if intent.get("business_horizon") in ("shrink", "may_be_sold_or_closed") and programme:
        flags.append("A programme that pays back over several years may not pay back before the business area changes; "
                     "weigh the payback against that horizon.")
    life = eng.answers[(eng.answers["item_id"] == "LF01") & (eng.answers["label"].fillna("") != "")
                       & ~eng.answers["dont_know"].fillna(False).astype(bool)]["label"]
    min_n = eng.instrument.rules.get("evidence", {}).get("min_role_n", 5)
    if programme and len(life) >= min_n and (life == "Less than 2 years").mean() >= 0.5:
        flags.append("Most of technology and business leadership expect the system to be retired within two years; a "
                     "programme on it would have to pay back before then.")
    triggers = []
    for t in intent.get("stop_triggers") or []:
        words = TRIGGERS.get(t.get("trigger"), t.get("text") or str(t.get("trigger", "")).replace("_", " "))
        triggers.append(words.format(value=float(t.get("value") or 0)))
    if triggers:
        line = f"Stop or pause on: {_join(triggers)}."
        cost = next((t for t in intent.get("stop_triggers") or [] if t.get("trigger") == "cost_overrun_pct"), None)
        past = eng.facts.get("past_programme_overrun_pct")
        out.append(line)
        if cost and past is not None and past.point is not None and float(cost.get("value") or 0) > float(past.point):
            flags.append(f"The stop trigger for cost ({float(cost['value']):g}% overrun) is looser than past programmes' "
                         f"typical overrun ({past.point:g}%): a programme that overran as they did would not trip it.")
    funded, dual = intent.get("funded_parallel_running_months"), eng.facts.get("dual_run_months")
    if host.get("verdict") in MOVES and funded is not None and dual is not None and dual.point is not None \
            and float(dual.point) > float(funded):
        flags.append(f"Running old and new side by side is estimated at {dual.point:g} months; the funding leadership "
                     f"set covers {float(funded):g}.")
    sc = intent.get("spending_constraint") or {}
    if sc.get("type") in CONSTRAINT:
        until = _date(sc.get("expires_on"))
        hit = ""
        if sc["type"] in ("capital_capped", "both") and host.get("verdict") in ("stay_as_is", "improve_current") and \
                eng.config.get("current_hosting", "own_infrastructure") != "cloud" and eng.facts.get("hw_refresh_capex"):
            hit = " The hardware refresh on the recommended hosting path needs capital."
        if sc["type"] in ("operating_capped", "both") and host.get("verdict") in ("move_to_cloud", "hybrid"):
            hit = " The recommended hosting path raises operating spending."
        out.append(f"Financing: {CONSTRAINT[sc['type']]}" + (f" until {until:%B %Y}" if until else "") +
                   "; shown beside the cost comparison, not folded into it.")
        if hit:
            flags.append(f"{CONSTRAINT[sc['type']][0].upper()}{CONSTRAINT[sc['type']][1:]}" +
                         (f" until {until:%B %Y}" if until else "") + "." + hit)
    pc = intent.get("prior_commitment") or {}
    if pc.get("status") in ("formal", "contractual"):
        flags.append(f"A direction was committed {pc['status'] == 'contractual' and 'by contract' or 'formally'} before "
                     "this assessment" + (f" ({_lower(pc['detail'].rstrip('.'))})" if pc.get("detail") else "") +
                     "; the recommendation was reached on the evidence alone.")
    dates = [f"{d.get('what', 'commitment')} ({_date(d.get('date')):%B %Y})" if _date(d.get("date")) else d.get("what", "")
             for d in intent.get("committed_dates") or []]
    if dates:
        out.append(f"Already promised to customers or regulators: {_join([x for x in dates if x])}.")
    shown = flags if len(flags) <= MAX_INTENT_FLAGS else \
        flags[:MAX_INTENT_FLAGS - 1] + [f"And {len(flags) - MAX_INTENT_FLAGS + 1} more under Preconditions."]
    return {"intent": out + flags, "intent_flags": shown}
