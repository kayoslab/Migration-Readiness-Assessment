"""Board readiness: checks over the finished report context, run on every build.

A report is board-ready when it asks for a decision, puts the money in euros, shows what decided each verdict, links
every "so what" to the rest of the report, places every caveat beside what it qualifies, agrees on its own draft
status, says when each decision is reopened, and speaks plain language. `mra report` prints failures;
`mra report --final` refuses to build while any check fails or no quality review is recorded.
"""

from __future__ import annotations

import re

STRUCTURAL = ("modular_monolith", "broad_decomposition", "targeted_extraction", "realign_services", "consolidate")
# keys whose values are data, identifiers or file paths rather than printed text
NOT_PRINTED = {"data", "charts", "chart", "path", "id", "ref", "signal", "verdict", "status", "tone", "decision",
               "fact", "kind", "severity", "metric", "facts", "exhibits", "decisions", "key_messages", "themes",
               "step_rewrite", "draws", "source", "levels_2024", "points", "interpretation", "phase", "outcome",
               "workstream", "rules", "evidence_strength", "group", "most_preferred", "evidence_path", "insufficient",
               "starts_with", "model", "mental_models", "item"}
TECHNICAL = [
    (re.compile(r"\b[a-z]+(?:_[a-z0-9]+)+\b"), "a field name"),
    (re.compile(r"\b(?:GV|AN|AC|HC|G|C[XO]|MO|SK)\d{2}\b"), "a questionnaire or checklist code"),
    (re.compile(r"\b[\w-]+\.ya?ml\b|engagement\.|→ \w+"), "a configuration reference"),
    (re.compile(r"\b(?=[0-9a-f]*\d)(?=[0-9a-f]*[a-f])[0-9a-f]{7,40}\b"), "a commit or hash"),
    (re.compile(r"`[^`]+`"), "a command"),
]


def _printed(node, key: str | None = None):
    """Every string the template prints (identifiers and data payloads excluded)."""
    if key in NOT_PRINTED:
        return
    if isinstance(node, str):
        if not (node.startswith("/") and node.endswith((".svg", ".png", ".pdf"))):   # chart files are not text
            yield node
    elif isinstance(node, dict):
        for k, v in node.items():
            yield from _printed(v, k)
    elif isinstance(node, list):
        for v in node:
            yield from _printed(v, key)


def technical_terms(ctx: dict) -> list[str]:
    found = []
    for text in _printed({k: v for k, v in ctx.items() if k not in ("exhibits", "evidence")}):
        for pattern, what in TECHNICAL:
            m = pattern.search(text)
            if m:
                found.append(f"{what} “{m.group(0)}” in: {text[:90]}")
    for e in ctx.get("exhibits", []):
        ins = e["insight"]
        texts = [ins.get("title", ""), ins.get("role", "")] + [s.get("t", "") for s in ins.get("so_what") or []] + \
            [c["message"] for c in ins.get("caveats", [])]
        for text in texts:
            for pattern, what in TECHNICAL:
                m = pattern.search(text)
                if m:
                    found.append(f"{what} “{m.group(0)}” in: {text[:90]}")
    return list(dict.fromkeys(found))


def run(ctx: dict) -> list[dict]:
    out = []

    def check(name: str, ok: bool, detail: str = ""):
        out.append({"check": name, "ok": bool(ok), "detail": "" if ok else detail})

    decisions = ctx["decisions"]
    brief = ctx.get("brief") or {}
    asked = {r["decision"] for r in brief.get("requests", [])}
    check("Decision requested for every decision", all(d["title"] in asked for d in decisions),
          "the decision page lacks a request for " + ", ".join(d["title"] for d in decisions if d["title"] not in asked))

    host = next((d for d in decisions if d["id"] == "hosting"), None)
    if host and host.get("economics") and host.get("show_amounts", True):
        check("Costs in euros", all(r.get("eur") for r in host["economics"]), "cost rows without an amount")

    arch = next((d for d in decisions if d["id"] == "architecture"), None)
    if arch and arch["verdict"] in STRUCTURAL:
        budget = next((r.get("budget") for r in brief.get("requests", []) if r["decision"] == arch["title"]), None)
        check("Architecture investment estimated or its owner named", bool(budget), "no investment statement")

    check("Every deciding condition shown", not ctx.get("coverage_issues"), "; ".join(ctx.get("coverage_issues", [])[:3]))
    check("Every “so what” linked and specific", not ctx.get("so_what_issues"),
          "; ".join(ctx.get("so_what_issues", [])[:3]))

    integrity = ctx.get("integrity") or {}
    placed = []
    for c in integrity.get("caveats", []):
        title = c["title"]
        beside = any(any(x["title"] == title for x in d.get("caveats", [])) for d in decisions) or \
            any(any(x["title"] == title for x in e["insight"].get("caveats", [])) for e in ctx.get("exhibits", [])) or \
            any(c["message"] in xs for xs in (ctx.get("text") or {}).get("key_message_caveats", [])) or \
            any(c["message"] in th.get("caveats", []) for th in (ctx.get("text") or {}).get("themes", [])) or \
            any(title.lower() in str(m.get("basis", "")) for m in ctx.get("measures", []))
        if not beside:
            placed.append(title)
    check("Every caveat placed beside what it qualifies", not placed, "only in the notice: " + "; ".join(placed))

    blocks = bool(integrity.get("blocks"))
    check("Draft status consistent", integrity.get("draft") == blocks == bool(ctx["engagement"].get("draft")),
          "cover, executive summary and integrity checks disagree on draft status")

    decided = [d for d in decisions if d["verdict"] != "insufficient_evidence"
               and any(not o["is_verdict"] and o["beliefs"] and o["state"] in ("conditions not met", "capability gap too large")
                       for o in d.get("options", []))]
    reopen = {t["decision"] for t in ctx.get("triggers", [])}
    check("Reopen criteria agreed for each decision", all(d["id"] in reopen for d in decided),
          "missing for " + ", ".join(d["id"] for d in decided if d["id"] not in reopen))

    terms = technical_terms(ctx)
    check("Plain language (no field names, codes, file names or commits)", not terms, "; ".join(terms[:3]))
    return out


def failures(rubric: list[dict]) -> list[str]:
    return [f"{r['check']}: {r['detail']}" for r in rubric if not r["ok"]]
