"""The narrative may only phrase the report's own findings."""

from mra.narrative import validate

PAYLOAD = {
    "decisions": [
        {"title": "Architecture", "verdict_label": "Restructure within the current system (modular monolith)",
         "status": "prepare_first", "interim_label": None, "leaning_label": None, "probability": 1.0,
         "economics": None, "why": ["Need for change (architecture): 3.34 (threshold: at least 2.5)."]},
        {"title": "Hosting", "verdict_label": "Improve, right-size and automate the current infrastructure",
         "status": "go", "interim_label": None, "leaning_label": None, "probability": 0.98,
         "economics": [{"option": "Improve / right-size", "ratio": 0.69}, {"option": "Move to cloud", "ratio": 2.6}]},
    ],
    "stakeholder_findings": [], "readiness": {}, "free_text": [], "next_steps": [],
}
PATHS = {"Restructure within the current system (modular monolith)", "Improve, right-size and automate the current infrastructure",
         "Gradually split into independently deployable services", "Move most workloads to a public cloud"}


def test_good_narrative_passes():
    out = {"executive": ["The evidence supports restructuring within the current system (modular monolith), with a need "
                         "score of 3.34; preconditions must be met first. Right-sizing costs 0.69 of today, while the cloud "
                         "would cost 2.6 times as much."],
           "chapters": {"architecture": "x.", "hosting": "y.", "readiness": "z.", "people": "w."}}
    n = validate(out, PAYLOAD, PATHS)
    assert not n.rejected and not n.dropped and len(n.executive) == 1


def test_invented_number_is_dropped():
    out = {"executive": ["Preconditions come first. The cloud would save 37% over five years."], "chapters": {}}
    n = validate(out, PAYLOAD, PATHS)
    assert "37%" not in " ".join(n.executive) and n.dropped


def test_recommending_another_path_is_dropped():
    out = {"executive": ["Preconditions must be met first. TechCo should move most workloads to a public cloud."], "chapters": {}}
    n = validate(out, PAYLOAD, PATHS)
    assert "public cloud" not in " ".join(n.executive)


def test_stakes_vocabulary_is_dropped():
    out = {"executive": ["Preconditions first. Operations resist the change out of self-interest."], "chapters": {}}
    assert "resist" not in " ".join(validate(out, PAYLOAD, PATHS).executive)


def test_missing_precondition_rejects_the_narrative():
    out = {"executive": ["Restructure within the current system (modular monolith) immediately."], "chapters": {}}
    assert validate(out, PAYLOAD, PATHS).rejected
