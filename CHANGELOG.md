# Changelog

Versions refer to the instrument and decision rules (`instrument/`), which an engagement signs off. The report
states the version its recommendation followed.

## 0.4 — 2026-11-02

The version for the pilot. Since the 0.3 draft (design freeze M0), the method has been built, calibrated and
reviewed from each respondent group's side.

### Decisions
- Three decisions per system: architecture, hosting, and build or buy for each candidate part.
- Keeping the current setup is always an option and is judged on the same evidence. Changing requires passing
  pre-registered gates; keeping does not.
- A path is recommended only if it holds in at least 80% of resampled draws; otherwise the report says the
  evidence is insufficient and names the inputs that would settle it.

### Evidence
- Facts outweigh opinions. Wherever a gate depends on a skill or a need, the fact alone decides, and the survey
  answer is only a perception check:
  - hardware skills and cloud skills are counted from tickets and rosters;
  - experience with distributed systems and the need for managed services are facts too.
- A group never checks a fact it supplied. Head counts are attested by the technology lead, not by the team being
  counted.
- Groups with fewer than five respondents are combined only with groups in a similar position, or not counted:
  - technology leadership with senior engineers and operations staff;
  - business leadership with finance and risk.
- Two signed sheets per engagement:
  - The **leadership intent sheet** records the horizon, priorities, stop triggers, financing constraints, prior
    commitments and promised dates. It is set before the survey opens and never changes a verdict.
  - The **risk and compliance sheet** records whether staying as it is is safe. A risk of staying makes "improve
    the current setup" the floor and adds steps required on every path.
- Integrity checks read the sources against each other. The report stays a draft while any of these holds:
  - the rules were signed off late;
  - the intent sheet was signed late;
  - the run cost does not reconcile with the cost model;
  - a hard stop cites no external requirement.

### Survey
- Each group is asked what it can answer: wording per group, grid rows per group, and items shown only when the
  option is on offer.
- The survey now asks about the cost of staying and the cost of changing. These answers are reported, never
  scored.
- Business stakeholders answer two plain preference questions instead of technical ones.
- Estimated times, to be measured in the pretest (`mra pretest`):

  | Group | Minutes |
  |---|---|
  | Engineering | 22 |
  | Operations | 19 |
  | Product | 16 |
  | Technology leadership | 16 |
  | Business | 10 |
  | Executives | 10 |
  | Finance | 8 |
  | Security | 7 |

### Report
- Opens with the decision requested on one page:
  - what is approved now and what is not;
  - the money in euros, with ranges;
  - conditions;
  - when each decision is taken again.
- Every exhibit has an action title and a "so what" that links to a step, risk, measure or section.
- Also included:
  - options appraisal;
  - roadmap with checkpoints;
  - success measures;
  - cost scenarios and break-even;
  - decision calendar;
  - risk register;
  - DORA delivery benchmark;
  - stakeholder map (optional);
  - what the groups report about staying and changing.
- A board-readiness rubric runs on every build. `--final` requires it to pass and a recorded quality review.

### Tools
- Commands to set up and run an engagement:
  - `mra init` creates an engagement with annotated templates for every input, including both sheets.
  - `mra forms` generates Google Forms.
  - `mra coupling` computes coupling facts from git history.
  - `mra pretest` produces interviewer sheets.
  - `mra review` lets a language model read the report as an executive would; local only.
- Commands to test the method:
  - `mra simulate` runs the calibration grid. The full grid shows no wrong outcome.
  - `mra stress` builds reports for generated organisations. 460 of them had no problems; CI runs 20.
- Pilot kit in `docs/pilot/`: engagement guide, DPO briefing, pretest protocol and pilot log.

### Changed since the question review (2026-11-02)
- Removed:
  - **HC01**, infrastructure as code (its fact decides);
  - **AA04**, manager protected time (G05 covers it);
  - **HC03**, cost attribution (its fact decides).
- Engineering no longer answers **AC04** (rollback, which the fact and Operations cover) or **S10** (anything else).
- The plan and its status are in [`docs/question-review.md`](docs/question-review.md).
