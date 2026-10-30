"""`mra init <folder>`: a blank v3 engagement with annotated templates for every input."""

from __future__ import annotations

import datetime as dt
import re
import shutil
from pathlib import Path

from .instrument import ROLES, load_instrument

CHECKLIST = """# Engagement checklist

1. Name the system in scope and its current hosting in `engagement.yaml`; name the sponsor and the fact-sheet owner
   (they must be different people).
2. Agree `decision_rules.yaml` with stakeholders and record who signed it off — **before** any results are seen.
3. Fill in `facts.yaml`. Produce the coupling metrics with `mra coupling <repo> --modules modules.yaml` and paste the
   output. Give cost inputs as low / likely / high with a source grade; use two independent estimators for them.
   Record `fact_sheet_frozen_on` in `engagement.yaml` once the sheet is complete.
4. Generate the survey forms (`mra forms engagement.yaml`), send them with the participant pack
   (`instrument/participant-information.md`) and export each group's responses to `Responses/<GROUP>.csv`.
5. Run `mra decide engagement.yaml` for the verdict.
6. Complete `governance.yaml` for the recommended path, with evidence references.
7. Run `mra decide engagement.yaml --pdf report.pdf` for the report.
"""


def _yaml_str(text: str) -> str:
    return '"' + str(text).replace('"', "'") + '"'


def facts_template(ins) -> str:
    lines = ["# Fact sheet — one entry per fact. Delete the entries you cannot provide; required ones are marked.",
             "# Numbers:    {value: 12, source: ..., date: YYYY-MM-DD, attester: ...}",
             "# Ranges:     {low: .., likely: .., high: .., grade: invoice|quote|calculator_export|benchmark|estimate, source: ...}",
             "# Two estimators: {estimates: [{estimator: ..., low: .., likely: .., high: .., grade: ...}, {...}]}",
             "# Categories: {value: <one of the listed options>, source: ...}", ""]
    current = None
    for fid, f in ins.facts.iterrows():
        heading = f"{f['decision']} · {f['axis']}"
        if heading != current:
            lines += ["", f"# ===== {heading} " + "=" * max(0, 90 - len(heading))]
            current = heading
        req = {"true": "REQUIRED", "false": "optional", "if_distributed": "required if several deployables",
               "if_cloud": "required if currently in the cloud", "if_hybrid": "required if currently hybrid", "if_distinct_profile": "required if a component has a distinct profile"
               }.get(f["required"], f["required"])
        lines.append(f"# {f['label']} [{f['unit']}] — {req}")
        if f["how_to_measure"]:
            lines.append(f"#   how: {f['how_to_measure']}")
        if f["kind"] == "category":
            lines.append(f"#   options: {f['categories'].replace('|', ' | ')}")
            lines.append(f"{fid}: {{value: null, source: null, date: null}}")
        elif f["range"] == "true":
            lines.append(f"{fid}: {{low: null, likely: null, high: null, grade: estimate, source: null, date: null}}")
        else:
            lines.append(f"{fid}: {{value: null, source: null, date: null}}")
    return "\n".join(lines) + "\n"


def governance_template(ins) -> str:
    lines = ["# Preconditions — complete after the verdict, for the recommended path.",
             "# answer: Yes (with an evidence reference) | Partly | No", ""]
    for cid, g in ins.governance.iterrows():
        lines += [f"# {g['statement']}", f"#   evidence: {g['evidence_required']} · attested by: {g['attested_by']} · applies to: {g['applies_to']}",
                  f"{cid}: {{answer: null, evidence: null, attested_by: null}}", ""]
    return "\n".join(lines)


def engagement_template(name: str) -> str:
    return f"""# Engagement: {name}
system: {_yaml_str('the <system name>')}            # used in every survey question
current_hosting: own_infrastructure           # own_infrastructure | cloud | hybrid
consistency_example: {_yaml_str('<an example from your business, e.g. an order shows as paid before stock is reserved>')}
instrument: {_yaml_str('../instrument')}                    # path to the instrument folder of this repository
rules: decision_rules.yaml                    # the signed-off copy for this engagement
people:
  sponsor: null                               # accountable executive of the change under discussion
  fact_sheet_owner: null                      # must not be the sponsor
fact_sheet_frozen_on: null                    # date the fact sheet was completed, before results were seen
facts: facts.yaml
governance: governance.yaml
responses:                                     # one form export per group; remove groups you do not survey
{chr(10).join(f'  {r}: Responses/{r}.csv' for r in ROLES)}
invited: {{}}                                   # people invited per group, e.g. ENG: 22 (for response rates)
benchmark:                                     # comparison group for delivery measures (mra benchmarks lists the data)
  industry: all                                # e.g. technology, financial_services, … (see instrument/benchmarks.yaml)
  organisation_size: all                       # e.g. fewer_than_1000 (500 to 999 employees)
targets: {{}}                                   # success-measure targets agreed with the sponsor, by fact id
influence: {{}}                                 # stakeholder map: GROUP: high | medium | low (default: EXE, TEC high)
report:
  stakeholder_map: false                       # discuss with the sponsor before switching on
  show_amounts: true                           # false hides absolute euro amounts (ratios remain)
  reviewed_by: null                            # quality reviewer (docs/quality-review.md); required for --final
  reviewed_on: null
  organisation: null
  title: Architecture and Hosting Assessment
  subtitle: null
  prepared_for: null
  prepared_by: null
  date: null                                   # null = today
  classification: Strictly confidential
llm:
  model: anthropic/claude-opus-5.5             # free-text analysis via the Vercel AI Gateway (mra decide --llm)
  redact: true
  redact_terms: []                             # names of people, customers or systems to remove before sending
"""


def init(folder: Path, instrument_dir: Path) -> list[Path]:
    folder.mkdir(parents=True, exist_ok=False)
    ins = load_instrument(instrument_dir)
    rel = Path(*([".."] * len(folder.resolve().relative_to(instrument_dir.resolve().parent).parts))) / instrument_dir.name \
        if folder.resolve().is_relative_to(instrument_dir.resolve().parent) else instrument_dir.resolve()
    files = {
        "engagement.yaml": engagement_template(folder.name).replace('"../instrument"', f'"{rel}"'),
        "facts.yaml": facts_template(ins),
        "governance.yaml": governance_template(ins),
        "CHECKLIST.md": CHECKLIST,
    }
    written = []
    for name, text in files.items():
        (folder / name).write_text(text)
        written.append(folder / name)
    rules = folder / "decision_rules.yaml"
    shutil.copy(instrument_dir / "decision_rules.yaml", rules)
    text = re.sub(r"^signed_off_by: null.*$", f"signed_off_by: null              # names of those who agreed the rules "
                  f"({dt.date.today():%Y-%m-%d} template)", rules.read_text(), count=1, flags=re.M)
    rules.write_text(text)
    (folder / "Responses").mkdir()
    return written + [rules]
