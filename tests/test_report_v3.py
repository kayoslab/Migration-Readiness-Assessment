"""v3 report: plain-language explanations, next steps from the action library, and the PDF build."""

import sys
from pathlib import Path

import pytest

from mra.assess import assess
from mra.recommend import next_steps
from mra.report_v3 import build_context, build_report

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "examples"))
from build_techco import TECHCO  # noqa: E402

from mra.scenario import build  # noqa: E402


@pytest.fixture(scope="module")
def techco(tmp_path_factory):
    return assess(build(TECHCO, tmp_path_factory.mktemp("techco"), ROOT / "instrument", seed=11), draws=300)


def test_example_verdicts(techco):
    arch, host = techco.results["architecture"], techco.results["hosting"]
    assert (arch.verdict, arch.status) == ("modular_monolith", "prepare_first")
    assert arch.gates["required"]["baseline"]["status"] == "fail"
    assert (host.verdict, host.status) == ("improve_current", "go")


def test_next_steps_come_from_the_library(techco):
    steps = next_steps(techco)
    phases = [s["phase"] for s in steps]
    assert phases == sorted(phases, key=["before_commitment", "capability", "first_steps", "people", "evidence"].index)
    baseline = next(s for s in steps if s["phase"] == "before_commitment")
    assert "lead time" in baseline["action"] and "not met" in baseline["reason"]
    assert all(s["owner"] for s in steps)


def test_plain_language_no_raw_signal_names(techco, tmp_path):
    ctx = build_context(techco, tmp_path, ROOT)
    text = " ".join(" ".join(d["why"] + d["flips"]) for d in ctx["decisions"])
    assert "need.architecture" not in text and "fact." not in text and ">=" not in text
    assert any("would apply if" in f for d in ctx["decisions"] for f in d["flips"])


def test_pdf_builds(techco, tmp_path):
    pdf = build_report(techco, tmp_path / "techco.pdf")
    assert pdf.stat().st_size > 100_000
