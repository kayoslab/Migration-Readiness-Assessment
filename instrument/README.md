# Instrument v3 (draft v0.3 — M0)

The v3 instrument decides **which path** fits an organisation, per decision (architecture, hosting), instead of
scoring readiness for a path chosen in advance. See [`docs/phase-2-plan.md`](../docs/phase-2-plan.md).

| File | Contents | Completed by |
|---|---|---|
| `items.csv` | Stakeholder survey (perception, experience, preference, stakes) | All invited groups |
| `facts.csv` | Fact sheet: metrics, categories and cost inputs | One accountable lead per system (not the sponsor), scripted where possible, second attester otherwise |
| `governance.csv` | Gate checklist, each answer backed by evidence | Sponsor, Finance, technology lead, risk & compliance — after the verdict, for the leading outcome |
| `decision_rules.yaml` | Semantics, thresholds, hard stops, gates, outcome rules, TCO model — **pre-registered** | Agreed and signed off by stakeholders before results |
| `outcomes.yaml` | Plain-language outcome definitions and preference labels | – |
| `participant-information.md` | Cover screen, participant information, data protection, form settings, invitation | Analyst, reviewed by DPO / works council |

## How the pieces fit

```
facts.csv ──(weight 2)──┐
                        ├─► sub-area scores ─► axes (need, capability, locality, fit, economics)
items.csv ──(weight 1)──┘        │                         │
   │                             └─ divergence findings    ▼
   │                                          outcome rules (decision_rules.yaml), per bootstrap draw
   │                                                       │
   │                                     hard stops (facts) / required capability → "prepare first"
   │                                                       ▼
   │                                     leading outcome + probability, "what would change this"
   │                                                       │
   │                         governance.csv (attested) ─► gates for that outcome → "prepare first" or go
   └─► preference & stakes (never decisive; reported at group level, n ≥ 5)
```

## Stakeholder groups

| Code | Group |
|---|---|
| ENG | Engineering (incl. engineering managers) |
| PRD | Product |
| BUS | Business stakeholders |
| TEC | Technology leadership (CTO, VP/Head of Engineering, chief architect) |
| EXE | Business leadership (CEO, COO, business unit heads) |
| OPS | Operations / SRE / infrastructure |
| SEC | Security, risk and compliance |
| FIN | Finance / controlling |

Items per group: ENG 40 · TEC 35 · OPS 34 · PRD 28 · BUS 20 · FIN 20 · EXE 19 · SEC 17 (≈ 10–15 minutes; to be timed in the pretest).

## `items.csv`

| Column | Meaning |
|---|---|
| `id` | `CX` context · `AN`/`HN` need · `AL` locality · `AC`/`HC` capability · `MD`/`MO` operating-model fit · `RQ` business requirement · `G` governance awareness · `AA` alignment · `S` preference & stakes |
| `page` | 1 context · 2 experience · 3 governance & alignment · 4 preference · 5 how options affect you (skippable) · 6 open questions |
| `block` | `context`, `need`, `locality`, `capability`, `fit`, `requirement`, `governance`, `alignment`, `risk`, `stakes` |
| `decision` / `area` | Which decision and sub-area the item feeds |
| `format` | `choice`, `frequency`, `yesno`, `scenario`, `likert5`, `grid`, `text` |
| `rows` | Grid rows (pipe-separated); `@preference:<decision>` expands to that decision's options |
| `options` / `scores` | Pipe-separated, aligned; `count:` maps the number of "Yes" rows in a grid to 1–5; `@preference:` as above |
| `dont_know` / `not_applicable` | "Don't know" offered; label of a "not applicable" option. Both are recorded, never scored |
| `scored` | Feeds an axis. Context, risk, preference and stakes items never do |
| `roles` / `core` | Groups asked. Every item referenced by a rule, gate or signal must be core |
| `source` | Origin and purpose ("Perception check for …" = compared against a fact) |

**Design rules** (from the methodology review):
- `{system}` names the system in scope; no item refers to "the proposed change". The cover screen states that no
  option has been chosen and keeping the current setup is one of them.
- Operating-model fit items are **descriptive and retrospective** ("think of the last time…"), with a "has not
  happened" option. Scores reflect fit with domain-owned, distributed working — not quality. A central SRE team or a
  single company-wide definition is a legitimate choice and is scored accordingly.
- Business consistency tolerance (`RQ01`) is a requirement, not a mindset.
- Preference is asked **after** the substantive items; stakes are measured **per option**, not only for the
  preferred one, so that stake and preference are independent measurements.
- Facts beat opinions: technical facts (rollback time, deploy automation, shared tables…) live in the fact sheet;
  the survey keeps perception checks whose divergence from the fact is itself a finding.

## `facts.csv`

| Column | Meaning |
|---|---|
| `axis` / `area` | `need`, `capability`, `locality`, `fit`, `distribution`, `economics`, `context`, `gate` |
| `kind` | `number` or `category` (with `categories` and `category_scores`) |
| `direction` / `cuts` | `up`: larger values → higher band; `down`: smaller → higher; four cut points → bands 1–5 (see `semantics.bands`) |
| `range` | Accepts low / likely / high; sampled in the bootstrap (PERT) |
| `required` | `true`, `false`, `if_distributed`, `if_cloud` |
| `band_source` | Source of the cuts; "calibrate in M5" marks provisional values |

Each value in `facts.yaml` (format: `mra/engagement.py`) carries its source, date, attester and — for economic
inputs — a source grade (invoice · quote · calculator export · benchmark · estimate) that sets a minimum range width.

## `governance.csv`

Answers are **Yes** (with an evidence reference) = pass, **Partly** = unresolved, **No** = fail. Gates are checked
for the leading outcome after the verdict, because funding or a sponsor for one path says nothing about another.
Survey items marked "Corroborates" measure awareness; disagreement with the attestation is reported.

Run `mra validate` after any change: it cross-checks every reference and enforces that anything a rule depends on is a core item.
