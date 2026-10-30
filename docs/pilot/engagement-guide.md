# Running a first engagement

A step-by-step guide for the analyst running an assessment for the first time — as a pilot, inside one's own
organisation or for a client. It follows the order in which things must happen; several safeguards depend on that
order (rules before facts, facts before results).

## Roles

| Role | Who | Must not be |
|---|---|---|
| **Sponsor** | The executive accountable for the decision | The fact-sheet owner |
| **Analyst** | Runs the assessment, sees individual responses | An advocate of any option |
| **Fact-sheet owner** | Collects and attests the facts | The sponsor |
| **Estimators** | Two people who estimate costs and effort independently | — |
| **Quality reviewer** | Reviews the report before it is final | The analyst |
| **Rule signatories** | Leadership from technology, business, operations and finance | — |

## Timeline (about eight weeks)

| Week | Step | Output |
|---|---|---|
| 0 | Scoping with the sponsor | `engagement.yaml` |
| 1 | Data protection and works council | Briefing reviewed ([dpo-briefing.md](dpo-briefing.md)) |
| 1–2 | Pretest (first engagement only) | Revised questions ([pretest-protocol.md](pretest-protocol.md)) |
| 2 | Rules agreed and signed off | Signed `decision_rules.yaml` |
| 2–4 | Fact sheet | Frozen `facts.yaml` |
| 3–5 | Survey open (two weeks, one reminder) | `Responses/*.csv` |
| 5 | Verdict and preconditions | `mra decide`; `governance.yaml` |
| 6 | Draft report and its board-readiness checks | Draft PDF |
| 6–7 | Quality review and sponsor read-through | Reviewed report |
| 8 | Final report to the leadership team | `mra report --final` |

## Step by step

### Week 0 — Scoping

- `mra init engagements/<name>`; fill in `engagement.yaml`: the system, its current hosting, the decisions in scope,
  the sponsor and the fact-sheet owner, the people invited per group (for response rates), and the benchmark group.
- Agree with the sponsor whether the stakeholder map is included and whether absolute euro amounts are shown.
- Ask the sponsor for the written confirmation that no decisions about individual roles follow from the survey.

### Week 1 — Data protection

- Send [dpo-briefing.md](dpo-briefing.md) and the participant information to the DPO and, where one exists, the
  works council. Do not open the survey until both have agreed.

### Weeks 1–2 — Pretest (first engagement)

- Follow [pretest-protocol.md](pretest-protocol.md); apply the changes; record them in the pilot log.

### Week 2 — Rules

- Walk the rule signatories through `decision_rules.yaml`: the thresholds, the 80% confidence level, the switching
  margin for hosting, the accepted premium for a need-motivated move, the acceptable run-cost increase.
- Record `signed_off_by` and `signed_off_on`. **Sign-off must come before the fact sheet is frozen**; otherwise the
  report stays a draft.

### Weeks 2–4 — Fact sheet

- The fact-sheet owner fills in `facts.yaml`; coupling metrics come from `mra coupling`.
- Costs and effort as low / likely / high with their source grade, from two independent estimators — including the
  effort, external cost and duration of the first architecture steps. If comparable past programmes overran, record
  the typical overrun.
- Reconcile the invoiced run cost with the cost components with Finance; allocate any difference.
- Check the governance answer on baseline measures: if delivery measures were not measured recently, measure them
  now rather than estimating.
- Record `fact_sheet_frozen_on`.

### Weeks 3–5 — Survey

- `mra forms` → one form per group; send the invitation from a neutral sender to **all** members of each group.
- One reminder after a week. Aim for at least 15 respondents per group; five is the minimum for a group to count.
- Watch the groups the decisions depend on most (for hosting: Operations, Security, Finance). If one stays below
  five, plan to hear it directly — the report will ask for that.

### Week 5 — Verdict and preconditions

- `mra decide engagements/<name>/engagement.yaml` — read the verdict and what would change it.
- Have the sponsor, Finance, the technology lead and risk and compliance attest the preconditions in
  `governance.yaml`, each with an evidence reference.

### Week 6 — Draft report

- `mra report engagements/<name>/engagement.yaml` (add `--llm` for free text and narrative).
- Read every "board readiness" line the command prints and fix the cause, not the symptom.
- Optional: `mra review engagements/<name>/engagement.yaml` for questions an executive would ask (not on client
  engagements).

### Weeks 6–7 — Review

- The quality reviewer works through [quality-review.md](../quality-review.md).
- The sponsor reads the decision page and the qualifications. Nothing on the board's version should surprise the
  sponsor.
- Record `reviewed_by` and `reviewed_on` under `report:`.

### Week 8 — Final

- `mra report engagements/<name>/engagement.yaml --final`.
- Delete raw responses and the language-model cache on the agreed date.
- Set reminders for the checkpoints (months 3, 6 and 12) and the dates in the decision calendar.

## After the decision

The assessment is only as good as what follows it. At each checkpoint, record in the pilot log what was decided, the
success measures against their baseline, and whether a reopen criterion was met. These records are what will allow
the decision rules to be calibrated against real outcomes rather than synthetic ones.
