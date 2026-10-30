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
   rules give for the whole population (the same answering process, including noise and rounding to answer
   options, with 100 respondents per group)? Five scenario families were each moved across one threshold
   (21 positions × group sizes 5 and 15 × five seeds = **210 runs each**). A sixth, fine-grained sweep sits exactly
   on the architecture threshold.

Results are classified as **correct** · **status differs** (right outcome, wrong go / prepare first) ·
**insufficient** (the engine declines although the truth is clear) · **overconfident** (the truth is itself
"insufficient evidence", and the run asserts the outcome it leans to) · **wrong** (a different outcome).

## Results

| Run set | Runs | Correct | Insufficient | Overconfident | Wrong |
|---|---|---|---|---|---|
| Validity grid (expert cases, all sizes and noise levels) | 720 | 100 % | 0 % | 0 % | **0 %** |
| Architecture: stay → restructure | 210 | 98.1 % | 1.9 % | 0 % | **0 %** |
| Architecture: restructure → separate out one part (pain test) | 210 | 100 % | 0 % | 0 % | **0 %** |
| Architecture: realign → consolidate (distributed estates) | 210 | 100 % | 0 % | 0 % | **0 %** |
| Hosting: stay → move to cloud (cost-motivated) | 210 | 99.5 % | 0.5 % | 0 % | **0 %** |
| Hosting: stay → move back from cloud (cost-motivated) | 210 | 100 % | 0 % | 0 % | **0 %** |
| Exactly on the architecture threshold (15 per group) | 110 | 86.4 % | 2.7 % | 5.5 % | **5.5 %** |

**Targets from the plan:** ≥ 90 % correct at ≥ 15 per group — met in every sweep. Wrong ≤ 5 % — met everywhere
except where an organisation sits exactly on a threshold (see finding 5): **no wrong outcome in 1,770 runs across
the validity grid and the five sweeps.**

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
   repatriation and cost-motivated hybrid moves. **Decision (2026-11-01): the default rules count payback from
   cut-over.** Both measures are still computed and reported (`payback_months.<option>`,
   `payback_after_cutover.<option>`).
3. **The validity grid is easy by construction.** The expert cases sit far from thresholds, and fact-sheet evidence
   (weight 2) dominates survey perception, so response noise barely matters there. It confirms the rules give the
   experts' answers; reliability is measured by the sweeps.
4. **Confidence 0.80 is kept.** Raising it to 0.85 removes most boundary overconfidence (4.3 % → 0.5 % in the
   hosting sweep) at the price of a few more "insufficient evidence" verdicts; 0.90 adds no further benefit.
   Kept at 0.80.

5. **Exactly on a threshold, wrong outcomes occur at roughly the rate the confidence level allows.** When the
   population itself is "too close to call" (here: need for change within a few hundredths of 2.5), 60 % of
   15-person samples still assert a verdict — about half of them on the wrong side (30 % of runs; 20 runs, so
   ± 10 %). One step either side of that point, wrong outcomes drop to zero. This is what "80 % confidence" means;
   a stricter level trades fewer wrong calls at the threshold for more "insufficient evidence" elsewhere:

   | Confidence | Wrong, exactly at the threshold | Insufficient evidence, away from it |
   |---|---|---|
   | 0.80 (default) | 30 % | 3 % |
   | 0.85 | 20 % | 6 % |
   | 0.90 | 15 % | 7 % |
   | 0.95 | 10 % | 10 % |

   The report therefore always shows *what would change the recommendation* and *where the evidence is uncertain*:
   an organisation on a threshold sees that it is on one.
6. **How truth is defined matters.** An earlier version compared samples with noise-free answers; rounding noisy
   views to answer options shifts averages by a few hundredths, enough to create spurious "wrong" outcomes at a
   threshold. Truth is now the population outcome under the same answering process.

## Limits

- Synthetic respondents answer consistently with their scenario; real response styles (straight-lining,
  acquiescence, misunderstanding) are not simulated beyond noise. The cognitive pretest (M7) addresses wording.
- Fact-sheet values are taken as given (with their ranges); a deliberately skewed fact sheet is countered by the
  procedural safeguards in `decision_rules.yaml → fact_discipline`, not by the statistics.
- Each sweep crosses one threshold with the others held clearly on one side; interactions between thresholds
  are covered by the validity grid. Further families can be added in `mra/sim.py → FAMILIES`.
