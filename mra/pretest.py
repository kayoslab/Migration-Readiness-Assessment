"""Interviewer sheets for the cognitive pretest: every question a group sees, in order, with an estimated answering
time and empty columns for what the interviewer observes (docs/pilot/pretest-protocol.md).
"""

from __future__ import annotations

import csv
from pathlib import Path

from .instrument import ROLES

# seconds per question, by format — a planning assumption that the pretest replaces with measured times
SECONDS = {"grid": 10, "choice": 20, "likert5": 12, "yesno": 8, "frequency": 15, "scenario": 45, "text": 60}
COLUMNS = ["seconds_measured", "comprehension", "retrieval", "judgement", "response_options", "sensitivity", "note"]


def sheets(engagement_path: str | Path, out: str | Path) -> dict[str, float]:
    """Write one CSV per group; returns the estimated minutes per group."""
    from .engagement import load_engagement
    eng = load_engagement(engagement_path)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    from .axes import derive_current_state
    current = eng.current_states(derive_current_state(eng.instrument, eng.facts))
    minutes = {}
    for role in ROLES:
        spec = eng.instrument.form_spec(role, eng.system, current, eng.config.get("consistency_example", ""))
        total = 0
        with (out / f"{role}.csv").open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["page", "item", "format", "question", "seconds_estimated", *COLUMNS])
            for q in spec:
                seconds = SECONDS.get(q["format"], 20)
                total += seconds
                text = q["text"] if not q.get("row") else f"{q['text']} — {q['row']}"
                w.writerow([q.get("page"), q["item_id"], q["format"], text, seconds, *[""] * len(COLUMNS)])
        minutes[role] = round(total / 60, 1)
    return minutes
