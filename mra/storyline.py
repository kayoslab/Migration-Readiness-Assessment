"""Storyline and "so what" for every exhibit, written from the complete findings rather than the exhibit alone.

Each exhibit gets a role in the report's argument (why this path, how robust the case is, what must be built, who
needs bringing along, what happens first, how we compare) and a "so what" of up to three parts:

- means: what the exhibit implies for the recommended path;
- connects: how it relates to another finding — another exhibit, the options considered, a risk;
- therefore: the next step, risk, measure or checkpoint it feeds.

A "so what" is a list of segments — text, or a reference to an exhibit, step, risk, section or checkpoint — so the
template can print live cross-references ("Exhibit 12", "step 13", "risk R2"). Only the `means` sentence may be
polished by the narrative writer; references always come from here. `check` flags any "so what" that links to
nothing or restates its title.
"""

from __future__ import annotations

import re

from .explain import outcome_label
from .instrument import _conditions
from .readiness import _label as area_label, _sub_area_name

ROLE = {
    "probabilities": "Why this path", "map": "Why this path", "leadtime": "Why this path", "tco": "Why this path",
    "tornado": "How robust the case is",
    "preferences": "Who needs bringing along", "stakes": "Who needs bringing along",
    "people.map": "Who needs bringing along", "people.divergence": "What must be clarified",
    "readiness.matrix": "What must be built", "readiness.weakest": "What must be built",
    "readiness.benchmark": "How we compare", "plan.roadmap": "What happens first",
}
SECTIONS = {"preconditions": "the preconditions chapter", "measures": "the success measures",
            "risks": "the risk register", "assumptions": "the key assumptions"}


# ---------------------------------------------------------------------------------------- segments

def T(text: str) -> dict:
    return {"t": text}


def X(eid: str) -> dict:
    return {"ref": "exhibit", "id": eid}


def S(no: int) -> dict:
    return {"ref": "step", "no": no}


def R(rid: str) -> dict:
    return {"ref": "risk", "id": rid}


def SEC(sid: str, name: str | None = None) -> dict:
    return {"ref": "section", "id": sid, "name": name or SECTIONS.get(sid, sid)}


def C(no: int) -> dict:
    return {"ref": "checkpoint", "no": no}


def replace_means(segments: list[dict], sentence: str) -> list[dict]:
    """Swap the first sentence (the "means") for a polished one; references are left untouched."""
    if not segments or "t" not in segments[0]:
        return segments
    head = segments[0]["t"]
    cut = re.search(r"(?<=[.!?])\s", head)
    if not cut and not (len(segments) == 1 and head.rstrip().endswith((".", "!", "?"))):
        return segments                                # the first sentence runs into a reference: keep it
    rest = head[cut.end():] if cut else ""
    return [T(sentence.strip() + (" " + rest if rest else (" " if len(segments) > 1 else "")))] + segments[1:]


def polish_ok(segments: list[dict], sentence: str) -> bool:
    """A polished "means" must be short and must not repeat the sentence that follows it."""
    if len(sentence.split()) > 40:
        return False
    words = lambda text: set(re.findall(r"[a-z]{5,}", text.lower()))      # noqa: E731
    rest = plain(replace_means(segments, "X."))[2:].strip()
    following = re.split(r"(?<=[.!?])\s", rest, maxsplit=1)[0]
    w = words(following)
    return not w or len(w & words(sentence)) / len(w) <= 0.4


def plain(segments: list[dict]) -> str:
    """Readable text of a "so what" (references written out), for checks and the narrative writer."""
    out = []
    for s in segments:
        if "t" in s:
            out.append(s["t"])
        elif s["ref"] == "exhibit":
            out.append(f"[exhibit {s['id']}]")
        elif s["ref"] == "step":
            out.append(f"step {s['no']}")
        elif s["ref"] == "risk":
            out.append(f"risk {s['id']}")
        elif s["ref"] == "checkpoint":
            out.append(f"checkpoint C{s['no']}")
        else:
            out.append(s["name"])
    return "".join(out)


# ---------------------------------------------------------------------------------------- the findings

class Findings:
    """Lookups across the whole report context."""

    def __init__(self, assessment, ctx: dict):
        self.a, self.ctx = assessment, ctx
        self.ins = assessment.engagement.instrument
        self.dec = {d["id"]: d for d in ctx["decisions"]}
        self.present = {e["insight"]["id"] for e in ctx["exhibits"]}
        self.data = {e["insight"]["id"]: e["data"] for e in ctx["exhibits"]}
        self.steps = ctx["steps"]
        self.risks = ctx["risks"]["risks"]
        self.measures = ctx["measures"]
        self.stake_map = {r["group"]: r for r in ctx["stakes"].get("map", [])}
        self.caveats = (ctx.get("integrity") or {}).get("caveats", [])

    def caveated(self, issue_id: str) -> bool:
        return any(c["id"] == issue_id for c in self.caveats)

    def label(self, d: str, oid: str | None) -> str:
        return outcome_label(self.ins, d, oid) if oid else ""

    def target(self, d: str) -> str | None:
        r = self.a.results[d]
        return r.verdict if r.verdict != "insufficient_evidence" else r.leaning

    def step(self, pred) -> int | None:
        return next((s["no"] for s in self.steps if pred(s)), None)

    def risk(self, pred) -> str | None:
        return next((r["id"] for r in self.risks if pred(r)), None)

    def exhibit(self, eid: str) -> list[dict]:
        return [X(eid)] if eid in self.present else []

    def needed_by(self, sub: str) -> dict[str, list[str]]:
        """Outcomes (per decision) whose capability requirements involve this sub-area or one of its facts."""
        parts = sub.split(".")
        facts = set()
        if len(parts) == 3:
            f = self.ins.facts
            facts = {f"fact.{i}" for i in f.index[(f["axis"] == parts[0]) & (f["decision"] == parts[1]) & (f["area"] == parts[2])]}
        out: dict[str, list[str]] = {}
        for d, spec in self.ins.rules["decisions"].items():
            for o in spec["outcomes"]:
                sigs = {c["signal"] for _, c in _conditions(o.get("requires_capability", []), "")}
                if any(s == sub or s.startswith(sub + ".") or s in facts for s in sigs):
                    out.setdefault(d, []).append(o["id"])
        return out

    def area_sub(self, label: str) -> str | None:
        items = self.ins.items
        for _, it in items[items["scored"] == "true"].iterrows():
            if it["block"] not in ("capability", "fit", "alignment", "governance"):
                continue
            sub = _sub_area_name(it)
            if area_label(sub, self.ins) == label:
                return sub
        return None

    def preferred(self, d: str, group: str) -> tuple[str, float] | None:
        st = self.a.stakes
        shares = (st.preferences.get(d, {}).get("by_group", {}) if st else {}).get(group)
        if not shares:
            return None
        o = max(shares, key=shares.get)
        return o, shares[o]


def _pct(x: float) -> str:
    return f"{x:.0%}"


def _join(words: list[str]) -> str:
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


# ---------------------------------------------------------------------------------------- composers

def _probabilities(f: Findings, d: str) -> list[dict]:
    r, dec = f.a.results[d], f.dec[d]
    if r.verdict == "insufficient_evidence":
        out = [T(f"The evidence does not yet single out one path; it leans towards “{f.label(d, r.leaning)}”. ")]
        rid = f.risk(lambda x: x["decision"] == d and x["kind"] == "evidence")
        out += [T("The inputs that would settle it are set out under “where the evidence is uncertain”"),
                *([T(" and in "), R(rid)] if rid else []), T(".")]
        return out
    others = sorted(((p, o) for o, p in r.distribution.items() if o != r.verdict), reverse=True)
    out = [T("The direction is settled: no alternative comes close. ") if not others or others[0][0] < 0.1 else
           T(f"The direction holds, with “{f.label(d, others[0][1])}” the nearest alternative ({_pct(others[0][0])}). ")]
    open_gates = [g["label"].lower() for g in dec.get("gates", []) if g["status"] != "pass"]
    open_items = open_gates + [h.lower() for h in dec.get("hard_stops", [])] + \
        [c[0].lower() + c[1:] for c in dec.get("capabilities", [])]
    if r.status == "prepare_first" and open_items:
        open_gates = open_items
        no = f.step(lambda s: s["decision"] == d and s["phase"] in ("before_commitment", "capability"))
        rid = f.risk(lambda x: x["decision"] == d and x["kind"] == "governance")
        gates_open = any(g["status"] != "pass" for g in dec.get("gates", []))
        out += [T(f"What remains open is readiness, not direction: {_join(open_gates)}"),
                *([T(" ("), SEC("preconditions"), T(")")] if gates_open else []), T(". ")]
        out += [T("Committing before "), S(no), T(" is complete is the main risk"), *([T(" ("), R(rid), T(")")] if rid else []),
                T(".")] if no else []
    else:
        no = f.step(lambda s: s["decision"] == d and s["phase"] == "first_steps")
        missing = next((c for c in f.caveats if c["id"] == f"critical_groups.{d}"), None)
        hear = f.step(lambda s: s["action"].startswith("Hear "))
        if missing and hear:
            out += [T("No precondition is open, but perspectives the decision depends on are missing; hearing them is "),
                    S(hear), T(". ")]
        out += [T("Nothing else has to be resolved before committing" if missing and hear else
                  "Nothing has to be resolved before committing"),
                *([T("; the work starts with "), S(no)] if no else []), T(", reviewed at "), C(1), T(".")]
    return out


def _arch_map(f: Findings) -> list[dict]:
    data = f.data["architecture.map"]
    need, cap = data["need_point"], data["weakest_capability_point"]
    v = f.target("architecture")
    if v == "targeted_extraction":
        out = [T("The system as a whole does not need splitting; one part's distinct load, availability or compliance "
                 "profile justifies separating that part alone. ")]
    elif v in ("consolidate", "realign_services"):
        out = [T("The services are divided in ways that create coordination work rather than independence; the change "
                 "corrects the boundaries rather than adding more. ")]
    elif v == "broad_decomposition":
        out = [T("Both the problem and the ability to change are large enough for a broad change. ")]
    elif need < 2.5:
        out = [T("The problem is small enough that better delivery practices address it; a structural change would "
                 "not pay back. ")]
    elif need >= 3.5:
        out = [T("The problem is large enough for a broad change, but the conditions for one are not in place. ")]
    elif cap >= 3.5:
        out = [T("The organisation could manage a larger change, but the problem is not large enough to justify one. ")]
    else:
        out = [T("The problem is moderate and the ability to change is limited, so the change stays within the "
                 "system. ")]
    split = next((o for o in f.dec["architecture"].get("options", []) if o["id"] == "broad_decomposition"
                  and not o["is_verdict"]), None)
    if split and split["beliefs"]:
        n = len(split["beliefs"])
        out += [T(f"A split into services would need {n} condition{'s' if n > 1 else ''} to change (see "),
                SEC("options-architecture", "“what you would need to believe”"), T("). ")]
    bm = (f.ctx["readiness"].get("benchmark") or {}).get("rows", [])
    slow = [r for r in bm if r["metric"] in ("leadtime", "deployfreq") and r["position"] == "below"]
    measured = [r for r in bm if r["metric"] in ("leadtime", "deployfreq") and r["score"] is not None]
    if measured and "readiness.benchmark" in f.present:
        if slow and v == "stay_and_improve":
            out += [T("Slower delivery than peers ("), X("readiness.benchmark"), T(") is what better practices target. ")]
        elif slow:
            out += [T("Slower delivery than peers ("), X("readiness.benchmark"), T(") supports the case for change. ")]
        elif v == "broad_decomposition":
            out += [T("Delivery speed is already at or above the industry average ("), X("readiness.benchmark"),
                    T("), so the case rests on coupling, not speed. ")]
        elif v in ("stay_and_improve", "modular_monolith"):
            out += [T("Delivery speed at or above the industry average ("), X("readiness.benchmark"),
                    T(") points the same way: no larger change is needed to keep up with peers"
                      + (", provided the measures are confirmed. " if f.caveated("baseline_unverified") else ". "))]
        else:
            out += [T("Delivery speed is at or above the industry average ("), X("readiness.benchmark"),
                    T("), so the change must not slow it down. ")]
    m = next((m for m in f.measures if m["decision"] == "Architecture" and m["basis"] != "missing baseline"), None)
    if m:
        out += [T(f"Progress shows in {m['measure'][0].lower() + m['measure'][1:].split(' (')[0]}: {m['baseline']} today, "
                  f"target {m['target']} ("), SEC("measures"), T(").")]
    return out


STRUCTURAL = ("modular_monolith", "broad_decomposition", "targeted_extraction", "realign_services", "consolidate")


def _leadtime(f: Findings) -> list[dict]:
    split = f.data["architecture.leadtime"]["by_group"]
    overall = split.get("All respondents asked", {})
    coord, wait = overall.get("Coordination between teams", 0), overall.get("Waiting on process", 0)
    v = f.target("architecture")
    if coord >= 0.5 and v in STRUCTURAL:
        out = [T("Changes wait on other teams' changes; restructuring around clearly owned parts addresses that, "
                 "whereas faster approvals alone would not shorten lead time. ")]
    elif wait >= 0.5:
        out = [T("The delay is in the process — approvals, manual testing or environments — which better practices "
                 "address" + (" before any structural change. " if v in STRUCTURAL else ". "))]
    else:
        out = [T("No single cause dominates lead time, so neither restructuring nor process change alone will "
                 "shorten it. ")]
    keep = [g for g in split if g not in ("All respondents asked", "Other groups")
            and (f.preferred("architecture", g) or (None,))[0] == "stay_and_improve"
            and max(split[g], key=split[g].get) == "Coordination between teams"]
    if keep and coord >= 0.5:
        out += [T(f"{_join(keep)}, which {'prefers' if len(keep) == 1 else 'prefer'} keeping the current architecture, "
                  f"{'gives' if len(keep) == 1 else 'give'} the same answer. ")]
    if any(c["id"] == "disputed_claims.process_not_coupling" for c in f.caveats):
        out += [T("This also answers the view that release approval is the bottleneck ("),
                SEC("free-text", "in respondents' own words"), T("). ")]
    no = f.step(lambda s: "cross-team" in s["action"])
    if no:
        out += [T("Whether restructuring works shows in the share of cross-team changes ("), S(no), T(").")]
    else:
        out += [T("Progress shows in "), SEC("measures"), T(".")]
    return out


def _tco(f: Findings) -> list[dict]:
    dec = f.dec["hosting"]
    econ = dec.get("economics") or []
    r = f.a.results["hosting"]
    word = {"stay_as_is": "Keep as is", "improve_current": "Improve / right-size", "move_to_cloud": "Move to cloud",
            "hybrid": "Hybrid", "repatriate": "Move back from cloud"}.get(r.verdict)
    row = next((e for e in econ if e["option"] == word), None)
    cheapest = min(econ, key=lambda e: e["ratio"]) if econ else None
    if r.verdict == "stay_as_is":
        cheaper = sorted((e for e in econ if e["ratio"] < 1), key=lambda e: e["ratio"])
        out = [T("Every alternative costs more than today's setup, so keeping it is also the cheapest course. ")
               if not cheaper else
               T(f"“{cheaper[0]['option']}” would cost {cheaper[0]['ratio']:.2f}× today's, but the evidence does not call "
                 "for a change; the saving is an option, not a requirement. ")]
    elif row and cheapest and row["option"] == cheapest["option"]:
        out = [T(f"The recommended path is also the cheapest ({row['ratio']:.2f}× today's cost), so cost and evidence "
                 "point the same way. ")]
    elif row and row["ratio"] < 1:
        out = [T(f"The recommended path costs less than today ({row['ratio']:.2f}×) but not the least; it is chosen for "
                 "the need it meets. ")]
    elif row:
        out = [T(f"The recommended path costs {row['ratio']:.2f}× today's setup; it is chosen for the need it meets, "
                 "not for cost. ")]
    else:
        out = [T("The cost comparison sets the bounds within which the recommended path was chosen. ")]
    be = (dec.get("scenarios") or {}).get("breakeven", [])
    if be and all(b["value"] is None for b in be):
        names = [f"“{b['option']}”" for b in be]
        out += [T(f"No single estimate, even at the end of its range, would make {_join(names)} pay off instead ("),
                SEC("scenarios-hosting", "scenarios"), T("). ")]
    elif be:
        found = next(b for b in be if b["value"] is not None)
        out += [T(found["sentence"].rstrip(".") + " ("), SEC("scenarios-hosting", "scenarios"), T("). ")]
    rid = f.risk(lambda x: x["kind"] == "cost")
    if f.caveated("run_cost_reconciliation"):
        out += [T("The ranking holds on the modelled costs, but the invoiced run cost is well above the modelled one; "
                  "allocate the difference before any budget is set.")]
    elif rid:
        out += [T("Firm up the estimate behind "), R(rid), T(" before budgets are committed.")]
    else:
        no = f.step(lambda s: s["decision"] == "hosting" and s["phase"] == "first_steps")
        out += [T("The cost case needs no further work before budgeting"),
                *([T("; the work starts with "), S(no)] if no else []), T(".")]
    return out


def _tornado(f: Findings) -> list[dict]:
    rows = f.data["hosting.tornado"]["inputs"]
    flips = [x for x in rows if min(x["low"], x["high"]) < 1 < max(x["low"], x["high"])]
    if flips:
        rid = f.risk(lambda x: x["kind"] == "cost")
        return [T(f"The comparison depends on {flips[0]['input'][0].lower() + flips[0]['input'][1:].split(',')[0]}: "
                  "within its range the answer changes. "),
                T("Replacing that estimate with a quote is the most valuable piece of cost work"),
                *([T(" ("), R(rid), T(")")] if rid else []), T(".")]
    return [T("The decision does not hinge on any single estimate. "),
            T("The estimates in "), SEC("assumptions"), T(" need confirming for budgeting, not for the decision.")]


def _preferences(f: Findings, d: str) -> list[dict]:
    st = f.a.stakes
    by = st.preferences[d]["by_group"]
    v = f.target(d)
    from .stakes import top_choice
    tops = {g: top_choice(s)[0] for g, s in by.items() if g != "All respondents" and top_choice(s)[2]}
    groups = list(tops)                                                  # counted as in the exhibit title
    agree = [g for g in groups if tops[g] == v]
    dissent = [g for g in groups if g not in agree and g != "Other groups" and tops[g]]
    overall = by.get("All respondents") or {}
    rival = max(((o, x) for o, x in overall.items() if o not in (v, "no_direction")), key=lambda kv: kv[1], default=None)
    tied = [g for g, s in by.items() if g != "All respondents" and top_choice(s)[0] is None and v in top_choice(s)[2]]
    if rival and rival[1] >= overall.get(v, 0):
        split = f", {len(tied)} {'is' if len(tied) == 1 else 'are'} split between it and another option" if tied else ""
        out = [T(f"Support is thin: {len(agree)} of {len(groups)} groups clearly prefer the recommended path{split}, and "
                 f"across respondents “{f.label(d, rival[0])}” is as popular ({_pct(rival[1])} against "
                 f"{_pct(overall.get(v, 0))}). Explaining how the two differ is the core of the communication. ")]
    elif len(agree) * 2 > len(groups):
        out = [T(f"{len(agree)} of {len(groups)} groups already prefer the recommended path, so communication can build "
                 "on agreement. ")]
    else:
        out = [T(f"Only {len(agree)} of {len(groups)} groups prefer the recommended path, so the evidence needs "
                 "explaining before the decision is announced. ")]
    for g in dissent[:2]:
        o, share = tops[g], by[g][tops[g]]
        concern = (st.concern.get(g) or {}).get("self")
        no = f.step(lambda s: g in s["action"] and s["phase"] == "people")
        then = [T("; engaging them is "), S(no)] if no else []
        if concern is not None and concern >= 0.4:
            out += [T(f"{g}'s preference for “{f.label(d, o)}” ({_pct(share)}) comes with high role concern "
                      f"({_pct(concern)}, "), *(f.exhibit("people.map") or f.exhibit(f"{d}.stakes")), T(")"), *then,
                    T(". ")]
        else:
            out += [T(f"{g} mostly prefers “{f.label(d, o)}” ({_pct(share)}), and the conditions for that path are set "
                      "out under "), SEC(f"options-{d}", "“what you would need to believe”"), *then, T(". ")]
    return out


def _stakes(f: Findings, d: str) -> list[dict]:
    by = f.a.stakes.stakes_by_option[d]
    v = f.target(d)
    by = {g: row for g, row in by.items() if g not in ("Other groups", "All respondents")}
    on_path = {g: row[v] for g, row in by.items() if v in row and row[v] is not None}
    worst_g, worst_v = min(on_path.items(), key=lambda kv: kv[1]) if on_path else (None, 0)
    pooled = (f.a.stakes.stakes_by_option[d].get("Other groups") or {}).get(v)
    if worst_v >= -0.2:
        out = [T("No named group expects the recommended path to harm its roles"
                 + (f" (lowest: {worst_g}, {worst_v:+.1f})" if worst_g else ""))]
        if pooled is not None and pooled < -0.2:              # the smaller groups, reported together, do
            out += [T(f", but respondents in the smaller groups, reported together, do ({pooled:+.1f}); their concern "
                      "needs hearing directly. ")]
        else:
            out += [T(". ")]
    else:
        out = [T(f"{worst_g} expects the recommended path to affect its roles ({worst_v:+.1f}); that is the concern to "
                 "address. ")]
    worst = min(((val, g, o) for g, row in by.items() for o, val in row.items() if val is not None), default=None)
    if worst and worst[2] != v and worst[0] <= -0.3:
        out += [T(f"The strongest negative expectation ({worst[1]}, {worst[0]:+.1f}) concerns “{f.label(d, worst[2])}”, "
                  "which is not recommended; saying so explicitly removes a worry that does not arise. ")]
    g = worst_g if worst_v < -0.2 else (worst[1] if worst else None)
    no = f.step(lambda s: "role" in s["action"].lower() and (g is None or g in s["action"])) or \
        f.step(lambda s: "role" in s["action"].lower())
    if no:
        out += [T("The role plan is "), S(no), T(".")]
    return out


def _people_map(f: Findings) -> list[dict]:
    rows = f.ctx["stakes"]["map"]
    engage = [r for r in rows if r["approach"] == "Engage closely"]
    if not engage:
        no = f.step(lambda s: s["phase"] == "people")
        return [T("Every high-influence group largely supports the recommended path, so it can be sponsored openly. "),
                *([T("The remaining engagement work starts with "), S(no), T(".")] if no else [])]
    g = engage[0]["group"]
    out = [T(f"{g} has the influence to slow the change if it is not persuaded. ")]
    for d in f.a.results:
        pref = f.preferred(d, g)
        v = f.target(d)
        if pref and pref[0] != v and pref[0] in {o["id"] for o in f.dec[d].get("options", [])}:
            dated = any(tr["decision"] == d and tr["alternative"] == f.label(d, pref[0])
                        for tr in f.ctx.get("triggers", []))
            out += [T(f"{g}'s respondents mostly prefer “{f.label(d, pref[0])}” ({_pct(pref[1])}); the conditions under which "
                      "that path would win ("),
                    SEC(f"options-{d}", "“what you would need to believe”"),
                    T(") make a good agenda, turning a difference of preference into a test of evidence"),
                    *([T(", and "), SEC("triggers", "the reopen criteria"), T(" give that test a date")] if dated else []),
                    T(". ")]
            break
    no = f.step(lambda s: g in s["action"] and "evidence" in s["action"])
    rid = f.risk(lambda x: x["kind"] == "people" and "leadership" in x["title"].lower())
    if no:
        out += [T("That conversation is "), S(no)]
        out += [T(", and it addresses "), R(rid), T(".")] if rid else [T(".")]
    return out


def _divergence(f: Findings) -> list[dict]:
    divs = f.a.evidence.divergences
    if not divs:
        return [T("Perception and measurement agree.")]
    top = max(divs, key=lambda x: abs(x["survey"] - x["fact_band"]))
    try:
        label = area_label(top["sub_area"], f.ins).split(": ", 1)[-1]
    except KeyError:                                   # need and other non-readiness sub-areas
        from .explain import signal_label
        label = signal_label(top["sub_area"], f.ins).lower()
    higher = top["survey"] > top["fact_band"]
    out = [T(f"Where perception runs ahead of measurement ({label}), plans built on perception would overreach. ") if higher
           else T(f"Where measurement is better than perception ({label}), the organisation underrates itself. ")]
    for d, outcomes in f.needed_by(top["sub_area"]).items():
        v = f.target(d)
        if v in outcomes:
            out += [T(f"The gap matters directly: the recommended {d} path relies on {label}. ")]
            break
        other = [o for o in outcomes if o != v]
        if other and higher:
            groups = (f.a.stakes.preferences.get(d, {}).get("by_group", {}) if f.a.stakes else {})
            fans = [g for g in groups if g not in ("Other groups", "All respondents")
                    and (f.preferred(d, g) or (None,))[0] in other]
            out += [T(f"The gap matters for “{f.label(d, other[0])}”, which is not recommended"),
                    T(f"; it may help explain why {_join(fans)} {'favours' if len(fans) == 1 else 'favour'} it. "
                      if fans else ". ")]
            break
    words = top["sub_area"].split(".")[-1].replace("_", " ")
    no = f.step(lambda s: "Reconcile" in s["action"] and (words in s["action"] or label.split(" (")[0] in s["action"]))
    if no:
        out += [T("Sharing the measurement is "), S(no), T(".")]
    return out


def _readiness_matrix(f: Findings) -> list[dict]:
    data = f.data["readiness.matrix"]
    means, spread = data["area_means"], data["spread_between_groups"]
    weakest = min(means, key=means.get)
    return _capability_gap(f, weakest, means[weakest]) + _spread(f, max(spread, key=spread.get), max(spread.values()))


def _capability_gap(f: Findings, label: str, value: float) -> list[dict]:
    sub = f.area_sub(label)
    short = label.split(": ", 1)[-1]
    if not sub:
        return [T(f"The weakest area is {short} ({value:.1f}). ")]
    needs = f.needed_by(sub)
    for d, outcomes in needs.items():
        v = f.target(d)
        if v in outcomes:
            no = f.step(lambda s: s["decision"] == d and s["phase"] in ("capability", "first_steps"))
            return [T(f"This gap lies on the recommended {d} path and has to be closed first"),
                    *([T(" ("), S(no), T(")")] if no else []), T(". ")]
    blocked = [(d, o) for d, outcomes in needs.items() for o in outcomes if o != f.target(d)]
    if blocked:
        d, o = blocked[0]
        return [T(f"This gap does not affect the recommended path, but it is one reason “{f.label(d, o)}” is not open "
                  "today ("), SEC(f"options-{d}", "options considered"), T("). ")]
    if sub.split(".")[0] in ("alignment", "governance"):
        return [T("This gap is about how the change is led rather than what it requires; it bears on "),
                SEC("preconditions"), T(". ")]
    return [T("No path assessed depends on this area ("), SEC("options-architecture", "options considered"),
            T("), so it is context, not a blocker. ")]


def _spread(f: Findings, label: str, value: float) -> list[dict]:
    short = label.split(": ", 1)[-1]
    if value < 1.5:
        return []
    no = f.step(lambda s: "facilitated session" in s["action"])
    rid = f.risk(lambda x: x["title"].startswith("Alignment"))
    out = [T(f"Groups rate “{short}” very differently ({value:.1f} points apart), which a single announcement will not "
             "bridge")]
    if no:
        out += [T("; "), S(no), T(" is the place to close the gap")]
    if rid:
        out += [T(" ("), R(rid), T(")")]
    return out + [T(".")]


def _readiness_weakest(f: Findings) -> list[dict]:
    items = f.ctx["readiness"]["weakest"]
    top = items[0]
    sub = _sub_area_name(f.ins.items.loc[top["item"]])
    label = area_label(sub, f.ins)
    short = label.split(": ", 1)[-1]
    matrix = f.data.get("readiness.matrix", {}).get("area_means", {})
    same = matrix and min(matrix, key=matrix.get) == label
    needs = f.needed_by(sub)
    on_path = [d for d, outcomes in needs.items() if f.target(d) in outcomes]
    out = [T(f"One question shows the {short} gap plainly: {_pct(top['low'])} of answers are at the low end"),
           *([T(", confirming "), X("readiness.matrix")] if same and "readiness.matrix" in f.present else []), T(". ")]
    if on_path:
        no = f.step(lambda s: s["decision"] == on_path[0] and s["phase"] in ("capability", "first_steps"))
        out += [T("Closing it is part of the recommended path"), *([T(" ("), S(no), T(")")] if no else []), T(". ")]
    elif needs:
        d, o = next((d, o) for d, outcomes in needs.items() for o in outcomes)
        out += [T(f"No action is needed for the recommended path; it becomes a precondition only if “{f.label(d, o)}” is "
                  "reconsidered ("), SEC(f"options-{d}", "options considered"), T("). ")]
    split = [i for i in items if i["low"] >= 0.25 and i["high"] >= 0.25]
    if split:
        out += [T(f"Where answers split ({_pct(split[0]['low'])} low, {_pct(split[0]['high'])} high), respondents "
                  "experience the same thing differently; clarify it before planning around it.")]
    return out


def _benchmark(f: Findings) -> list[dict]:
    rows = [r for r in f.ctx["readiness"]["benchmark"]["rows"] if r["score"] is not None]
    if not rows:
        return [T("Without measured delivery data the comparison cannot be made; measuring it is part of "),
                SEC("measures"), T(".")]
    below = [r["label"].lower() for r in rows if r["position"] == "below"]
    if f.caveated("baseline_unverified"):
        out = [T("The comparison is provisional: the measures have not been verified against system data. ")]
        out += [T(f"If confirmed, catching up on {_join(below)} is part of what the change must deliver. ") if below else
                T("If confirmed, delivery performance is not the problem to solve but the thing to protect. ")]
    else:
        out = [T(f"Catching up on {_join(below)} is part of what the change must deliver. ") if below else
               T("Delivery performance is not the problem to solve, so it is the thing to protect. ")]
    out += [T("These measures belong next to "), SEC("measures"),
            T(" as guardrails at each checkpoint, so that the change does not trade stability for structure.")]
    return out


def _roadmap(f: Findings) -> list[dict]:
    high = [r["id"] for r in f.risks if r["score"] >= 9]
    out = [T("Nothing irreversible happens before the first checkpoint. ")]
    if len(high) == 1:
        out += [T("The highest-rated risk ("), {**R(high[0]), "short": True}, T(") is dealt with in this phase. ")]
    elif high:
        out += [T("The highest-rated risks ("), *_refs([{**R(x), "short": True} for x in high[:3]]),
                T(") are dealt with in this phase. ")]
    out += [T("The first checkpoint ("), {**C(1), "short": True}, T(") is the real decision point: commit, re-scope or stop, against "),
            SEC("measures"), T(".")]
    if f.ctx.get("triggers"):
        out += [T(" What would reopen each decision is agreed now ("), SEC("triggers", "when to reopen"), T(").")]
    if (f.ctx.get("roadmap") or {}).get("load"):
        out += [T(" One owner carries too many actions at once; see the capacity note.")]
    return out


def _refs(refs: list[dict]) -> list[dict]:
    out = []
    for i, r in enumerate(refs):
        if i:
            out.append(T(" and " if i == len(refs) - 1 else ", "))
        out.append(r)
    return out


# ---------------------------------------------------------------------------------------- entry points

def compose(assessment, ctx: dict) -> None:
    """Attach `role` and `so_what` to every exhibit insight in the context, and the check results to the context."""
    f = Findings(assessment, ctx)
    failed = []
    for e in ctx["exhibits"]:
        ins = e["insight"]
        eid = ins["id"]
        head, _, tail = eid.partition(".")
        ins["role"] = ROLE.get(eid) or ROLE.get(tail, "")
        try:
            if tail == "probabilities":
                seg = _probabilities(f, head)
            elif tail in ("preferences", "stakes"):
                seg = (_preferences if tail == "preferences" else _stakes)(f, head)
            else:
                seg = {"architecture.map": lambda: _arch_map(f), "architecture.leadtime": lambda: _leadtime(f),
                       "hosting.tco": lambda: _tco(f),
                       "hosting.tornado": lambda: _tornado(f), "people.map": lambda: _people_map(f),
                       "people.divergence": lambda: _divergence(f), "readiness.matrix": lambda: _readiness_matrix(f),
                       "readiness.weakest": lambda: _readiness_weakest(f), "readiness.benchmark": lambda: _benchmark(f),
                       "plan.roadmap": lambda: _roadmap(f)}[eid]()
        except (KeyError, IndexError, TypeError, ValueError, StopIteration) as exc:
            seg = None                                     # fall back to the exhibit's own observations
            failed.append(f"{eid}: so-what could not be composed ({type(exc).__name__}: {exc})")
        ins["so_what"] = _tidy(seg) if seg else [T(" ".join(ins["points"]))]
    ctx["so_what_issues"] = failed + check(ctx)
    ctx["coverage_issues"] = coverage(assessment, ctx)


def _tidy(segments: list[dict]) -> list[dict]:
    """Merge adjacent text and normalise spacing around references."""
    out: list[dict] = []
    for s in segments:
        if "t" in s and out and "t" in out[-1]:
            out[-1] = T(out[-1]["t"] + s["t"])
        elif "t" not in s or s["t"]:
            out.append(s)
    if out and "t" in out[-1]:
        out[-1] = T(out[-1]["t"].rstrip())
    return out


def drivers(assessment) -> dict[str, list[str]]:
    """Signals that decided each verdict: the satisfied conditions of the verdict, and every condition that keeps an
    alternative from applying (all of its routes)."""
    from .appraisal import _routes
    from .decision import Context, evaluate
    from .report_v3 import _met_leaves
    ins, ev = assessment.engagement.instrument, assessment.evidence
    out: dict[str, list[str]] = {}
    for d, r in assessment.results.items():
        ctx = Context(ev.at(0), ins.rules, ev.current_state, d)
        found: list[str] = []
        for o in ins.rules["decisions"][d]["outcomes"]:
            allowed = o.get("only_if_current")
            if allowed and ev.current_state[d] not in (allowed if isinstance(allowed, list) else [allowed]):
                continue
            if o["id"] == r.verdict:                     # the route that decided, as "why this path" shows it
                found += [c["signal"] for c in _met_leaves(o.get("when"), ctx)]
            elif any(evaluate(ins.rules["hard_stops"][h]["when"], ctx) is True for h in o.get("excluded_by", [])):
                continue                                   # ruled out by a hard stop, which is the stated reason
            else:
                found += [c["signal"] for route in _routes(o.get("when"), ctx) for c in route if "signal" in c]
        out[d] = [s for s in dict.fromkeys(found) if s != "<unresolved>"]
    return out


def coverage(assessment, ctx: dict) -> list[str]:
    """Every driver must be visible in the body of the report (not only in the appendix)."""
    import json

    from .explain import signal_label
    ins = assessment.engagement.instrument
    body = json.dumps([{k: d.get(k) for k in ("why", "flips", "summary", "options")} for d in ctx["decisions"]],
                      ensure_ascii=False) + json.dumps(ctx["key_messages"], ensure_ascii=False)
    body += " ".join(e["insight"]["title"] + " " + plain(e["insight"].get("so_what") or []) for e in ctx["exhibits"])
    body = body.lower()
    missing = []
    for d, signals in drivers(assessment).items():
        for s in signals:
            label = signal_label(s, ins)
            if label.lower()[:40] not in body:
                missing.append(f"{d}: “{label}” decides the verdict but is not shown in the report")
    return missing


def check(ctx: dict) -> list[str]:
    issues = []
    for e in ctx["exhibits"]:
        ins = e["insight"]
        seg = ins.get("so_what") or []
        if not any("ref" in s for s in seg):
            issues.append(f"{ins['id']}: the so-what links to no other finding, step, risk or measure")
        title = set(re.findall(r"[a-z]{4,}", ins["title"].lower()))
        first = set(re.findall(r"[a-z]{4,}", (seg[0].get("t", "") if seg else "").lower()))
        if first and len(title & first) / len(first) > 0.6:
            issues.append(f"{ins['id']}: the so-what restates the title")
        if len(plain(seg).split()) > 110:
            issues.append(f"{ins['id']}: the so-what is longer than 110 words")
    return issues
