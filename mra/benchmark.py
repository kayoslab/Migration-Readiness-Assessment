"""Delivery performance against published industry benchmarks (DORA research programme).

Primary reference: the benchmark data behind the DORA Quick Check — per industry and organisation size, the mean and
standard deviation of each software delivery metric on DORA's 0–10 scale (10 best). Our measured values are put on
the same scale with DORA's own conversion (answer categories 1–6 → 0–10; percentages p → 10 − p / 10) and placed
above, around or below the segment average (more than half a standard deviation counts as above or below). No
percentiles: DORA publishes means and standard deviations of ordinal answers, not distributions.

Secondary reference: the 2024 performance levels (elite / high / medium / low) from the Accelerate State of DevOps
Report 2024. DORA stopped publishing levels in 2025, and the 2024 levels do not rank change failure rate (the medium
cluster failed less often than the high one), so the level is shown only for the three throughput measures.

The data lives in instrument/benchmarks.yaml with its source, version and retrieval date; `mra benchmarks` reports
its age and `mra benchmarks --update` rebuilds it from DORA's published repository.
"""

from __future__ import annotations

import datetime as dt
import json
import urllib.request
from pathlib import Path

import yaml

REPO = "dora-team/dora.dev"
DATA_DIR = "svelte/quick-check/src/lib/data/editions"
STALE_AFTER_YEARS = 2

# our fact -> DORA metric, and how the fact's unit maps onto DORA's answer categories (1 worst … 6 best)
METRICS = {
    "leadtime": {"fact": "lead_time_hours", "label": "Lead time for changes", "kind": "duration"},
    "deployfreq": {"fact": "deploys_per_week", "label": "Deployment frequency", "kind": "frequency"},
    "failurerecovery": {"fact": "restore_hours", "label": "Failed deployment recovery time", "kind": "duration"},
    "changefailure": {"fact": "change_failure_pct", "label": "Change failure rate", "kind": "percentage"},
    "rework": {"fact": "deploy_rework_pct", "label": "Deployment rework rate", "kind": "percentage"},
}
DURATION_LIMITS = [(1, 6), (24, 5), (168, 4), (730, 3), (4380, 2)]        # hours: <1 h, <1 day, <1 week, <1 month, <6 months
FREQUENCY_LIMITS = [(10, 6), (5, 5), (1, 4), (0.23, 3), (1 / 26, 2)]      # per week: see benchmarks.yaml → conversion
POSITION_MARGIN_SD = 0.5


# ---------------------------------------------------------------------------------------- conversion

def category(kind: str, value: float) -> int | None:
    if kind == "duration":
        return next((c for limit, c in DURATION_LIMITS if value < limit), 1)
    if kind == "frequency":
        return next((c for limit, c in FREQUENCY_LIMITS if value >= limit), 1)
    return None


def score(kind: str, value: float) -> float:
    """DORA's 0–10 scale, 10 best (Quick Check DataService.calculatePerformanceScore)."""
    if kind == "percentage":
        return max(0.0, min(10.0, 10 - value / 10))
    return (category(kind, value) - 1) * 2.0


def _level_2024(metric: str, cat: int | None, levels: dict) -> str | None:
    if cat is None:
        return None
    return (levels.get(metric) or {}).get(cat)


# ---------------------------------------------------------------------------------------- comparison

def load(instrument_root: Path) -> dict | None:
    path = Path(instrument_root) / "benchmarks.yaml"
    return yaml.safe_load(path.read_text()) if path.exists() else None


def age_warning(bench: dict, today: dt.date | None = None) -> str | None:
    today = today or dt.date.today()
    edition = int(bench["source"]["edition"])
    if today.year - edition > STALE_AFTER_YEARS:
        return (f"Benchmarks are from the {edition} DORA edition, more than {STALE_AFTER_YEARS} years old; "
                "run `mra benchmarks --update`.")
    return None


def compare(engagement) -> dict | None:
    bench = load(engagement.instrument.root)
    if not bench:
        return None
    cfg = engagement.config.get("benchmark") or {}
    industry_key = cfg.get("industry", "all")
    size_key = cfg.get("organisation_size", "all")
    segments = bench["segments"]
    if industry_key not in segments["industry"] or size_key not in segments["organisation_size"]:
        raise ValueError(f"benchmark: unknown industry '{industry_key}' or organisation size '{size_key}'; "
                         f"see instrument/benchmarks.yaml")
    industry, size = segments["industry"][industry_key], segments["organisation_size"][size_key]
    labels = bench["categories"]
    rows = []
    for metric, spec in METRICS.items():
        fact = engagement.facts.get(spec["fact"])
        ref = industry["metrics"].get(metric)
        if ref is None:
            continue
        mean, sd = _good_scale(metric, ref["mean"]), ref["std"]
        size_ref = size["metrics"].get(metric)
        row = {"metric": metric, "label": spec["label"], "industry_mean": round(mean, 1), "industry_sd": sd,
               "industry_typical": _typical(metric, spec["kind"], ref["mean"], labels),
               "size_mean": round(_good_scale(metric, size_ref["mean"]), 1) if size_ref else None,
               "value": None, "shown": "not measured", "score": None, "position": "not measured",
               "size_position": None, "level_2024": None}
        if fact is not None and fact.point is not None:
            value = float(fact.point)
            s = score(spec["kind"], value)
            cat = category(spec["kind"], value)
            row.update({
                "value": value, "score": round(s, 1), "z": round((s - mean) / sd, 2) if sd else 0.0,
                "shown": _shown(spec["kind"], value, cat, metric, labels),
                "position": _position(s, mean, sd),
                "size_position": _position(s, _good_scale(metric, size_ref["mean"]), size_ref["std"]) if size_ref else None,
                "level_2024": _level_2024(metric, cat, bench["levels_2024"]["by_category"]),
            })
        rows.append(row)
    return {"rows": rows, "industry": industry["name"], "organisation_size": size["name"],
            "source": bench["source"], "levels_2024": bench["levels_2024"], "warning": age_warning(bench)}


def _position(s: float, mean: float, sd: float) -> str:
    z = (s - mean) / sd if sd else 0.0
    return "above" if z > POSITION_MARGIN_SD else "below" if z < -POSITION_MARGIN_SD else "around"


def _good_scale(metric: str, raw_mean: float) -> float:
    """The data stores percentage metrics on DORA's instability scale (low is good); invert like the Quick Check."""
    return 10 - raw_mean if METRICS[metric]["kind"] == "percentage" else raw_mean


def _typical(metric: str, kind: str, raw_mean: float, labels: dict) -> str:
    if kind == "percentage":
        return f"about {raw_mean * 10:.0f}%"
    cat = int(round(1 + raw_mean / 2))
    return labels[metric][cat].lower()


def _shown(kind: str, value: float, cat: int | None, metric: str, labels: dict) -> str:
    if kind == "percentage":
        return f"{value:.0f}%"
    unit = {"duration": "h", "frequency": " per week"}[kind]
    number = f"{value:g}{unit}" if kind == "duration" else f"{value:g}{unit}"
    return f"{number} ({labels[metric][cat].lower()})"


# ---------------------------------------------------------------------------------------- update

def _get(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=30) as r:          # noqa: S310 — fixed https host
        return r.read()


def update(instrument_root: Path, edition: str = "2025") -> Path:
    """Rebuild instrument/benchmarks.yaml from DORA's published Quick Check data, keeping the 2024 levels."""
    path = Path(instrument_root) / "benchmarks.yaml"
    current = yaml.safe_load(path.read_text()) if path.exists() else {}
    api = f"https://api.github.com/repos/{REPO}/commits?path={DATA_DIR}/{edition}/industry_metrics.json&per_page=1"
    commit = json.loads(_get(api))[0]["sha"]
    raw = f"https://raw.githubusercontent.com/{REPO}/{commit}"
    industry = json.loads(_get(f"{raw}/{DATA_DIR}/{edition}/industry_metrics.json"))
    size = json.loads(_get(f"{raw}/{DATA_DIR}/{edition}/organization_size_metrics.json"))
    answers = json.loads(_get(f"{raw}/svelte/quick-check/src/lib/data/metrics_question_responses.json"))

    def segment(data):
        return {k: {"name": v["name"], "metrics": {m: {"mean": v[m]["mean"], "std": v[m]["std"]}
                                                   for m in METRICS if m in v}} for k, v in data.items()}

    current["source"] = {
        "title": f"DORA Quick Check benchmarks, {edition} edition",
        "research": f"DORA research programme, {edition}",
        "publisher": "DORA (Google Cloud)",
        "url": f"https://github.com/{REPO}/tree/{commit}/{DATA_DIR}/{edition}",
        "commit": commit, "edition": int(edition), "retrieved": dt.date.today().isoformat(),
        "licence": "Apache-2.0 (dora.dev repository)",
        "note": "Self-reported survey answers; means and standard deviations on DORA's 0–10 scale. Percentage "
                "metrics are stored on DORA's instability scale (mean × 10 ≈ mean percentage).",
    }
    current["categories"] = {m: {int(k): v for k, v in a.items()} for m, a in answers.items()}
    current["segments"] = {"industry": segment(industry), "organisation_size": segment(size)}
    path.write_text(_HEADER + yaml.safe_dump(current, sort_keys=False, allow_unicode=True, width=120))
    return path


_HEADER = """# Delivery performance benchmarks. Rebuild with `mra benchmarks --update`; do not edit the segments by hand.
# `levels_2024` is transcribed from the Accelerate State of DevOps Report 2024 (v. 2024.3, p. 13) and is kept on update.
# `conversion` documents how the fact sheet's units map onto DORA's answer categories (mra/benchmark.py).
"""
