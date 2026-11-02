# Question review: are we asking the right questions to the right people?

Status: proposal, 2026-11-02. Nothing in `instrument/` has been changed yet.

## How this was reviewed

There was one reviewer per respondent group, each briefed as a practitioner from that group's side of a migration:

| Group | Reviewer's background |
|---|---|
| ENG | Staff engineer / engineering manager |
| PRD | Head of product |
| BUS | Business change lead |
| TEC | CTO / chief architect |
| EXE | COO and programme sponsor |
| OPS | Head of infrastructure / SRE |
| SEC | CISO in a regulated sector |
| FIN | IT controller |

The review ran in two rounds:

- **Round 1.** Each reviewer judged their group's questionnaire item by item: keep, reword, drop or reroute. They also said what is missing, what the group cannot know or would answer strategically, and how long the survey takes.
- **Round 2.** All reviewers read the consolidated findings. They resolved routing conflicts, merged duplicate proposals and committed to a final list per group within a time budget.

Where the reviewers still disagreed after round 2, the decision taken here is marked **(decided)**.

Three defects in today's instrument were confirmed against the repository:

1. **Self-rated gates.**
   - The repatriate and hybrid gates rest on `capability.hosting.onprem_ops`. That is HC05 alone, which Operations rates about itself, with no fact behind it.
   - The cloud gate rests on `capability.hosting.cloud_skills` (HC02, Operations and Technology leadership, no fact).
   - `architecture/skills` (AC12, Technology leadership only) has no fact either.
2. **HN05 measures something else than its fact.** HN05 asks about product teams' time. The fact it checks, `infra_toil_pct`, measures platform hours spent on hardware.
3. **G14's threshold differs between files.** The item says 30%; the rule (`stop_criteria.mandatory_if`) uses 0.5.

## What the reviewers agreed on

1. **No group may decide a gate or score through its own self-rating, and no group checks a fact it supplied.**
   - Every survey input to a gate needs a fact behind it, with the survey answer as the perception check.
   - Facts produced by Operations are attested by the technology lead. Facts produced by the technology lead are attested by a second estimator.
   - Each fact records which group supplied it. That group's answer gets weight 0 when its perception check is compared with that fact.
2. **The tool asks too little about the cost of staying, and almost nothing about the cost of changing as the business experiences it.**
   - Both sides need to be measured, and with the same discipline.
   - Only facts and euros enter scoring, on both sides. Perception items about pain or tolerance are reported, never scored.
   - Adding cost-of-staying items without their change-side mirror would only swap a lean toward the status quo for a lean toward migration.
3. **Nothing captures the forward view or what was already decided.** Missing today:
   - the future of the business area;
   - the system's expected life;
   - what the business can absorb;
   - whether a direction was announced before the assessment.
4. **Small groups need one policy.** Technology leadership, Executives, Security and Finance, and often Operations, are usually under 5 people. Today their cells are suppressed, yet a group of 2 counts as much as 40 engineers.
5. **Non-technical groups are asked technical preferences they cannot judge.** The board would then read "Business favours cloud" as business demand.
6. **Burden is over budget.** Pretest Engineering took about 20 minutes against the 15 promised. Every addition must replace something.

## New governance artefacts

### Leadership intent sheet

**Who and when.** The sponsor fills the sheet, and Finance co-signs the money items. The technology lead is consulted but does not sign, because of their stake. It is filled after the decision rules are signed, and locked before the survey opens. Any later change is a dated amendment, and the report shows the result under both versions.

**Contents**, each with evidence:

| Item | Content |
|---|---|
| Business horizon | Grow / hold / shrink / may be sold or closed. This caps the payback period and the cost-comparison horizon. |
| Top three outcomes | Lower run cost, faster delivery, fewer outages, regulatory demands, scale or new markets, less dependence on key people or vendors, freeing money for other priorities. |
| Prior commitment | Any direction already announced, budgeted, contracted or started. Cross-checked against `sunk_commitment_cost`. |
| Competing priority | Where the system ranks against other initiatives next year. |
| Stop triggers | Feeds GV08 and is printed on the decision page. A trigger looser than the organisation's own track record is flagged as one that can never fire. |
| Funded months of running old and new in parallel | Finance co-signs. |
| Spending constraint | Capital capped, operating spend capped, both, or neither. Needs a board document and an expiry date. Reported as a financing constraint beside the cash comparison, never folded into it. |
| Budget lock date | |
| Dates already promised to customers or regulators | |
| Acceptable run-cost increase and accepted premium | Moved here from the fact sheet, because they are leadership choices, not measurements. |

**How the report uses it.**

- Hard constraints mark options as feasible or not, and say so openly.
- The top three outcomes never change scores or the probability. They are shown only as "best fit to stated priorities".
- Gaps between the sheet and the anonymous answers from Executives, Finance and Product are reported as findings.

### Risk and compliance sheet

One accountable risk lead fills this, in 30–45 minutes, before the verdict, because it feeds the need for change. GV09–GV11 and GV13 stay after the verdict as they are.

| Item | Content |
|---|---|
| RC1 | Critical or important function under DORA, or essential service under NIS2. This makes GV11 mandatory and sets the regulator-notification lead time. |
| RC2 | High-severity findings in the last 24 months from a regulator, audit or penetration test: the number raised and the number still open after 90 days. Finance co-sources it. |
| RC3 | Result of the last full disaster-recovery test: met the recovery targets / met with deviations / failed / partial scope / never tested. |
| RC4 | `hosting_constraint`, citing the external regulation or contract clause. |
| RC5 | Widened `stack_eol_months`: the earliest end of vendor support across framework, runtime, operating system, database and hardware. |
| RC6 | Median days from request to decision over the last five security or compliance reviews. This is the fact behind GV09. |
| RC7 | Compensating controls in place because the current setup cannot meet a requirement, with the list. |
| RC8 | Existing compliance-scope facts. |

## Survey: final routing

Legend: ● asked · ○ conditional (the condition is in the note) · blank = not asked.

| Item | ENG | PRD | BUS | TEC | EXE | OPS | SEC | FIN | Change |
|---|---|---|---|---|---|---|---|---|---|
| CX01 position | ● | ● | ● | ● | ● | ● | ● | ● | — |
| CX02 involvement | ● | ● | ● | ● | ● | ● | ● | ● | New option "My work depends on what it produces, but I rarely use it myself", weighted like weekly |
| AN01 lead-time driver | ● | | | | | ● | | | TEC dropped (sees a dashboard, not the queue) |
| AN02 release delays | ● | | | | | | | | — |
| AN03 teams per feature | ● | ● | | | | | | | TEC dropped (supplies the fact) |
| AN05 distinct parts | ● | ○ | | | | ● | | | Reworded to events in the last 12 months. Rows: load → ENG, OPS; availability → OPS, PRD; release timing → ENG. Compliance row removed; the fact decides it |
| AN06 roadmap delay | | ● | | | | | | | PRD wording: "items you owned … the reason stated at the time". Scored only when the `roadmap_slip_system_pct` fact exists; otherwise perception only |
| AN06B requests refused (new) | | | ● | | ● | | | | Perception check for AN06. EXE stem: "initiatives in your area held back" |
| AN09 confident change | ● | | | | | | | | — |
| AL01 friction concentration | ● | | | | | | | | PRD and TEC dropped |
| AL02 friction areas (text) | ○ | | | ● | | | | | Optional for ENG |
| AC01 one-line change | ● | | | | | | | | — |
| AC02 deploy method | ● | | | | | | | | OPS dropped |
| AC04 rollback | ○ | | | | | ● | | | ENG only when AC06 = owning team **(decided)** |
| AC05 platform basics | ● | | | | | ● | | | — |
| AC06 first call | ● | | | | | ● | | | — |
| AC08 data access | ● | | | | | | | | — |
| AC10 module boundaries | ● | | | ● | | | | | TEC added |
| AC12 distributed experience | ○ | | | | | ● | | | Perception only (fact decides). ENG: managers only. TEC dropped |
| AC13 key people | ● | | | ● | | | | | ENG added (the gap is a finding) |
| AC14 platform for distribution | ○ | | | | | ○ | | | Only when broad decomposition is on offer |
| MD01 shared data | ● | | | | | | | | PRD and TEC dropped |
| MD02 business terms | | ● | ● | ● | | | | | ENG dropped |
| MD03 data structure change | ● | | | ● | | | | | — |
| MD04 joint workshop | | ● | ● | | | | | | BUS added, TEC dropped |
| MD06 cross-part feature | ● | ● | | | | | | | TEC dropped |
| MD07 team funding | | ● | | ● | | | | | Perception check for the new fact `team_funding_model` (Finance) |
| MO02 degraded feature: practice | | | | | | ● | | | Scores operating-model fit |
| MO02T degraded feature: tolerance (new) | | ● | ● | | | | | | "How soon would your area need it back?" Feeds context only, never fit |
| MO04 new technology | ● | | | ● | | | | | — |
| RQ01 consistency | | ● | ● | | | | | | Reworded as a consequence ("would that cause a real problem?") and reverse-scored. EXE dropped |
| HN01 load variation | | | | | | ● | | | — |
| HN02 capacity lead time | | | | | | ● | | | — |
| HN04 business need: edge, ML | | ● | | ● | ● | | | | Split. Perception check for `managed_services_required` and `regions_required` |
| HN04S need: scale we could not run (row) | | | | ● | | ● | | | Perception only; the fact gates repatriation |
| HN04O observed limit (new) | ● | | | | | | | | "Hit a limit of a database, queue or ML capability we could not resolve?" |
| HN05a platform hardware time | | | | | | ● | | | Reworded to match `infra_toil_pct` |
| HN05b product-team infra time (new) | ● | | | | | | | | — |
| HC01 infrastructure as code | | | | | | ● | | | ENG dropped (duplicates the AC05 row) |
| HC02 cloud skills | | | | | | ● | | | Perception only (fact decides). TEC dropped |
| HC03 cost attribution | | | | | | | | | Removed; the fact `cost_allocation_method` decides |
| HC04 infra-caused outages | | | | | | ● | | | Reworded to "caused mainly by infrastructure". Fact `infra_caused_incidents_6m`, attested by TEC |
| HC05 hardware skills | | | | | | ● | | | Perception only (fact decides). Scope widened to "teams running {system}" |
| HC06 runbook restore | | | | | | ● | | | New option "Runbooks exist but have not been used by anyone outside the team" |
| G04 reserved capacity | ● | ● | | ● | ● | | | | EXE added |
| G05 improvement protected | ● | ● | | ● | | | | | TEC added. Reported as a gap between groups |
| G10 other changes | ○ | ● | ● | ● | ● | ○ | ● | ● | ENG and OPS: managers only. Examples widened (regulatory change, peak season) |
| G14 past overrun | ● | ● | ● | ● | ● | ● | ● | ● | Threshold fixed (see rules) |
| G16 named executive | | ● | | ● | ● | | | ● | FIN stem: "holds both the budget and the decisions". Supporting evidence for GV01 only |
| AA01 leaders understand | ● | ● | ● | ● | ● | ● | | | SEC and FIN dropped |
| AA02 shared future | | ● | ● | ● | | ● | ● | ● | ENG and EXE dropped |
| AA03 reasons explained | ● | ● | ● | | ○ | ● | ● | ● | TEC dropped. EXE: N/A option "I commissioned the review" |
| AA04 manager protected time | | | | | | | | | Removed (G05 covers it) |
| SO01 differentiation | | ● | ● | ● | ● | | | | Anchored to customer behaviour; at most two parts rated "Considerably" or above; business names for parts; "I don't know this part" option; no group weighting |
| SO02 change per part (new) | | ● | | ● | | | | | Second column of the SO01 grid |
| SO03 adopt the product's process (new) | | ● | ● | | | | | | Only for parts with a buy option. Includes "No, our process is required by law or contract" |
| SO04 part confidence (new) | ● | | | | | | | | "Could your team change this part confidently today?" |
| S01 architecture preference | ● | ● | | ● | ● | ● | ● | | BUS and FIN dropped |
| S02 hosting preference | ● | ● | | ● | ● | ● | ● | ● | BUS dropped |
| BP01 stability vs faster change (new) | | | ● | | | | | | Replaces S01/S02 for BUS. Preference only |
| BP02 already told a direction (new) | ● | ● | ● | | | ● | ● | | Lobbying signal |
| PC01 prior commitment (new) | | | | ● | ● | | | ● | Survey version. The signed version is on the intent sheet |
| S03 confidence | ● | ● | | ● | ● | ● | ● | ○ | FIN: hosting row only |
| S04 role impact | ● | ● | | ● | ● | ● | ● | ● | EXE stem: "budget, headcount or decision rights of your area" |
| S05 career skills | ● | | | ● | | ● | | | Only these three groups |
| S06 concern | ● | ● | ● | | | ● | | ● | TEC and SEC dropped |
| S06P concern (projective) | ● | ● | ● | | | ● | | | — |
| S08 evidence that would change view | ● | ● | | ● | ● | ○ | ● | ● | Optional for OPS |
| S09 if nothing changed | ● | ● | ● | ● | ● | ● | ● | ● | BUS stem: "for your area or your customers" |
| S10 anything else | ○ | ○ | ○ | ○ | | ○ | | ○ | Optional and last. Merged into S09 for EXE and SEC |
| X1 business horizon (new) | | ● | | | ● | | | | — |
| LF01 system lifetime (new) | | | | ● | ● | | | | EXE sees X1 and LF01 as one two-row grid |
| X2 top three outcomes (new) | | | | | ● | | | | Never scored |
| ABS absorption (new) | | ● | ● | | ● | | | | Two rows: months of slower new delivery, months of higher outage risk. Options: none / up to 1 month / 1–3 / 3–6 / 6–12 / longer. Reported against the duration facts. A risk, never a gate |
| BI01 outage impact (new) | | | ● | | | | | | — |
| BI02 workarounds and data trust (new) | | ● | ● | | | | | | Perception check for the new data-quality fact |
| TT01 test safety net trust (new) | ● | | | | | | | | — |
| TT02 local end-to-end loop (new) | ● | | | | | | | | — |
| CAP01 capacity you could release (new) | ○ | | | | | ○ | | | Managers only |
| HR01 hiring and retention (new) | ○ | | | ● | | ○ | | | ENG/OPS: team lead and above. Perception check for a fact |
| OP-A on-call load (new) | ○ | | | | | ● | | | ENG: only those on call |
| OP-C last capacity crunch (new) | | | | | | ● | | | — |
| OP-D disaster-recovery confidence (new) | | | | | | ● | | | Perception check for RC3. TEC and SEC excluded **(decided)** |
| CX03 withdrawal word | ● | ● | ● | ● | ● | ● | ● | ● | — |

Proposed or discussed, not adopted:

- OP-B alert quality: rotated out because of burden.
- A security review-time survey item: replaced by the RC6 fact.
- Separate regulator-raised survey items: merged into RC2.
- Identity integration as a security fact: left to the technology lead as an effort input, if it is wanted.

### Estimated time per group (reviewers' estimates)

| Group | Today | Proposed | Notes |
|---|---|---|---|
| ENG | about 20 min, measured in the pretest | about 15 min | +1 min for managers who are on call |
| PRD | 16–19 | 15–16 | Cut S06P or AA02 first if over |
| BUS | 13–16 | about 12 | Fewer technical items, more about what the business carries |
| TEC | 20–25 | 13–15 | — |
| EXE | 13–16 | about 10.5 | — |
| OPS | 17–20 | 13.5–14 | about 16 with the optional items |
| SEC | 6–7 | about 4 | Plus the risk sheet (30–45 min, one person) |
| FIN | 9–11 | about 6 | Fact sheet effort unchanged; plus the intent-sheet session |

## Facts: additions and changes

| Fact | Supplied by / attested by | Purpose |
|---|---|---|
| `onprem_hw_ops_people` | Accountable lead / TEC. Counted from tickets for the last 36 months, excluding vendor break-fix | Gate for repatriate and hybrid (replaces HC05). Cuts `1|2|3|5`. `infra_bus_factor` cannot serve here: in a cloud organisation it counts cloud restores |
| `cloud_oncall_experienced_people` | Accountable lead / TEC, with HR confirming outside experience. Counts production on-call for public cloud in the last 36 months, any employer | Cloud gate (replaces HC02) |
| `distributed_ops_people` | OPS lead from the incident tool / analyst spot-check. Counts primary responders on multi-service incidents in the last 12 months | `architecture/skills` (replaces AC12) |
| `infra_caused_incidents_6m` | From post-incident review classification / TEC | Hosting operations (behind HC04) |
| `team_funding_model` | Finance | Replaces MD07 as evidence |
| `cost_allocation_method` | Finance | `hosting/cost_discipline` (replaces HC03) |
| `roadmap_slip_system_pct` | Product, from planning or retrospective records | Makes AN06 scorable |
| `past_savings_verified` | Finance, from programme records | "Not achieved" or "never checked" makes GV14 mandatory |
| `hard_to_fill_roles` (roles open for more than 90 days for the system's skills) | HR | Behind HR01 |
| `data_quality_remediation_effort` | Accountable lead with the business owner | Cost of change (data clean-up). BI02 checks it |
| `business_blackout_months`, `max_planned_outage_hours` | Signed by a named business process owner, citing the business calendar and customer SLAs | Cost of change: cut-over windows |
| `contract_end_months` (widened) | Finance | Now covers the longest infrastructure contract (colocation, licences, support, managed service). The early-exit fee goes into the bridge cost |
| `owned_asset_book_value` (optional) | Finance | Report only, never in the cost comparison (sunk cost) |
| RC1–RC8 | Risk lead (risk and compliance sheet) | See above |

## Rules and gates

- **G14.** Stop criteria become mandatory at 30% yes. The share is computed per reporting pool with n ≥ 5, and otherwise over all informed respondents, so one person in a group of two cannot trigger it. No group can lower it. Align `items.csv` and `decision_rules.yaml`.
- **Small groups.**
  - There are two reporting pools: technology leadership (TEC plus ENG/OPS respondents at "Head of" or "Executive" level) and leadership and control (EXE, FIN, SEC).
  - SEC is never pooled with OPS, and EXE never with TEC.
  - Role weight on scored items is min(n, 5)/5.
  - A pool still under 5 shows "not reported", and its free text appears only as analyst-paraphrased themes.
- **GV14 (new), savings realisation.**
  - Every saving in the recommended path has a budget owner and a year in which it leaves the budget, and released people have an agreed destination.
  - For cloud and hybrid, it adds: a named owner reviews the cloud bill monthly against the case.
  - Mandatory whenever the case relies on staff savings (`tco_saving_fte`), and that includes improve-current.
- **GV11 widened.** It also covers the current third-party provider for a critical or important function, and repatriation targets. Provider concentration becomes required evidence.
- **GV10.** Data classification becomes required evidence.
- **Hard stops** (`own_premises_only`, `product_compliance = no`) must cite the specific external requirement and be countersigned by legal. An internal policy is not enough.
- **"Required whichever path".** A failed or missing disaster-recovery test, or a critical function without a tested exit plan for the current provider, appears as a step the organisation must take whichever path it chooses, including staying.
- **Symmetry.**
  - Status-quo facts (RC1–RC3, RC5, RC7) raise the need for change.
  - Change-side facts (absorption against duration, blackout months, data clean-up, committed dates) enter feasibility in the same way.
  - Perception items on either side are reported, never scored.

## Order of work

1. **Defects first.** G14 threshold, HN05 wording, and gate facts for onprem_ops, cloud_skills and skills. This needs no new artefacts. **Done 2026-11-02:**
   - G14 reads its threshold (30%) from the rule; groups under 5 count only in the overall share.
   - HN05, HC02, HC05 and AC12 are reworded to the bands of their facts.
   - New facts `onprem_hw_ops_people`, `cloud_oncall_experienced_people` (both required) and `distributed_ops_people`, each with a second attester.
   - `evidence.fact_decides` covers onprem_ops, cloud_skills, architecture skills and managed services.
   - A role plan is now added whenever a named group expects the recommended path to harm its roles.
2. **Routing and wording** in `items.csv`, including conditional and row-level routing. That needs small extensions to the item format: per-row roles, conditions on CX01/AC06 answers and on the outcomes on offer. **Done 2026-11-02:**
   - The item format gained `role_text`, `row_roles` and `show_if`, all applied in the one form spec that both the forms and the analysis use.
   - The routing table above is applied to existing items: AN06B (counted, for Business and Executives) and MO02T (tolerance, never scored) split off.
   - AA04 is removed.
   - Conditions on a respondent's own answers are not possible in a generated Google Form without branching pages. AC04 and AC12 therefore carry a "not applicable" option instead ("Another team rolls releases back", "I am not a team lead or manager"), and G10 stays with everyone, with "Don't know".

   **Deferred**, because each needs a later step:
   - HC03 removal and MD07 for Finance wait for their facts (step 4).
   - AN06 scored only with its fact (step 4).
   - Business's S01/S02/S08 swap for BP01/BP02 (step 5).
   - The Executives' AA03 "I commissioned the review" option (needs per-group options; low value).

   MidCorp's need targets were set to 2.5 and 2.3 so that its expected need sits at the threshold, as the example intends. With the redrawn synthetic answers, the old targets landed above it by chance.
3. **Small-group policy**: pools and weights. **Done 2026-11-02:**
   - One grouping rule (`mra/groups.py`, pre-registered as `evidence.pools`) is used by scoring, the track-record rule, stakes, build or buy, the lead-time exhibit, the stakeholder map (a pool carries its members' highest influence) and the report's note on combined groups.
   - The proposed weight min(n, 5)/5 is not needed: a group or pool under five never counts, so every group that counts would get weight 1.
   - Consequence: a small Operations group (fewer than five) is no longer counted through "Other groups" alongside Security or Finance. It counts only with other small delivery groups, or not at all. The hosting gates no longer depend on its survey answers (step 1), but the report hears less from it. Worth confirming in the pilot.
4. **New facts and both sheets**, with their report use: the decision page, feasibility marks and "required whichever path".
5. **New survey items.** Then rerun the pretest timing, the calibration simulation and the three examples.
