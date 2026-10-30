# Build or buy

The third decision, assessed per *candidate part* of the system named in `engagement.yaml`: keep building the part,
or replace it with a product (software bought as a service or licence). Implemented in `mra/sourcing.py`; the rules
are pre-registered in `decision_rules.yaml → sourcing`.

## The rule

Replace a part with a product only if **all** of these hold:

| Condition | Evidence | Default threshold |
|---|---|---|
| The part does not set the organisation apart | Survey SO01, rated per part by Product, Business, Technology leadership and Executive; every group counts equally | below 2.5 on 1–5 |
| A product meets enough of its requirements as they are | Requirements walk-through with the vendor (fact `product_coverage_pct`) | at least 80% |
| Buying is clearly cheaper over five years | Today's people and running cost against licence, remaining people, one-off switch, running both until the switch, and the cost of leaving the product again | at most 0.85 of building |

Otherwise keep building it. As for the other decisions:

- every draw resamples the respondents within their group and every estimate within its range (minimum width by
  source grade; two estimators' union); a verdict needs 80% of draws, otherwise the evidence is insufficient;
- **hard stops** rule replacing out: the data cannot be exported from the product, or the product does not meet a
  compliance requirement of the part;
- **keeping needs no preconditions; replacing does**: an accountable sponsor, funding, and an exit plan (data export
  tested, contract terms that allow leaving — governance check GV13);
- a part whose tables other parts also write (more than 20%) must have its data separated first: the verdict is
  *prepare first*. Where the architecture verdict is a restructuring, its data-ownership step does exactly that,
  and the report links the two.

## Inputs

- Engagement: `sourcing: {candidates: {id: name}, facts: sourcing.yaml}`; `mra init` writes both templates.
- Facts per part (`sourcing.yaml`, same formats as `facts.yaml`): people maintaining it, running cost, licence,
  one-off switching cost, people still needed, months to switch, exit cost, requirements coverage, data export,
  compliance, and the share of its tables other parts also write.
- Survey: one question with one row per candidate part, for the business-facing groups (SO01).

## In the report

A chapter after Hosting with an exhibit (how much each part sets the organisation apart against how much of it a
product covers), and per part: verdict and status, why, what would change it, five-year cost of keeping and
replacing in euros, hard stops, preconditions, and the link to the architecture decision. Replacing feeds the
decision page, next steps (proof of concept, export test, separating the data), the budget by phase, the risk
register (dependence on the vendor; coverage below the bar within its range) and the reopen criteria (keep building
if the proof of concept shows too little coverage or too high a cost; reconsider a kept part at the annual review).

## Calibration

Six expert cases (`mra/cases.py → SOURCING_CASES`): a commodity part a product covers and that is cheaper to buy
(replace); a differentiating part (keep); poor coverage (keep); no data export (keep, ruled out); data shared with
other parts (replace, prepare first); coverage at the bar from a rough estimate (insufficient). Across group sizes
5, 10, 15 and 30 and five seeds each — 120 runs — every case was decided correctly.

## Limits

- Differentiation is a judgement by the business-facing groups; it is not checked against a strategy document.
- The cost comparison covers the part alone; effects on neighbouring parts beyond separating its data are not
  modelled.
- Only replacement is assessed; adopting a product for a new capability (where nothing exists to keep) is not.
