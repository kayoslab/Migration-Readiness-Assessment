"""The generated Google Forms match what the analysis reads back from their CSV exports."""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pandas as pd
import pytest

from mra.engagement import load_engagement
from mra.forms import apps_script, form_specs

ROOT = Path(__file__).resolve().parents[1]
TECHCO = ROOT / "examples" / "techco" / "engagement.yaml"


def test_every_export_header_is_a_form_title():
    spec = form_specs(TECHCO)
    eng = load_engagement(TECHCO)
    for form in spec["forms"]:
        titles = set()
        for q in form["questions"]:
            titles.update(f"{q['title']} [{r}]" for r in q["rows"]) if q["kind"] == "grid" else titles.add(q["title"])
        exported = pd.read_csv(ROOT / "examples" / "techco" / f"Responses/{form['group']}.csv", nrows=0).columns
        assert set(exported) - {"Timestamp"} == titles, form["group"]
    assert not eng.problems


def test_pages_in_order_and_privacy_settings():
    script = apps_script(TECHCO)
    for setting in ("setCollectEmail(false)", "setLimitOneResponsePerUser(false)", "setRequired(false)"):
        assert setting in script
    spec = json.loads(re.search(r"const SPEC = (\{.*?\n\});", script, re.S).group(1))
    for form in spec["forms"]:
        pages = [q["page"] for q in form["questions"]]
        assert pages == sorted(pages)
        assert "No option has been chosen" in form["description"]


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_script_is_valid_javascript(tmp_path):
    path = tmp_path / "forms.js"
    path.write_text(apps_script(TECHCO))
    subprocess.run(["node", "--check", str(path)], check=True)
