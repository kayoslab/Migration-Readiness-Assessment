# Calibration report (M5)

Generated with `mra simulate` (full grid and sweeps) on synthetic engagements built by `mra/scenario.py`.
Re-run after any change to the instrument or rules; CI runs a reduced grid (`mra simulate --quick`) and fails
above 5 % wrong outcomes.

## Method

Two questions are answered separately (`mra/sim.py`):

1. **Validity** — do the rules reach the outcome the experts expect? The 12 walk-through cases from the M0
   reviews (`mra/cases.py`, 7 architecture, 5 hosting + a cost-symmetry case) were run at group sizes 5 / 10 / 15 /
   30 per stakeholder group, three levels of response noise (spread of personal optimism 0.3 / 0.6 / 0.9) and five
   seeds: **720 runs**. Truth is the experts' expected outcome.
2. **Reliability near thresholds** — given the rules, how often does a realistic sample reproduce what the same
   rules give on noise-free answers from 60 respondents per group? Two scenario families were moved continuously
   across a threshold (21 positions × group sizes 5 and 15 × five seeds = **210 runs each**):
   - *architecture need*: from a small, loosely coupled organisation to a large, tightly coupled one
     (truth moves from "stay and improve" to "modular monolith");
   - *hosting cost*: own infrastructure with no specific need while the cloud estimate falls (truth moves from
     "stay" to a cost-motivated "move to cloud").

Results are classified as **correct** · **status differs** (right outcome, wrong go / prepare first) ·
**insufficient** (the engine declines although the truth is clear) · **overconfident** (the truth is itself
"insufficient evidence", and the run asserts the outcome it leans to) · **wrong** (a different outcome).

## Results

| Run set | Runs | Correct | Insufficient | Overconfident | Wrong |
|---|---|---|---|---|---|
| Validity grid (all sizes, all noise levels) | 720 | 100 % | 0 % | 0 % | **0 %** |
| Architecture threshold sweep | 210 | 98.1 % | 1.9 % | 0 % | **0 %** |
| Hosting cost sweep (payback from decision) | 210 | 100 %¹ | 0 % | 0 % | **0 %** |
| Hosting cost sweep (payback from cut-over) | 210 | 95.7 % | 0 % | 4.3 % | **0 %** |

¹ Trivially: under this rule the truth never becomes "move to cloud" — see finding 2.

**Targets from the plan:** ≥ 90 % correct at ≥ 15 per group — met everywhere. At small groups, "insufficient
evidence" rather than a wrong outcome (wrong ≤ 5 %) — met: **no wrong outcome in 1,350 runs**.

## Findings

1. **Near the architecture threshold the engine declines rather than guesses.** With 5 people per group, runs just
   below the stay → modular-monolith boundary give "insufficient evidence" in 20–60 % of cases and never the wrong
   outcome; with 15 per group they are always correct.
2. **A payback bar counted from the decision makes cost-motivated moves practically unreachable.** Payback is
   dominated by migration duration, not by the size of the saving: with a 10–18-month migration, an option that is
   37 % cheaper and saves 2.8 salaries a year still pays back only after 20–30 months, so the noise-free truth is
   "insufficient evidence" and lower savings give "stay". Counting payback **from cut-over** ("does the new setup
   recover its switching costs within two years of running?") removes the artefact: the verdict moves from "stay" to
   "move to cloud" at a saving of roughly 35 %, through a short "insufficient evidence" band. The same applies to
   repatriation and cost-motivated hybrid moves. **This is a rule decision for the engagement owner**; both measures
   are computed (`payback_months.<option>`, `payback_after_cutover.<option>`).
3. **The validity grid is easy by construction.** The expert cases sit far from thresholds, and fact-sheet evidence
   (weight 2) dominates survey perception, so response noise barely matters there. It confirms the rules give the
   experts' answers; reliability is measured by the sweeps.
4. **Confidence 0.80 is sufficient.** Raising it to 0.85 removes most boundary overconfidence (4.3 % → 0.5 % in the
   hosting sweep) at the price of a few more "insufficient evidence" verdicts; 0.90 adds no further benefit.
   Kept at 0.80.

## Limits

- Synthetic respondents answer consistently with their scenario; real response styles (straight-lining,
  acquiescence, misunderstanding) are not simulated beyond noise. The cognitive pretest (M7) addresses wording.
- Fact-sheet values are taken as given (with their ranges); a deliberately skewed fact sheet is countered by the
  procedural safeguards in `decision_rules.yaml → fact_discipline`, not by the statistics.
- Thresholds not crossed by a sweep (e.g. targeted extraction, consolidation, repatriation) are covered only by
  the validity grid; further sweep families can be added in `mra/sim.py → FAMILIES`.
