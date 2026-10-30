# Phase 2 plan: from readiness score to recommended path

## Goal

v1/v2 answer "are we ready to migrate?". v3 answers **"which path is right for us, and how sure are we?"** —
separately for each decision on the table: mainly **architecture** (keep ↔ modularise ↔ microservices) and
**hosting** (bare metal ↔ hybrid ↔ cloud). Every recommendation rests on hard evidence, is robust against
personal interests, and follows rules agreed before results are seen. The v2 scoring code remains the engine
underneath; Phase 2 builds on top of it.

## Status

| Milestone | State |
|---|---|
| M0 Design freeze | Approved (instrument v0.3, two review rounds) |
| M1 Instrument & data layer | Done — `mra validate`, form spec, engagement loading |
| M2 Architecture decision | Done — expert walk-through cases (a)–(g) pass for 10/10 seeds |
| M3 Hosting decision | Done — 5-year TCO model; hosting cases (a)–(e) + symmetry case pass; near-threshold case gives "insufficient evidence", never a wrong outcome |
| M4 Stakes & fit | Done — within-respondent stake test (no false alarms on random answers across seeds), watermelon and leadership-disagreement checks, disclosure control, fit per outcome, `mental_model` code |
| M5 Simulator & calibration | Done — 1,350 simulated runs, no wrong outcome; see `docs/calibration.md`. Open decision: payback counted from decision or from cut-over |
| M6–M7 | Open |

## Agreed defaults

| Topic | Decision |
|---|---|
| Decisions in scope | Architecture and hosting; build-vs-buy / SaaS later |
| Collection channel | Google Forms, generated from the item bank |
| Stakes questions | Anonymous and optional; reported at group level only (n ≥ 5) |
| Fact sheet | One accountable lead per system, assisted by a git change-coupling script |
| v2 data | Remains analysable, as readiness only |
| Uncertainty | Prefer "insufficient evidence" over a guessed outcome |

---

## 1. Decision model

### 1.1 Decisions are evaluated separately

`assessment.yaml` gets a `decisions:` block. Each decision has a current state and its own outcomes:

| Decision | Outcomes |
|---|---|
| **Architecture** | stay and improve practices · modular monolith · targeted extraction · broad decomposition · consolidate (already over-split) |
| **Hosting** | stay as is · improve current infrastructure (automation, observability) · hybrid · move to cloud · repatriate (if starting in the cloud) |

A proposal such as "microservices **and** move to the cloud" becomes two independent verdicts, which usually differ.

### 1.2 Inputs per decision

| Axis | Question | Architecture inputs | Hosting inputs |
|---|---|---|---|
| **Need (N)** | Is there real pain, and does this decision address it? | Teams per deployable, cross-team change share, where lead time goes, blast-radius incidents, components with distinct scale/SLO/compliance needs | Load variability (peak/average), growth, hardware end of life, geographic reach, managed services genuinely required |
| **Capability (C)** — scored in sub-areas | Can we build and run the target? | Delivery (DORA, test automation), platform & operations, data separability, **mindset: domain thinking**, **mindset: distributed operations** | Infrastructure as code & automation, cloud skills, cost discipline, operations capacity |
| **Gates (G)** — pass / fail / unresolved, attested with evidence after the verdict | Are the preconditions in place for the leading outcome? | Sponsor with budget and roadmap authority, committed funding incl. dual running, protected capacity, baseline metrics, agreed stop criteria | Same, plus compliance / data residency, contractual lock-in |
| **Locality (L)** — architecture only | Is the pain concentrated? | Share of friction in the top 2–3 areas, data ownership of those areas | – |
| **Economics (E)** | Does it pay off? | Run cost of the target architecture vs today | 3-year total cost of ownership per option, with ranges |
| **Alignment & stakes** — diagnostic, never decisive | Who wants what, and why? | Preferences, personal stakes, cross-group and within-leadership gaps | Same |

**Facts over opinions:** each axis combines fact-sheet evidence (weight 2) with survey perception (weight 1).
Where the two diverge by more than one band, that is reported as a finding in its own right.

### 1.3 Decision rules as declarative YAML

Pre-registered in `decision_rules.yaml`; each threshold records its source (DORA bands, Newman, Team Topologies,
or "agreed in engagement"). Conditions are structured data, never executable code. Starting set for
architecture (calibrated in M5):

| Outcome | Rule |
|---|---|
| **Consolidate** (distributed) | ≥ 30% lockstep releases and > 3 services per team or ≥ 30% cross-service changes |
| **Realign services** (distributed) | Need ≥ 2.5 without over-splitting |
| **Targeted extraction** | A component with a distinct compliance scope, availability tier, or load profile that one node cannot absorb, **and** evidence that it hurts today (incidents, compliance scope, scaling cost); seam data, pipeline, platform basics and distributed-operations fit as capabilities |
| **Stay and improve** | N < 2.5, *or* lead time dominated by process waits (not release trains) with little coordination, < 15% cross-team changes and weak delivery pipeline — "the problems would follow you" |
| **Broad decomposition** | N ≥ 3.5, ≥ 6 teams, diffuse pain; pipeline, platform and operations ≥ 3.5, shared tables < 20%, provisioning ≤ 2 days, both fit axes ≥ 3.5, run cost within the pre-registered tolerance |
| **Modular monolith** | Default when N ≥ 2.5 and the stricter conditions above are not met |
| **Hard stops** (from facts) | Rollback > 60 min, manual deployment steps, no central logs/metrics, no on-call owner → "prepare first" for extraction and decomposition, with the next outcome as interim step |

Delivery is split into **pipeline quality** (a precondition) and **throughput** (diagnostic only), because a coupled
monolith cannot show high throughput precisely because it is coupled.

Rules are evaluated in a fixed order. Missing inputs make a condition *unresolved*, not false. A failed gate, hard
stop or capability never yields "proceed"; it produces "prepare first" with the blocked outcome, plus the best
outcome whose preconditions already pass as the interim step. The report also shows a **shadow verdict** under the
unmodified default rules, and "insufficient evidence" is explicitly not a recommendation to keep the current state.

### 1.4 Uncertainty propagates to the outcome

Each bootstrap draw resamples respondents within group **and** samples fact-sheet values from their stated
ranges, producing axis scores and an outcome. **Outcome probability = share of draws.** The report states the
leading outcome with its probability, or "insufficient evidence" below the agreed confidence. It also states
**what would change the recommendation**: the smallest input change that flips the leading outcome
(e.g. "targeted extraction would apply if shared tables fell below 30%").

---

## 2. Operating-model fit

- **Descriptive, retrospective scenario items** ("think of the last time…", with a "has not happened" option)
  on two axes: *domain ownership* and *distributed operations*, plus facts (module ownership, domain map).
  Scores express fit with domain-owned, distributed working — not maturity; a central SRE team or one
  company-wide definition is a legitimate choice.
- Business **consistency tolerance** is measured as a requirement, not as mindset.
- **Fit, not maturity:** each outcome has minimum mindset requirements (modular monolith: high domain thinking,
  low distributed operations; broad decomposition: both high). The report shows fit per outcome.
- **Cross-group gaps** are findings ("Leadership expects autonomy; scenario answers show decisions go to the board").
- **Free-text codebook** gains a "mental model" code (centralised ↔ domain-owned).

## 3. Stakes, preference and personal interests

- **Items** (asked *after* the substantive questions, stakes on a separate skippable page): preferred path per
  decision (plain-language options generated from the current state) + confidence; effect of **each** option on
  the respondent's role and on their skills (so stake and preference are measured independently); a gently worded,
  non-reversed concern item with a projective companion; "what evidence would change your preferred direction?"
  as a pre-commitment compared with the evidence afterwards.
- **Analysis (group level only, n ≥ 5):** preference distribution per group; association between preference and
  personal stake (within-group rank correlation, ordinal model controlling for group); **preference vs evidence**;
  within-leadership disagreement; the "watermelon" pattern (leadership optimistic, engineering pessimistic).
- **Tone:** neutral and descriptive, never accusatory.
- **Ethics & privacy:** anonymous, optional collection; where works councils exist (e.g. Germany, Austria),
  attitude surveys may require consultation — ship a participant-information and data-protection template.

## 4. Hosting economics

Transparent cost model (`mra/tco.py`): **5-year net present value** with residual hardware value (3 and 7 years
as sensitivity), per option — stay, improve/right-size (or optimise the cloud), hybrid, cloud, repatriate. About
40 inputs as low/likely/high with a source grade that sets a minimum range width; cloud and on-premises sizing
generated from monitoring data, commitments applied to baseline load only, PERT sampling with common random
numbers across options, migration and dual-run overruns correlated. One **symmetric switching rule** applies to a
move in either direction (ratio ≤ 1.0, plus a premium leadership pre-registers for a named need). Output: ratio,
payback and saving in FTE per option, tornado chart and break-even values. If load is flat and one machine
suffices, the model shows it plainly.

## 5. Instrument

- **Item bank** `instrument/items.csv`: id, block, decision, area, text, format, options, option scores,
  don't-know, reverse-keyed, scored, roles, core, gate, source.
- **Size:** ~40 items per respondent (~15 min). Core items per area asked of all groups; small role modules
  (Ops/SRE, Security/Compliance, Finance; Leadership split into technology and business executives).
  Seniority recorded so middle management can be analysed.
- **Fact sheet** `instrument/facts.csv` + `Responses/facts.yaml` per system, each value with source, date and
  range; mostly from git, CI/CD, incident and cost data. Helper for git change coupling via CODEOWNERS.
- **Content:** draft from the expert proposals plus mindset, stakes and hosting items; independent expert
  re-review for neutral wording; cognitive pretest with 3–5 people before use.
- **Collection:** form-export CSVs; Apps Script generator builds the Google Form from the item bank.
- **v2 data** converted to the item format and analysed as readiness only.

## 6. Report v3

Executive summary per decision: **recommended path** with probability and evidence strength; **gate checklist**
(pass / fail / unresolved, with owners); **what would change this**; 3–5 named blockers. New exhibits:
Need × Capability map (bootstrap cloud over outcome regions), outcome probabilities, mindset fit per outcome,
evidence-vs-perception gaps, hosting TCO comparison, aggregated preferences and stakes. Recommendations come
from a library keyed on outcome plus failing items. v2 readiness chapters move behind the decision chapters as
supporting evidence.

## 7. Validation & calibration

- **Simulator** with ground-truth scenarios (fact sheet + survey + free text): healthy monolith with few teams
  → stay; **bare metal, single machine suffices, team against, leadership pro-cloud → stay / improve current
  infrastructure, stakes flagged**; many coupled teams with strong platform → broad decomposition; single hotspot
  → targeted extraction; good tooling but centralised mindset → modular monolith first; over-split microservices
  with small team → consolidate; no sponsor → gate fail; polarised leadership.
- **Grid:** scenarios × group sizes (5 / 10 / 15 / 30) × noise levels.
- **Targets:** ≥ 90% correct outcome at ≥ 15 per group; at small n "insufficient evidence" rather than a wrong
  outcome (wrong-outcome rate ≤ 5%).
- **Calibration** only against the simulator and documented sources, never against a client's data. CI runs a
  reduced grid on every change.

## 8. Code structure

| Module | Responsibility |
|---|---|
| `mra/instrument.py` | Item-bank schema & validation, answer→score maps, reverse keying, scenario scoring |
| `mra/facts.py` | Fact sheet loading, banding to 1–5, value ranges |
| `mra/axes.py` | N / C sub-areas / L per decision; combines evidence and perception; joint bootstrap |
| `mra/gates.py` | Gate evaluation incl. "unresolved" (don't-know rate or disagreement) |
| `mra/decision.py` | Rule engine over draws → outcome probabilities, explanations, flip analysis |
| `mra/stakes.py` | Preference, stake, motivated-reasoning and watermelon diagnostics |
| `mra/tco.py` | Hosting TCO with Monte Carlo ranges |
| `mra/recommendations.py` + `recommendations.yaml` | Outcome- and item-driven action library |
| `sim/` | Scenario simulator and validation grid |
| `tools/forms.gs`, `tools/git_coupling.py` | Form generator, change-coupling extractor |

## 9. Milestones

| # | Milestone | Deliverable | Owner input |
|---|---|---|---|
| **M0** | Design freeze | Item bank, fact-sheet spec, governance checklist, `decision_rules.yaml`, outcome definitions, participant pack; two rounds of independent expert review | Approve; recruit 3–5 pretest participants (incl. one BUS, one FIN, one OPS) |
| **M1** | Instrument & data layer | Schemas, loaders, v2 converter, fact sheet, clear validation errors | – |
| **M2** | Architecture decision | Axes, gates, rule engine, probabilities, flip analysis; tests | Review outcome wording |
| **M3** | Hosting decision | TCO model, hosting axes and rules | Sanity-check cost assumptions |
| **M4** | Mindset & stakes | Scenario scoring, stakes diagnostics, extended codebook | Review reporting tone |
| **M5** | Simulator & calibration | Scenario grid, confusion matrix, calibrated thresholds, CI job | Set accuracy targets |
| **M6** | Report v3 & notebook | New executive summary, exhibits, recommendation library, notebook sections | Visual review |
| **M7** | Pilot | Pretest, one real or friendly organisation, form generator, participant/privacy pack | Run it |

M1–M2 are built first and reviewed before hosting and stakes are layered on.
