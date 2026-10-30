"""Optional LLM analysis of free-text answers through the Vercel AI Gateway.

Uses Vercel's AI SDK for Python (`ai`), which routes every model (e.g. anthropic/claude-opus-5.5)
through the gateway and validates structured output against Pydantic models.

Configuration: AI_GATEWAY_API_KEY (required), MRA_LLM_MODEL (overrides llm.model in assessment.yaml).

Each respondent's answers are coded in one call against a fixed codebook (sentiment, stance on
change, themes, reasons), cached on disk, then aggregated. A final call writes a short synthesis
that may only use the coded evidence and quotes it is given.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pandas as pd
import pydantic

from .config import Config, LLMSettings
from .data import Survey

PROMPT_VERSION = "2026-11-01.1"   # adds mental_model; string item ids (v2 and v3)

THEMES = (
    "Delivery speed", "Technical debt", "Coupling & dependencies", "Data & integration",
    "Release process", "Skills & knowledge", "Ownership & autonomy", "Leadership & sponsorship",
    "Funding & ROI", "Communication & alignment", "Change readiness", "Cost", "Risk",
    "Platform & tooling", "Documentation", "Customer impact",
)
REASONS = (
    "Speed of delivery", "Cost", "Risk", "Workload & capacity", "Career & skills",
    "Customer value", "Control & governance", "Past experience", "Scalability", "Other",
)


MENTAL_MODELS = ("centralised", "domain_owned", "mixed", "unclear")


class AnswerCode(pydantic.BaseModel):
    item_id: str
    sentiment: Literal[-2, -1, 0, 1, 2]
    stance: Literal["supports_change", "opposes_change", "mixed", "neutral"]
    themes: list[Literal[THEMES]]
    reasons: list[Literal[REASONS]]
    mental_model: Literal[MENTAL_MODELS]


class Coding(pydantic.BaseModel):
    answers: list[AnswerCode]


class ThemeFinding(pydantic.BaseModel):
    theme: str
    finding: str
    quote_ids: list[int]


class Synthesis(pydantic.BaseModel):
    key_messages: list[str]
    themes: list[ThemeFinding]


CODING_INSTRUCTIONS = f"""You code free-text survey answers from an organisational assessment of
readiness for a platform / architecture migration. Code every answer you are given, independently
and literally — do not infer beyond the text.

- sentiment: -2 very negative … 0 neutral … 2 very positive, about the respondent's current situation.
- stance: the respondent's attitude to the proposed change (migration / modernisation):
  supports_change, opposes_change, mixed, or neutral when the answer does not express a stance.
- themes: 1–3 from this list only: {", ".join(THEMES)}.
- reasons: the motives behind the stance (empty if no stance): {", ".join(REASONS)}.
- mental_model: how the respondent implicitly thinks systems and data should be organised —
  centralised (one shared model, central decisions, central ownership), domain_owned (teams or business areas own
  their part and its data end to end), mixed, or unclear when the answer does not reveal it. Neither is better;
  code what the words imply, not what you would recommend.

Return one entry per item_id given."""

SYNTHESIS_INSTRUCTIONS = """You write the qualitative findings section of a management-consulting
report on migration readiness. Use formal, concise British English in the register of a Big Four
advisory report. Use ONLY the aggregated codes and numbered quotes provided; never invent facts,
numbers or quotes. Attribute views to stakeholder groups, never to individuals. Express shares as percentages
(e.g. "71% of Operations answers"), never as decimals.

Return:
- key_messages: 3–5 one-sentence messages, most decision-relevant first.
- themes: up to 6 entries, each with the theme name, a 2–3 sentence finding that names which
  groups hold the view, and up to 2 supporting quote_ids from the list provided."""


@dataclass
class LLMClient:
    model: str
    api_key: str | None

    @classmethod
    def from_settings(cls, settings: LLMSettings) -> "LLMClient":
        return cls(model=os.getenv("MRA_LLM_MODEL") or settings.model, api_key=os.getenv("AI_GATEWAY_API_KEY"))

    def require_key(self) -> None:
        if not self.api_key:
            raise RuntimeError("AI_GATEWAY_API_KEY is not set. Copy .env.example to .env and add your key.")

    async def complete(self, instructions: str, payload: dict,
                       output_type: type[pydantic.BaseModel]) -> dict:
        """One request through the gateway, validated against `output_type`."""
        import ai

        self.require_key()
        messages = [ai.system_message(instructions),
                    ai.user_message(json.dumps(payload, ensure_ascii=False))]
        async with ai.stream(ai.get_model(self.model), messages, output_type=output_type) as s:
            async for _ in s:
                pass
        return s.output.model_dump()


def run_sync(coro):
    """Run a coroutine from sync code, including inside Jupyter's already-running event loop."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


# --------------------------------------------------------------------------- redaction & cache

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_URL = re.compile(r"https?://\S+")
_PHONE = re.compile(r"\+?\d[\d\s().-]{7,}\d")


def redact(text: str, terms: list[str]) -> str:
    text = _URL.sub("[url]", _EMAIL.sub("[email]", text))
    text = _PHONE.sub("[phone]", text)
    for term in sorted(terms, key=len, reverse=True):
        text = re.sub(re.escape(term), "[redacted]", text, flags=re.I)
    return text


class Cache:
    def __init__(self, directory: Path):
        self.directory = directory
        directory.mkdir(parents=True, exist_ok=True)

    def _path(self, key: dict) -> Path:
        digest = hashlib.sha256(json.dumps(key, sort_keys=True).encode()).hexdigest()[:24]
        return self.directory / f"{digest}.json"

    def get(self, key: dict):
        path = self._path(key)
        return json.loads(path.read_text()) if path.exists() else None

    def put(self, key: dict, value) -> None:
        self._path(key).write_text(json.dumps(value, ensure_ascii=False, indent=1))


async def _cached(client: LLMClient, cache: Cache, kind: str, instructions: str, payload: dict,
                  output_type: type[pydantic.BaseModel]) -> dict:
    # the instructions are part of the key: editing a prompt must never serve results of the old one
    prompt = hashlib.sha256(instructions.encode()).hexdigest()[:12]
    key = {"v": PROMPT_VERSION, "prompt": prompt, "model": client.model, kind: payload}
    result = cache.get(key)
    if result is None:
        result = await client.complete(instructions, payload, output_type)
        cache.put(key, result)
    return result


# --------------------------------------------------------------------------- analysis

@dataclass
class TextAnalysis:
    coded: pd.DataFrame          # one row per answer with codes
    by_role: pd.DataFrame        # sentiment & stance shares per role
    theme_share: pd.DataFrame    # theme x role: share of that group's answers mentioning the theme
    synthesis: dict
    quotes: list[dict]
    model: str


async def code_answers(texts: pd.DataFrame, questions: dict, settings: LLMSettings, client: LLMClient, cache: Cache,
                       concurrency: int = 4) -> pd.DataFrame:
    """Code free-text answers; `texts` has respondent_id, role, item_id, answer."""
    limit = asyncio.Semaphore(concurrency)

    async def run(rid: str, role: str, items: list[dict]) -> list[dict]:
        async with limit:
            result = await _cached(client, cache, "payload", CODING_INSTRUCTIONS,
                                   {"role": role, "answers": items}, Coding)
        by_id = {a["item_id"]: a for a in result.get("answers", [])}
        return [{"respondent_id": rid, "role": role, **item,
                 **{k: v for k, v in by_id.get(item["item_id"], {}).items() if k != "item_id"}}
                for item in items]

    jobs = []
    for rid, answers in texts.groupby("respondent_id"):
        items = [{"item_id": str(r.item_id), "question": questions[r.item_id],
                  "answer": redact(r.answer, settings.redact_terms) if settings.redact else r.answer}
                 for r in answers.itertuples()]
        jobs.append(run(rid, answers["role"].iat[0], items))
    batches = await asyncio.gather(*jobs)
    return pd.DataFrame([row for batch in batches for row in batch])


def summarise(coded: pd.DataFrame, roles: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Sentiment/stance per role, and theme prevalence as a share of each role's answers (not raw counts,
    which would let the largest group dominate)."""
    coded = coded.dropna(subset=["sentiment"])
    per_person = coded.groupby(["role", "respondent_id"])["sentiment"].mean().reset_index()
    by_role = per_person.groupby("role")["sentiment"].agg(mean="mean", n="count")
    stance = pd.crosstab(coded["role"], coded["stance"], normalize="index")
    by_role = by_role.join(stance).reindex([r for r in roles if r in by_role.index]).fillna(0)
    exploded = coded.explode("themes").dropna(subset=["themes"])
    counts = pd.crosstab(exploded["themes"], exploded["role"]).reindex(columns=roles, fill_value=0)
    share = counts / coded.groupby("role").size().reindex(roles)
    share = share.loc[share.mean(axis=1).sort_values(ascending=False).index]
    if "mental_model" in coded:
        models = pd.crosstab(coded["role"], coded["mental_model"], normalize="index").add_prefix("model_")
        by_role = by_role.join(models).fillna(0)
    return by_role, share


def pick_quotes(coded: pd.DataFrame, per_theme: int) -> list[dict]:
    """Shortest distinct answers per theme and sentiment pole, so quotes are readable and varied."""
    quotes, seen = [], set()
    exploded = coded.explode("themes").dropna(subset=["themes"])
    for theme, sub in exploded.groupby("themes"):
        sub = sub.assign(length=sub["answer"].str.len()).sort_values(["sentiment", "length"])
        for _, r in pd.concat([sub.head(per_theme), sub.tail(per_theme)]).iterrows():
            if r["answer"] in seen:
                continue
            seen.add(r["answer"])
            quotes.append({"id": len(quotes) + 1, "theme": theme, "role": r["role"], "text": r["answer"],
                           "sentiment": int(r["sentiment"])})
    return quotes


async def _analyse(texts: pd.DataFrame, questions: dict, roles: list[str], settings: LLMSettings,
                   cache_dir: Path) -> TextAnalysis:
    client = LLMClient.from_settings(settings)
    client.require_key()
    cache = Cache(cache_dir)
    coded = await code_answers(texts, questions, settings, client, cache)
    by_role, theme_share = summarise(coded, roles)
    quotes = pick_quotes(coded, settings.max_quotes)
    payload = {
        "sentiment_by_role": by_role.round(2).reset_index().to_dict("records"),
        "share_of_answers_mentioning_theme_by_role": theme_share.round(2).reset_index().to_dict("records"),
        "quotes": quotes,
    }
    synthesis = await _cached(client, cache, "synthesis", SYNTHESIS_INSTRUCTIONS, payload, Synthesis)
    return TextAnalysis(coded, by_role, theme_share, synthesis, quotes, client.model)


def analyse_text(survey: Survey, cfg: Config) -> TextAnalysis:
    """v2: free text from the v2 questionnaire."""
    questions = survey.questionnaire["Question"].to_dict()
    return run_sync(_analyse(survey.text, questions, survey.roles, cfg.llm, cfg.root / "Output" / "llm_cache"))


EXCLUDED_FROM_LLM = {"CX03"}   # the withdrawal word is never sent anywhere


def analyse_engagement_text(eng) -> TextAnalysis:
    """v3: open questions of an engagement (settings from engagement.yaml → llm)."""
    ins = eng.instrument
    text_items = [i for i in ins.items.index if ins.items.at[i, "format"] == "text" and i not in EXCLUDED_FROM_LLM]
    texts = eng.answers[eng.answers["item_id"].isin(text_items)].rename(columns={"label": "answer"})
    questions = {i: ins.items.at[i, "text"].replace("{system}", eng.system) for i in text_items}
    settings = LLMSettings(**(eng.config.get("llm") or {}))
    roles = list(dict.fromkeys(eng.respondents["role"]))
    return run_sync(_analyse(texts[["respondent_id", "role", "item_id", "answer"]], questions, roles, settings,
                             eng.root / "Output" / "llm_cache"))
