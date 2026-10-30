"""Loading the questionnaire and responses into a tidy long format.

Every answer becomes one row: respondent_id, role, item_id, value. Missing answers are
NaN, never 0, and "Don't know" is kept as its own flag rather than folded into a score.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import Config

ROLE_FLAG_TRUE = {"TRUE", "True", "true", "1", "yes", "Yes"}


@dataclass
class Survey:
    questionnaire: pd.DataFrame   # indexed by item_id
    likert: pd.DataFrame          # long: respondent_id, role, item_id, value, dont_know
    text: pd.DataFrame            # long: respondent_id, role, item_id, answer
    respondents: pd.DataFrame     # respondent_id, role

    @property
    def roles(self) -> list[str]:
        return list(dict.fromkeys(self.respondents["role"]))

    def applicable(self, item_id: int, role: str) -> bool:
        return bool(self.questionnaire.at[item_id, role]) if role in self.questionnaire.columns else False


def load_questionnaire(path, roles: list[str]) -> pd.DataFrame:
    q = pd.read_csv(path, index_col="ID")
    q.index.name = "item_id"
    for col in ["Critical", *roles]:
        if col in q.columns:
            q[col] = q[col].astype(str).str.strip().isin(ROLE_FLAG_TRUE)
        else:
            q[col] = False
    q["Question"] = q["Question"].fillna("").astype(str).str.strip()
    return q


def _score(value, scale: dict[str, int], dont_know: set[str]) -> tuple[float, bool]:
    """Map one raw cell to (score, dont_know). Accepts labels or numeric 1..5."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return np.nan, False
    if isinstance(value, str):
        text = value.strip()
        if text in dont_know:
            return np.nan, True
        if text in scale:
            return float(scale[text]), False
        try:
            value = float(text)
        except ValueError:
            return np.nan, False
    value = float(value)
    valid = set(scale.values())
    return (value, False) if value in valid else (np.nan, False)


def load_survey(cfg: Config) -> Survey:
    q = load_questionnaire(cfg.questionnaire, cfg.roles)
    text_to_id = {t: i for i, t in q["Question"].items() if t}
    quant_ids = set(q.index[q["Type"] == "Quantitative"])
    qual_ids = set(q.index[q["Type"] == "Qualitative"])
    dont_know = set(cfg.dont_know_labels)

    likert_rows, text_rows, people = [], [], []
    for source in cfg.responses:
        role = source["role"]
        raw = pd.read_csv(source["file"], dtype=object, keep_default_na=False, na_values=[""])
        for row_no, row in raw.iterrows():
            rid = f"{role[:3].upper()}-{row_no + 1:03d}"
            people.append({"respondent_id": rid, "role": role})
            for column, value in row.items():
                item_id = text_to_id.get(str(column).strip())
                if item_id is None:
                    continue  # Timestamp, index columns, unknown questions
                if item_id in quant_ids and q.at[item_id, role]:
                    score, dk = _score(value, cfg.scale, dont_know)
                    likert_rows.append((rid, role, item_id, score, dk))
                elif item_id in qual_ids and isinstance(value, str) and value.strip():
                    text_rows.append((rid, role, item_id, value.strip()))
        # Applicable items with no column at all are still recorded as missing
        answered = {(r[0], r[2]) for r in likert_rows}
        for rid in [p["respondent_id"] for p in people if p["role"] == role]:
            for item_id in quant_ids:
                if q.at[item_id, role] and (rid, item_id) not in answered:
                    likert_rows.append((rid, role, item_id, np.nan, False))

    likert = pd.DataFrame(likert_rows, columns=["respondent_id", "role", "item_id", "value", "dont_know"])
    text = pd.DataFrame(text_rows, columns=["respondent_id", "role", "item_id", "answer"])
    respondents = pd.DataFrame(people)
    return Survey(questionnaire=q, likert=likert, text=text, respondents=respondents)
