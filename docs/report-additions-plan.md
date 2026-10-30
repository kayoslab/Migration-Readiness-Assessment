# Report additions: plan and evaluation

Status of the additions that bring the report to the standard of an advisory deliverable.

| Addition | Status |
|---|---|
| Options appraisal | Done |
| What you would need to believe | Done |
| Risks, assumptions and dependencies | Done |
| Basis of preparation (notice, glossary, response rates) | Done |
| Roadmap with stage gates | Planned — **A** |
| Success measures | Planned — **B** |
| Scenarios | Planned — **C** |
| Benchmark against published bands | Planned — **D** |
| Stakeholder map | Planned — **E** |
| Benefit side of the business case | Evaluated — **F**, needs new inputs and safeguards |
| Sustainability (energy and carbon) | Evaluated — **G**, needs new inputs |

Recommended order: **A, B, C** (no new inputs, high value) → **E** (no new inputs, but a sensitive exhibit) →
**D** (needs a maintained reference table) → **F** (most valuable, most gameable) → **G**.

---

## A. Roadmap with stage gates

**What.** A phased plan — *now* (0–3 months), *next* (3–6), *later* (6–12+) — for the recommended path, with
explicit review points where the agreed stop criteria are checked, rendered as a simple timeline exhibit.

**Inputs.** All existing: next steps and their phases, preconditions and hard stops (before commitment), capability
gaps (preparation), outcome first steps, `migration_months` and `dual_run_months` for hosting moves, the stop
criteria gate and the track-record flag.

**Method.** Deterministic placement: preconditions and hard stops in *now*; capability building in *now/next*;
first steps on the path in *next*; cut-over windows from the fact sheet's migration range (likely value, with the
high estimate shown as a hatched extension). Review gates at the end of each phase, each tied to the outcome measures
from B. The interim step, if any, runs in *now*.

**Risks.** A timeline invites being read as a commitment. Mitigation: label it "indicative sequencing", show the
migration duration as a range, and never place a start date before the open preconditions.

**Effort.** Medium (≈ 1 day): one module, one chart, one chapter section. Test: phases consistent with statuses.

**Recommendation.** Build first. It is the single most-asked-for page in a board pack and uses only data we have.

## B. Success measures

**What.** A small table of the measures by which the decision will be judged later: measure, baseline, target,
owner, review cadence. One set per decision.

**Inputs.** Existing: delivery metrics from the fact sheet (lead time, deployment frequency, change failure rate,
time to restore, cross-team change share), cost ratios, and governance check GV07 (outcome measures). New, optional:
targets agreed by the sponsor (`engagement.yaml → targets`).

**Method.** Baseline = current fact value. Default target derived from the outcome: e.g. *restructure* → cross-team
change share below the "low" band; *improve current* → infrastructure toil and cost ratio; *move to cloud* → cost
within the agreed premium and capacity lead time in days. Where no target is agreed, show "target to be agreed" —
never invent one.

**Risks.** Default targets may be read as promises. Mitigation: mark defaults as proposals; agreed targets take
precedence and are labelled as agreed.

**Effort.** Small (≈ half a day).

**Recommendation.** Build with A; the stage gates in A review these measures.

## C. Scenarios

**What.** Named cost scenarios — conservative, base, favourable — for each hosting option, next to the existing
ranges, plus the break-even values ("the cloud wins only if compute falls below €X").

**Inputs.** Existing: all ranged facts, the tornado and the TCO model.

**Method.** Conservative = all inputs at the end of their range that disadvantages the option; favourable = the
opposite; base = likely values. Break-even by solving the cost ratio for the input with the largest swing, holding
others at likely values. Shown as a small table and one sentence per option.

**Risks.** Extreme scenarios combine unlikely extremes; label them as bounds, not forecasts. The existing ranges
remain the primary measure of uncertainty.

**Effort.** Small (≈ half a day).

**Recommendation.** Build with A and B; it answers the board's usual "and in the worst case?" directly.

## D. Benchmark against published bands

**What.** The organisation's delivery metrics placed in the published performance bands of the DORA research
programme (elite / high / medium / low), and infrastructure toil and cost transparency against stated reference
ranges where public sources exist.

**Inputs.** Existing fact-sheet metrics. New: a maintained reference table (`instrument/benchmarks.yaml`) with the
band boundaries, the report year and the source.

**Method.** Band lookup per metric; an exhibit with the organisation's position on each band scale.

**Risks.** Bands change from year to year (the 2024 report re-cut change failure rate); a stale table misleads.
Mitigation: the table records its source year, and the report prints it; validation warns when it is older than
two years. Only published, citable sources — no invented "industry averages".

**Effort.** Small (≈ half a day) plus keeping the table current.

**Recommendation.** Build after A–C; worth it for executive audiences, low risk with the source year shown.

## E. Stakeholder map

**What.** Groups positioned by *support for the recommended path* and *influence*, with a communication approach per
quadrant (manage closely, keep satisfied, keep informed, monitor).

**Inputs.** Existing: preference shares (support for the verdict), stakes, concern, seniority. New, optional:
an influence rating per group (`engagement.yaml → influence`), because influence is not measurable from the survey.

**Method.** Support = share of the group preferring the recommended path (or its interim step), with the stake test
and concern as annotations. Influence from the engagement configuration, defaulting to a stated assumption
(leadership groups high, others medium).

**Risks.** The most politically sensitive exhibit in the report. A map can read as a list of opponents. Mitigations:
groups only (never below the minimum size), neutral quadrant labels, the "never used to weight answers" statement
beside it, and an engagement switch to leave it out of the client report.

**Effort.** Small to medium (≈ half a day).

**Recommendation.** Build, switched off by default for self-assessments and on for consultant engagements where it is
discussed with the sponsor first.

## F. Benefit side of the business case

**What.** Today the cost model compares costs only. A full business case nets the **benefits** of each option against
its costs: value of faster delivery (cost of delay), avoided incidents, avoided hiring or capacity constraints,
revenue enabled. Output: net present value and payback including benefits, per option.

**Inputs (new).**
- Value of one week of earlier delivery for the typical roadmap item (cost of delay), with range and source grade.
- Expected change in lead time per option — derived from the fact sheet and the outcome (with a stated, conservative
  default effect size per outcome, documented as judgement).
- Cost of a production incident (or of an hour of downtime) and the expected change in incident rate per option.
- Optional: revenue or margin enabled by named initiatives that are blocked today (from the open answers and AN06),
  only with a named business owner.

**Method.** Benefits as monthly cash flows from cut-over (ramped), discounted like costs, sampled from their ranges in
the same draws (common random numbers). The rules gain a benefit-aware variant of the cost test, pre-registered as an
option; the default rules stay cost-only so that benefits cannot silently decide.

**Risks.** Benefits are the most gameable numbers in any business case — an advocate can make any option win with an
optimistic cost of delay. Safeguards, all mandatory:
- two independent estimators and the minimum range width by grade (as for costs);
- benefit effect sizes per outcome capped by documented defaults unless evidence is attached;
- the report shows the decision **with and without** benefits side by side, and the break-even benefit needed to
  change the verdict;
- benefits never enter a hosting decision that is cost-motivated without being labelled as such.

**Effort.** Large (≈ 3–4 days): model, inputs, rules variant, safeguards, simulator family, report section, tests.
Calibration of default effect sizes needs literature (Accelerate / DORA research on delivery performance and
organisational outcomes) and is the uncertain part.

**Recommendation.** The most valuable remaining addition, but only with the safeguards. Build after A–E, starting with
a design review of the default effect sizes and the "with and without benefits" presentation.

## G. Sustainability (energy and carbon)

**What.** Estimated energy use and emissions per hosting option over the horizon, reported next to cost — not as a
decision criterion unless an engagement pre-registers one.

**Inputs (new).** Current power draw or energy bill of own infrastructure; data-centre PUE; grid emission factor for
the location; cloud provider's published emission data or a regional factor for the target region; growth from the
existing facts.

**Method.** kWh per option from power and utilisation (right-sizing reduces it), emissions = kWh × factor; cloud via
provider-published factors or the same location method. Ranges sampled like costs.

**Risks.** Cloud emission figures are reported inconsistently across providers (market- vs location-based); mixing
them misleads. Mitigation: one method per report, stated; ranges wide by default; shown as indicative.

**Effort.** Medium (≈ 1–2 days) including the input templates and a reference note on emission-factor sources.

**Recommendation.** Build on demand — increasingly expected in EU engagements where sustainability reporting
applies, but rarely decisive for the architecture or hosting question itself.

---

## Proposed sequence

1. **A + B + C** together (≈ 2 days): roadmap with stage gates, success measures, scenarios and break-evens.
2. **E** (≈ half a day): stakeholder map with an engagement switch.
3. **D** (≈ half a day): benchmark with a maintained, dated reference table.
4. **F** (≈ 3–4 days): design review of benefit defaults and presentation first, then build.
5. **G** (≈ 1–2 days): when an engagement asks for it.

Each step is testable on generated answers: the simulator and the TechCo example cover A–E without new data; F and G
need new synthetic inputs in the scenario builder.
