"""The decision page: what the leadership team is asked to decide, on one page, from the findings of the report.

Built only from the verdicts, their status and the findings already in the report context — never from
preferences — so it stays neutral: with insufficient evidence it requests the work that settles the evidence, not a
path. Sections: decision requested (per decision), situation – complication – resolution, the money, conditions,
and when the decision is taken again.
"""

from __future__ import annotations

from .recommend import FIRST_STEP_OWNER


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
        if dec["verdict"] == "insufficient_evidence":
            settle = [u["text"] for u in dec.get("uncertain", [])][:2]
            ask = ("Do not choose a path yet. Approve the work that settles the evidence"
                   + (f": {_join([_lower(s.rstrip('.')) for s in settle])}" if settle else "") + ".")
            not_yet = f"Any {d} programme, until the assessment is re-run."
        elif dec["status"] == "prepare_first":
            ask = (f"Approve the preparation for “{dec['verdict_label']}”, led by {owner}: "
                   f"{_join([_lower(i) for i in open_items])}.")
            not_yet = "Budget and timeline for the path itself; decided at checkpoint C1 (month 3)."
        else:
            ask = f"Approve “{dec['verdict_label']}” and mandate {owner} to start."
            not_yet = None
        alt = triggers.get(d)
        if alt:
            reopen = f"“{alt['alternative']}” is not pursued; it is reopened only under the agreed criteria."
            not_yet = f"{not_yet} {reopen}" if not_yet else reopen
        requests.append({"decision": dec["title"], "path": dec["verdict_label"], "status": dec["status_label"],
                         "tone": dec["tone"], "ask": ask, "not_yet": not_yet, "budget": _budget(assessment, d, dec)})
    return {"requests": requests, "scr": _scr(assessment, ctx, decs), "money": _money(assessment, decs),
            "conditions": _conditions(ctx, decs), "again": _again(ctx, triggers)}


def _budget(assessment, d: str, dec: dict) -> str | None:
    eng = assessment.engagement
    show = (eng.config.get("report") or {}).get("show_amounts", True)
    if d == "hosting" and dec["verdict"] == "improve_current":
        inv = eng.facts.get("automation_investment")
        if inv and inv.point and show:
            return f"First phase: €{inv.point / 1e3:,.0f}k one-off for automation."
    if d == "architecture" and dec["verdict"] not in ("insufficient_evidence", "stay_and_improve"):
        return ("Investment not yet estimated: the technology lead and a second estimator provide it before "
                "checkpoint C1.")
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
                  for d in decs.values() if d["verdict"] != "insufficient_evidence"]
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
        out.append("The restructuring is not yet costed.")
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
    for t in triggers.values():
        out.append(f"{t['decision'].title()}: “{t['alternative']}” can be reopened at {t['when']}, only under the "
                   "agreed criteria.")
    return out
