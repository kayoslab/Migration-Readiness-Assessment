"""An executive narrative and chapter introductions written by a language model from the report's own findings.

The model only phrases what the deterministic report already says. Every sentence is checked before use:
- numbers must appear in the report data (as given, or the same value as a percentage);
- a sentence that recommends a path must name the verdict or the interim step of that decision;
- the stakes vocabulary rules apply (no "bias", "agenda", "resist", …).
If the executive summary contradicts a decision's status (no mention of preconditions under "prepare first", or of
uncertainty under "insufficient evidence"), the narrative is discarded and the report keeps its deterministic text.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

import pydantic

from .storyline import plain

NARRATIVE_INSTRUCTIONS = """You write the narrative parts of a management-consulting report on the future of a
software platform, in the register of a Big Four advisory report: formal, concise British English, no jargon.

You receive the report's findings as JSON. Use ONLY these findings. Never introduce a number, a path or a fact that
is not in them; copy numbers exactly as given (shares may be written as percentages). Do not recommend any path
other than the one each decision's verdict names; you may mention the interim step. If a decision's status is
"prepare_first", say that preconditions must be met first. If it is "insufficient", say that the evidence does not
yet support a single path. Describe stakeholder stakes neutrally, as considerations for planning and
communication, never as motives or bias. Attribute views to groups, never to individuals. "integrity" lists where the
inputs contradict each other: carry each qualification where you use the affected finding, never present a view
marked as unsupported as a finding or as common ground, and if any issue has severity "block", say in the first
paragraph that the report is a draft and why.

Return:
- executive: 2 to 4 short paragraphs telling one coherent story — the situation, what the evidence says for each
  decision and why, what must happen first, and what it means for the people involved.
- chapters: one short paragraph (2–3 sentences) introducing each of: architecture, hosting, readiness, people.
- exhibits: for every exhibit in "exhibits", ONE sentence that replaces the first sentence of its "so_what_draft".
  It states what the exhibit implies for the recommended path, read against all the other findings and the
  exhibit's "role" in the storyline — not what the chart shows (the title already says that). Add what the rest of
  the draft does not say and never repeat it. At most 35 words. Do not mention exhibit numbers, steps, risks or
  sections: the rest of the so-what links to them. Return the id unchanged."""

BANNED = ("bias", "biased", "self-interest", "motivated", "agenda", "resist", "resistance", "obstruct", "blame")
RECOMMEND = re.compile(r"\b(recommend|should|must|advise|propose|best option|the right path)\w*", re.I)
NUMBER = re.compile(r"(?<![\w.])(\d+(?:[.,]\d+)*)(\s?%)?")


class Chapters(pydantic.BaseModel):
    architecture: str
    hosting: str
    readiness: str
    people: str


class ExhibitText(pydantic.BaseModel):
    id: str
    interpretation: str


class NarrativeOut(pydantic.BaseModel):
    executive: list[str]
    chapters: Chapters
    exhibits: list[ExhibitText]


@dataclass
class Narrative:
    executive: list[str]
    chapters: dict[str, str]
    dropped: list[str] = field(default_factory=list)
    rejected: str | None = None
    exhibits: dict[str, str] = field(default_factory=dict)


def findings_payload(ctx: dict) -> dict:
    """The parts of the report context the narrative may draw on (no chart paths, no raw evidence table)."""
    decisions = []
    for d in ctx["decisions"]:
        decisions.append({k: d.get(k) for k in ("id", "title", "current", "verdict_label", "status", "probability",
                                                "leaning_label", "summary", "why", "flips", "hard_stops", "capabilities",
                                                "interim_label", "notes", "excluded")}
                         | {"preconditions_open": [g["label"] for g in d.get("gates", []) if g["status"] != "pass"],
                            "uncertain": [u["text"] for u in d.get("uncertain", [])],
                            "economics": [{"option": e["option"], "cost_ratio_vs_current": e["ratio"],
                                           "range_90pct": e["range"], "payback_months_after_cutover": e["payback"],
                                           "saving_fte_per_year": e["saving_fte"]} for e in d.get("economics") or []]})
    return {
        "organisation": ctx["engagement"]["organisation"], "system": ctx["system"],
        "decisions": decisions,
        "readiness": {"weakest_key_message": [m for m in ctx["key_messages"] if "weakest" in m],
                      "differences": [d for d in ctx["readiness"]["differences"] if d["significant"]]},
        "stakeholder_findings": ctx["stakes"]["findings"],
        "free_text": (ctx.get("text") or {}).get("key_messages", []),
        "next_steps": [{"phase": s["phase_label"], "action": s["action"]} for s in ctx["steps"]][:10],
        "exhibits": [{"id": e["insight"]["id"], "role": e["insight"].get("role", ""), "title": e["insight"]["title"],
                      "so_what_draft": plain(e["insight"].get("so_what") or []), "observations": e["insight"]["points"],
                      "data": e["data"]} for e in ctx.get("exhibits", [])],
        "options": {d["id"]: [{"option": o["label"], "status": o["state"], "would_need": o["beliefs"]}
                              for o in d.get("options", [])] for d in ctx["decisions"]},
        "risks": [{"id": r["id"], "risk": r["title"], "likelihood": r["likelihood"], "impact": r["impact"]}
                  for r in ctx["risks"]["risks"]],
        "success_measures": ctx.get("measures", []),
        "benchmark": [{k: r[k] for k in ("label", "shown", "position")}
                      for r in (ctx["readiness"].get("benchmark") or {}).get("rows", [])],
        "stakeholder_map": [{k: r[k] for k in ("group", "support", "influence", "approach")}
                            for r in ctx["stakes"].get("map", [])],
        "integrity": [{"severity": i["severity"], "issue": i["title"], "detail": i["message"]}
                      for i in (ctx.get("integrity") or {}).get("issues", [])],
    }


# ---------------------------------------------------------------------------------------- validation

def _allowed_numbers(payload: dict) -> set[float]:
    text = json.dumps(payload, ensure_ascii=False)
    values = set()
    for raw, _ in NUMBER.findall(text):
        try:
            values.add(float(raw.replace(",", "")))
        except ValueError:
            continue
    for v in list(values):
        if 0 <= v <= 1:
            values.add(round(v * 100, 1))                       # shares may be written as percentages
    return values | {float(i) for i in range(0, 25)}            # small counts, months and years in prose


def _numbers_ok(sentence: str, allowed: set[float]) -> bool:
    for raw, _ in NUMBER.findall(sentence):
        try:
            n = float(raw.replace(",", ""))
        except ValueError:
            return False
        decimals = len(raw.split(".")[1]) if "." in raw else 0
        if not any(abs(round(a, decimals) - n) < 1e-9 or abs(a - n) < 1e-9 for a in allowed):
            return False
    return True


def _recommendation_ok(sentence: str, allowed_paths: set[str], all_paths: set[str]) -> bool:
    if not RECOMMEND.search(sentence):
        return True
    named = {p for p in all_paths if p.lower() in sentence.lower()}
    return named <= allowed_paths


def _sentences(paragraph: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z“\"(])", paragraph.strip()) if s.strip()]


def validate(out: dict, payload: dict, all_paths: set[str]) -> Narrative:
    allowed = _allowed_numbers(payload)
    allowed_paths = {p for d in payload["decisions"] for p in (d["verdict_label"], d.get("interim_label"),
                                                               d.get("leaning_label")) if p}
    dropped = []

    def clean(paragraph: str) -> str:
        kept = []
        for s in _sentences(paragraph):
            reason = None
            if any(re.search(rf"\b{w}\b", s, re.I) for w in BANNED):
                reason = "stakes vocabulary"
            elif not _numbers_ok(s, allowed):
                reason = "number not in the findings"
            elif not _recommendation_ok(s, allowed_paths, all_paths):
                reason = "recommends a path other than the verdict"
            if reason:
                dropped.append(f"{reason}: {s}")
            else:
                kept.append(s)
        return " ".join(kept)

    executive = [p for p in (clean(p) for p in out.get("executive", [])) if p]
    chapters = {k: clean(v) for k, v in (out.get("chapters") or {}).items()}
    known = {e["id"] for e in payload.get("exhibits", [])}
    exhibits = {}
    for e in out.get("exhibits") or []:
        if e["id"] in known:
            text = clean(e["interpretation"])
            if len(_sentences(text)) == 1:          # exactly one sentence; otherwise the computed one stays
                exhibits[e["id"]] = text
    story = " ".join(executive).lower()
    for d in payload["decisions"]:
        if d["status"] == "prepare_first" and not re.search(r"precondition|before committing|first", story):
            return Narrative([], {}, dropped, f"{d['title']}: narrative omits that preconditions come first", exhibits)
        if d["status"] == "insufficient" and not re.search(r"insufficient|not yet|uncertain|too close", story):
            return Narrative([], {}, dropped, f"{d['title']}: narrative omits that the evidence is insufficient", exhibits)
    return Narrative(executive, chapters, dropped, exhibits=exhibits)


def write(ctx: dict, eng) -> Narrative:
    """Draft through the Vercel AI Gateway (settings from engagement.yaml → llm), cached, then validate."""
    from .config import LLMSettings
    from .llm import Cache, LLMClient, _cached, run_sync

    payload = findings_payload(ctx)
    settings = LLMSettings(**(eng.config.get("llm") or {}))
    client = LLMClient.from_settings(settings)
    client.require_key()
    out = run_sync(_cached(client, Cache(eng.root / "Output" / "llm_cache"), "narrative", NARRATIVE_INSTRUCTIONS,
                           payload, NarrativeOut))
    ins = eng.instrument
    all_paths = {spec.get("label") for d in ("architecture", "hosting") for spec in ins.outcomes[d].values()}
    return validate(out, payload, all_paths)
