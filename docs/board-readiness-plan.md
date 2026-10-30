# Board readiness: plan

A review of the TechCo report from the position of the executive it is addressed to (2026-10-30) found that the
analysis is sound and traceable, but the report is not yet a basis for approval and in places contradicts its own
inputs. This plan addresses the causes, not only the symptoms.

## 1. What the review found

| # | Finding | Kind |
|---|---|---|
| F1 | Delivery metrics are benchmarked and used as baselines, while governance check GV06 says they have not been measured; step 1 asks for them to be measured | Contradiction |
| F2 | Invoice-grade run cost (€0.8–1.3M a year) is roughly twice the component cost the model uses (~€0.5M); not reconciled, not flagged | Contradiction |
| F3 | Improve and keep-as-is show no uncertainty ("0.69–0.69") because their inputs are single values | False precision |
| F4 | Finance's "refresh is due, decide now" is repeated as time-critical; the fact sheet says the refresh is 30 months away and the contract ends in 36 | Contradiction |
| F5 | "5 of 7 groups prefer the recommended path" counts a tie as agreement; across respondents, keeping as is (33%) leads improving (31%) | Overstatement |
| F6 | The finding that settles the main dispute (lead time is 100% coordination, 0% process waits) drives the rules but is not shown; the summary suggests release approval instead | Evidence not surfaced |
| F7 | Security (4) and Finance (3) fall below the minimum group size, are pooled and disappear from the map; never stated | Silent gap |
| F8 | Decision rules not signed off — mentioned only in the appendix | Method integrity |
| F9 | No decision request, no euros, no architecture investment, no cost of inaction, no business framing of "speed" | Missing for a decision |
| F10 | No trigger for revisiting the split, although employees named one themselves | Missing for a decision |
| F11 | The two decisions are treated independently although they compete for the same people | Missing for a decision |
| F12 | Step numbers "010", raw IDs in the evidence appendix, duplicate rows, "100% · indicative" unexplained, unnamed owners | Presentation |

## 2. Root causes

1. **Built from the analysis outwards, not from the decision inwards.** Every chapter reports what was computed.
   Nothing starts from the questions an executive must answer: what am I approving, what does it cost, what do I
   get, what if I do nothing, when do I decide again (F9–F11).
2. **No layer that reads the sources against each other.** Facts, governance answers, survey scores and free text
   are each processed correctly in isolation; contradictions between them pass straight through (F1, F2, F4).
3. **An incomplete economic model.** Only hosting is costed, only on costs, from component inputs that are partly
   single values; the invoice total is collected but unused (F2, F3, F9).
4. **No coverage rule between what decides and what is shown.** Signals that drive a verdict can stay invisible,
   while weaker material (free-text themes) reaches the summary (F6).
5. **Method safeguards are advisory.** Unsigned rules, pooled groups and missing perspectives are recorded but do not
   change what the reader sees (F7, F8).
6. **No acceptance test from the reader's side.** Tests check correctness of computations and the absence of orphan
   "so whats"; nothing checks whether the report answers an executive's questions or is internally consistent.

## 3. Principles

- **Neutral referee stays the core.** A decision page states what the evidence supports and what is being asked for;
  it does not advocate. Alternatives and "what you would need to believe" remain alongside.
- **Every figure traceable** to a fact, a survey aggregate or a computation; no number is invented, including by the
  language model.
- **Caveat over silence, block over mislead.** A contradiction that changes how a finding should be read is printed
  next to that finding; one that undermines the verdict stops the report from being issued as final.
- **Draft and final are different products.** A report can always be generated; it can only be marked final when
  integrity checks pass and the rules are signed off.
- **New inputs only where judgement cannot be avoided** (architecture effort, benefits), always with ranges, source
  grades and two estimators.

## 4. Workstreams

### WS1 — Evidence integrity layer (causes 2, 5)

**Goal.** No report states something its own inputs contradict.

**Design.** A cross-source check engine, `mra/integrity.py`, with checks declared in `instrument/integrity.yaml`
(versioned with the rules). Each check names its sources, a condition, a severity and the findings it qualifies:

| Severity | Effect |
|---|---|
| `block` | Report is marked **draft**; cover and executive summary say why; `mra report --final` fails |
| `caveat` | A caveat is printed beside every finding, exhibit and step that uses the affected input |
| `note` | Listed in the basis of preparation |

Initial checks:

| Check | Sources | Severity |
|---|---|---|
| Delivery metrics present but GV06 = No/Partly | facts × governance | caveat on benchmark, success measures, step 1 rewritten to "verify" |
| Invoice run cost vs component total differ by > 25% | facts × facts | caveat on cost case; block if the verdict flips within the gap |
| Urgency in free text vs `hw_refresh_due_months` / `contract_end_months` | free text × facts | caveat on the free-text finding, with the dates |
| Survey perception vs measured value (existing divergences) | survey × facts | caveat (as now, moved next to the finding) |
| Group critical to a decision below minimum size (SEC, FIN for hosting; OPS for both) | participation × rules | caveat on the decision; listed on the decision page |
| Rules not signed off before `fact_sheet_frozen_on` | rules × engagement | block |
| Scripted fact without script output, attested fact without evidence | facts | note |
| Free-text claims with numbers or dates not matching facts | free text × facts | caveat |

**Acceptance.** TechCo produces caveats for F1, F2, F4, F7 and a draft banner for F8; each check has a test with a
planted contradiction and one without.

**Effort.** ~2 days.

### WS2 — Euros, timing and honest uncertainty (cause 3, part 1)

**Goal.** The cost case is in money, reconciled, dated and as uncertain as its inputs.

- Show five-year totals and annual run cost in euros next to every ratio: today, improved, hybrid, cloud; savings in
  euros and FTE.
- **Reconcile** invoice run cost with components: show both, the gap and which one the model uses; let the analyst
  set an `unallocated_run_cost` that closes the gap, sampled over its range.
- **Ranges for the component inputs** that are single values today (operations FTE share, data-centre cost,
  maintenance, refresh capex): the fact sheet accepts low/likely/high for them, defaulting to the stated grade's
  minimum width, so "0.69–0.69" cannot occur.
- **Decision calendar:** refresh due date and capex, contract end, migration window; the hosting chapter answers
  "what to decide now, and what at month 30 and 36" (right-size before the refresh; how much of the €400k a
  right-sized refresh saves; revisit hosting at contract end).
- **Cost of inaction:** keeping as is becomes an explicit row with its euro cost and the risks it carries (bus
  factor, refresh), not only the 1.00 reference.

**Acceptance.** TechCo's cost case shows €2.6M / €1.8M / €3.0M / €4.8M with ranges wider than zero, the
reconciliation, and the month-30 refresh with a sized saving.

**Effort.** ~2 days.

### WS3 — Evidence coverage (cause 4)

**Goal.** Whatever decides the verdict is shown; whatever is shown is weighed.

- **Driver coverage rule.** For each decision, list the signals in the satisfied rule branch and in the nearest
  flip; each must appear in the report (text, table or exhibit). A test fails when a driver is not rendered.
- **New exhibit: where lead time goes** — coordination between teams vs waiting on process vs build/test, from the
  survey items behind `wait_state_share` and `coordination_share`, set against cross-team change share. It answers
  the Operations-vs-Technology dispute with evidence.
- **Reconcile perception with measurement in business terms**: when executives cite speed while pipeline metrics
  are average, the report says what is slow — feature delivery across teams (cross-team change share, coordination
  share) — rather than "speed is fine".
- **Free-text claims audit.** Themes reach the executive summary only when consistent with facts and survey, or
  when presented as a disputed view with the evidence beside it (this would have stopped the "release approval as
  common ground" sentence).

**Acceptance.** TechCo shows the lead-time exhibit; the summary no longer suggests release approval as the fix; a
test plants a driver and checks it is rendered.

**Effort.** ~1.5 days.

### WS4 — Decision page (cause 1)

**Goal.** Page 1 lets an executive decide.

Structure (one page, before the current executive summary):

1. **Decision requested** — per decision: the path, what is approved now (mandate, budget for the first phase, named
   owner), what is explicitly *not* approved yet, and the date of the next decision.
2. **Situation – complication – resolution** in three short paragraphs, from the findings (computed; the language
   model may polish under the existing checks).
3. **The money** — investment for the first phase, five-year effect in euros, cost of doing nothing.
4. **Conditions** — preconditions open, integrity caveats, groups missing, rules status.
5. **When we decide again** — checkpoints with their reopen triggers (WS5) and the dated decisions from WS2.

**Neutrality safeguard.** The request is generated from the verdict and its status only; with insufficient evidence
the page requests the evidence work, not a path.

**Acceptance.** For every expert case and TechCo, the page fits on one page, contains a request, euros (where
facts allow), next decision date and conditions; the integrity status is visible.

**Effort.** ~2 days (after WS1–WS3, WS5).

### WS5 — Staged decisions and reopen triggers (cause 1)

**Goal.** Turn disagreement into a test the organisation agreed to in advance.

- For each verdict, a **reopen trigger** for the nearest alternative, built from the flip conditions and the success
  measures, e.g. "reopen the split at checkpoint C3 if cross-team change stays above 20% after module boundaries are
  enforced, or if need for change rises above 3.5".
- **Employees' own criteria:** the text analysis already extracts what would change respondents' minds (TEC: a proof
  of concept on independent deployability; ENG: enforce boundaries first). These are matched to triggers and quoted,
  so the group that disagrees sees its own test in the plan.
- **Interdependency of decisions:** the roadmap merges both decisions on one capacity line (people from the fact
  sheet: platform FTE, teams), flags overload, and sequences them.

**Acceptance.** TechCo's plan contains a split-reopen trigger at C3 referencing ENG's and TEC's criteria, and a
combined roadmap that does not schedule the restructuring and the infrastructure work on the same people at once
without saying so.

**Effort.** ~1.5 days.

### WS6 — Complete business case (cause 3, part 2)

**Goal.** Both decisions have an investment, a benefit and a payback.

- **Architecture investment inputs** (new fact-sheet items, ranged, two estimators): effort per first step in
  person-months, teams involved, external support, expected duration — with a reference-class check against
  `migration_months`-style history.
- **Benefits** (planned addition F from `report-additions-plan.md`): cost of delay per week, incident cost, expected
  change per outcome capped by documented defaults; the decision shown **with and without** benefits.
- **Programme budget by phase** combining both decisions, with FTE and euro totals.

**Acceptance.** TechCo shows an architecture investment range, a payback with and without benefits, and a phase
budget; the cost-only verdict never changes because benefits were added.

**Effort.** ~4–5 days, including a design review of benefit defaults.

### WS7 — Stakeholder fidelity (cause 5)

- Count ties as ties; titles say "prefer or tie with"; show the respondent-level split next to the group count.
- Pooled groups: state who was pooled and what their pooled answers say; when a group critical to a decision is
  pooled, raise the WS1 caveat.
- Name the sponsor and owners from `engagement.yaml → people`; the action library maps tasks to roles (engineering
  tasks to the technology lead, not the sponsor).

**Effort.** ~1 day.

### WS8 — Presentation fixes (F12)

Step numbering beyond 9, evidence appendix labels and duplicates, explanation of "indicative", merge the two
100%-bar exhibits into a single line when no alternative has a share, figures in the roadmap.

**Effort.** ~0.5 day.

### WS9 — Board-readiness quality assurance (cause 6)

**Goal.** A report cannot regress into one that misleads or does not answer the executive's questions.

- **Readiness rubric** as tests over the report context: decision request present; euros present where cost facts
  exist; each driver rendered; no integrity check silently failed; no claim in the summary contradicted by facts;
  each exhibit's "so what" linked; draft banner when required.
- **Planted-defect scenarios** in the simulator: each WS1 contradiction, a tie, a pooled critical group, unsigned
  rules — the report must catch every one.
- **Independent review pass.** An optional `mra review` runs a language-model reviewer in the role of the
  executive over the final context and lists unanswered questions; output goes to the analyst, never into the
  report.
- **Human sign-off** for consultants: a quality-review checklist (`docs/quality-review.md`) mirroring a Big Four
  second-partner review — numbers tied out, caveats agreed, sponsor read-through — and a `report.reviewed_by` field
  printed in the basis of preparation.

**Effort.** ~2 days (rubric and planted defects), ~1 day for the reviewer and checklist.

## 5. Sequence

**Status (2026-10-30):** Phase 1 done — WS1, WS7, WS8 and the coverage part of WS3. Findings F1, F2, F4–F8 and
F12 are addressed; F3 and F9–F11 belong to phase 2 and 3. Deviations from the plan: the run-cost check is a caveat
only (the block condition "verdict flips within the gap" needs WS2's allocation of the difference); free-text claims
are checked against named survey measures (`disputed_claims`) rather than all numbers in the text.

| Phase | Workstreams | Outcome | Effort |
|---|---|---|---|
| **1. Do not mislead** | WS1, WS7, WS8, WS3 (coverage rule, lead-time exhibit) | Every contradiction surfaced; draft vs final; ties and pooled groups honest | ~5 days |
| **2. Make it decidable** | WS2, WS5, WS4 | Euros, decision calendar, reopen triggers, decision page | ~5.5 days |
| **3. Complete the business case** | WS6 | Architecture investment, benefits, phase budget | ~4–5 days |
| **4. Keep it that way** | WS9 | Rubric, planted defects, reviewer, sign-off | ~3 days |

Phase 1 comes first because a report that is easy to decide on but contradicts its inputs is worse than one that is
hard to decide on. WS9's rubric tests are written alongside each phase, not only at the end.

## 6. Decisions (agreed 2026-10-30)

1. **Blocking.** Unsigned rules and `block`-level contradictions prevent a final report: the report is generated as
   a draft with the reasons on the cover, and `mra report --final` fails.
2. **Euros in the client report.** Shown by default; an engagement switch can suppress absolute figures.
3. **Architecture effort estimates.** Provided by the technology lead with a second, independent estimator.
4. **Benefits.** The report stays cost-only until a pilot has run; WS6 builds the architecture investment and phase
   budget, and the benefit model waits for pilot data.
5. **Reviewer persona.** `mra review` is a local tool for the analyst and is not run on client engagements.

## 7. Risks

| Risk | Mitigation |
|---|---|
| Decision page drifts into advocacy | Generated from verdict and status only; integrity and alternatives on the same page; neutrality test across all expert cases |
| Integrity checks produce noise and are ignored | Severity levels; caveats appear only beside affected findings; thresholds calibrated on the expert cases |
| New inputs lengthen the fact sheet | Architecture effort and benefits optional; the report states what is missing instead of guessing |
| Euros make the report sensitive | Classification already on every page; engagement switch (decision 2) |
| Scope grows | Phases are independently shippable; phase 1 alone fixes everything that misleads |
