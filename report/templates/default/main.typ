#import "template.typ": *

#let data = json(sys.inputs.data)
#let e = data.engagement
#let verdict = data.verdict
#let r = data.rules

// number formatting
#let fmt(x, d: 1) = {
  if x == none { return "–" }
  let s = str(calc.round(float(x), digits: d))
  if d == 0 { return s }
  let parts = s.split(".")
  let frac = if parts.len() > 1 { parts.at(1) } else { "" }
  parts.at(0) + "." + frac + "0" * (d - frac.len())
}
#let pct(x) = if x == none { "–" } else { str(int(calc.round(float(x) * 100))) + "%" }
#let join(items) = items.join(", ", last: " and ")

#show: mra-report.with(engagement: e)

#page(header: none)[
  #v(12mm)
  #text(size: 20pt, weight: "regular", fill: theme.primary)[Contents]
  #v(8mm)
  #outline(title: none, depth: 1, indent: 0pt)
]

= Executive summary

#grid(columns: (1.15fr, 1fr), column-gutter: 18pt,
  [
    #eyebrow[Overall assessment]
    #v(2pt)
    #text(size: 24pt, weight: "light", fill: theme.tone.at(verdict.tone), verdict.decision)
    #v(-4pt)
    #text(size: 8.5pt, fill: theme.muted)[Evidence base: #verdict.evidence]
    #v(4pt)
    #set text(size: 8.5pt)
    #for reason in verdict.reasons [- #reason \ ]
  ],
  grid(columns: (1fr, 1fr, 1fr), column-gutter: 8pt,
    kpi(str(data.respondents_total), "respondents"),
    ..("RED", "GREEN").map(s => {
      let n = data.domains.filter(d => d.status == s).len()
      kpi(str(n), (if n == 1 { "domain " } else { "domains " }) + lower(s), color: theme.status.at(s))
    }),
  ),
)

#v(6mm)
#callout(title: "Key messages")[
  #for m in data.key_messages [- #m \ ]
]

== Readiness at a glance

#data-table(
  columns: (2.4fr, 0.8fr, 1.2fr, 1.2fr, 1.6fr),
  align: (left, right, center, left, left),
  header: ("Domain", "Index", "95% range", "Status", "Lowest-scoring group"),
  ..data.domains.map(d => (
    d.name,
    strong(fmt(d.index, d: 2)),
    text(fill: theme.muted, fmt(d.ci_low) + "–" + fmt(d.ci_high)),
    status-badge(d.status, uncertain: d.uncertain),
    if d.min_role == none [–] else [#d.min_role (#fmt(d.min_role_score))],
  )).flatten(),
)
#v(2pt)
#text(size: 7.5pt, fill: theme.muted)[
  Index = mean of stakeholder-group scores, each group weighted equally regardless of headcount.
  RED below #fmt(r.red_below), GREEN from #fmt(r.green_from). A status is marked uncertain when
  the bootstrap places less than #pct(r.confidence) probability on it.
]

= Readiness by domain

The chart below shows, for each of the six readiness domains, the role-weighted index and the range
within which it would fall with 95% probability had a different sample of the same stakeholder groups
responded. Where the range crosses a threshold, the status should be read as provisional.

#v(4mm)
#figure-block(data.charts.domain_index,
  caption: "Exhibit 1 — Readiness index by domain",
  source: "Source: stakeholder survey; stratified bootstrap (" + str(r.bootstrap_iterations) + " resamples).")

#v(4mm)
#data-table(
  columns: (2.2fr, 2.4fr, 1.6fr, 1fr),
  align: (left, left, left, right),
  header: ("Domain", "Groups contributing", "Not counted", "Alpha"),
  ..data.domains.map(d => (
    d.name,
    join(d.roles_scored),
    if d.roles_not_scored.len() == 0 [–] else { text(fill: theme.muted, join(d.roles_not_scored)) },
    if d.alpha == none [–] else if d.reliable { fmt(d.alpha, d: 2) } else { text(fill: theme.status.RED, fmt(d.alpha, d: 2) + " (low)") },
  )).flatten(),
)
#v(2pt)
#text(size: 7.5pt, fill: theme.muted)[
  A group is counted in a domain when at least #r.min_role_n of its members answered at least
  #r.min_role_items statements in that domain. Reliability (Cronbach's α, median across groups) below
  #fmt(r.min_reliability, d: 2) indicates that the statements do not measure a single coherent construct.
]

= Stakeholder perspectives

Migration programmes rarely fail for technical reasons alone; misaligned expectations between
stakeholder groups are a leading cause. Exhibit 2 compares how each group assesses each domain.

#v(4mm)
#figure-block(data.charts.role_heatmap,
  caption: "Exhibit 2 — Domain scores by stakeholder group",
  source: "Hatched cells are shown for context but are not counted: too few respondents or statements.")

#v(4mm)
== Where perceptions diverge

#if data.role_differences.len() == 0 [
  Too few groups contributed to any domain to compare perspectives.
] else [
  #data-table(
    columns: (2.2fr, 1.5fr, 1.5fr, 0.8fr, 1fr),
    align: (left, left, left, right, left),
    header: ("Domain", "Most positive", "Most negative", "Spread", "Difference"),
    ..data.role_differences.sorted(key: d => -d.spread).map(d => (
      d.domain,
      [#d.high_role (#fmt(d.high))],
      [#d.low_role (#fmt(d.low))],
      fmt(d.spread),
      if d.significant { strong(d.effect) } else { text(fill: theme.muted, d.effect + ", not significant") },
    )).flatten(),
  )
  #v(2pt)
  #text(size: 7.5pt, fill: theme.muted)[
    Difference: Kruskal–Wallis test across groups, effect size ε², significance after false-discovery-rate
    adjustment (q < 0.05).
  ]
]

#v(2mm)
#if data.gaps.len() > 0 [
  At statement level, #data.gaps.len() of #data.gaps_tested statements answered by several groups show
  a difference unlikely to be due to chance:
  #data-table(
    columns: (3.4fr, 0.7fr, 1.4fr, 1.4fr),
    align: (left, right, left, left),
    header: ("Statement", "Gap", "Higher", "Lower"),
    ..data.gaps.map(g => (g.question, fmt(g.gap), g.high_role, g.low_role)).flatten(),
  )
] else [
  At statement level, none of the #data.gaps_tested statements answered by several groups shows a
  difference between groups that is distinguishable from chance at the current sample size.
  Domain-level comparisons above are therefore the more reliable guide.
]

= Areas of concern

Exhibit 3 shows the ten statements with the lowest role-weighted scores and how responses were
distributed. These are the most specific starting points for remediation.

#v(4mm)
#figure-block(data.charts.likert,
  caption: "Exhibit 3 — Lowest-scoring statements",
  source: "Bars show the share of respondents per answer; neutral answers are split either side of zero.")

#if data.critical_red.len() > 0 [
  == Critical statements below threshold
  #block(sticky: true)[The following statements were designated critical in the questionnaire and score below #fmt(r.red_below):]
  #data-table(
    columns: (0.5fr, 4fr, 2fr, 0.7fr),
    align: (left, left, left, right),
    header: ("ID", "Statement", "Domain", "Score"),
    ..data.critical_red.map(c => (str(c.id), c.question, c.domain, strong(fmt(c.score, d: 2)))).flatten(),
  )
]

= Qualitative insights

#if data.text == none [
  Free-text responses were not analysed for this report. Enable the optional language-model analysis
  (`mra report --llm`) to code every answer for sentiment, stance on change, themes and underlying
  motives, and to summarise the findings by stakeholder group.
] else [
  #let t = data.text
  This section summarises what stakeholders said in their own words: how they describe the current
  situation, where they stand on the proposed change, and which concerns recur within each group.

  #v(3mm)
  #callout(title: "Qualitative key messages")[
    #for m in t.key_messages [- #m \ ]
  ]

  #v(4mm)
  #figure-block(data.charts.stance, caption: "Exhibit 4 — Stance on change by stakeholder group",
    source: "Share of coded answers. Stance as expressed in the answer, not inferred.")
  #v(4mm)
  #figure-block(data.charts.themes, caption: "Exhibit 5 — Most frequent themes by stakeholder group",
    source: "Share of each group's answers that mention the theme, so that larger groups do not dominate.")

  #for th in t.themes [
    == #th.theme
    #th.finding
    #for q in th.quotes [
      #block(inset: (left: 12pt, y: 4pt), stroke: (left: 1.5pt + theme.rule))[
        #text(style: "italic")[“#q.text”] #h(4pt) #text(size: 8pt, fill: theme.muted)[— #q.role]
      ]
    ]
  ]
]

= Recommended next steps

#for (i, s) in data.next_steps.enumerate() [
  #grid(columns: (12mm, 1fr),
    text(size: 16pt, weight: "light", fill: theme.accent, numbering("01", i + 1)),
    [#text(weight: "semibold", fill: theme.primary, s.title) \ #s.body],
  )
  #v(3mm)
]

#counter(heading).update(0)
#set heading(numbering: "A.1")

= Methodology and decision rules

== Approach
Respondents rated statements on a five-point scale (1 = strongly disagree, 5 = strongly agree). Each
statement was addressed only to the stakeholder groups able to judge it. Missing answers and
"don't know" responses are excluded rather than scored (#pct(data.missing_rate) of applicable
statements were left unanswered, #pct(data.dont_know_rate) answered "don't know").

+ *Person score:* the mean of a respondent's answers within a domain, provided at least
  #pct(r.min_item_coverage) of the statements addressed to them were answered.
+ *Group score:* the mean of person scores within a stakeholder group.
+ *Domain index:* the mean of group scores, with each group weighted equally (or as agreed), so that
  larger groups do not dominate.
+ *Uncertainty:* respondents are resampled within each group #r.bootstrap_iterations times; ranges and
  probabilities are derived from the resampled indices.
#if data.text != none [
+ *Free-text answers:* each of the #data.text.answers answers was coded against a fixed codebook
  (sentiment, stance on the change, themes, motives). Groups are compared by the share of their
  answers, not by volume. Quotations are verbatim.
]

== Decision rules
#data-table(
  columns: (3fr, 2fr),
  header: ("Rule", "Setting"),
  [Status thresholds], [RED < #fmt(r.red_below) ≤ AMBER < #fmt(r.green_from) ≤ GREEN],
  [Proceed], [every domain ≥ #fmt(r.proceed_from) with ≥ #pct(r.confidence) probability; no group RED on any domain],
  [Not ready], [any domain RED with ≥ #pct(r.confidence) probability, or any essential group RED on #join(r.role_veto_domains)],
  [Minimum respondents per group], [#r.min_role_n to be scored; #r.strong_evidence_role_n for a strong evidence base],
  [Essential groups], [#join(r.essential_roles)],
  [Decision rules agreed by], [#if r.signed_off_by == none { text(fill: theme.status.RED)[not recorded] } else { r.signed_off_by }],
)

== Limitations
- The assessment measures perceived readiness to execute a change; it does not establish whether the
  change is warranted. Objective delivery and cost metrics should be considered alongside it.
- Survey responses are subject to social desirability and acquiescence effects, particularly in small
  groups where anonymity is limited.
- Findings for groups below #r.strong_evidence_role_n respondents are indicative.

= Respondents and themes

== Participation
#data-table(
  columns: (2fr, 1fr, 1fr, 1.5fr),
  align: (left, right, right, left),
  header: ("Stakeholder group", "Respondents", "Weight", "Evidence"),
  ..data.respondents.map(p => (p.role, str(p.n), fmt(p.weight), p.evidence)).flatten(),
)

== Cross-cutting themes
#data-table(
  columns: (2.6fr, 0.8fr, 1.2fr, 2.4fr),
  align: (left, right, left, left),
  header: ("Theme", "Index", "Status", "Groups contributing"),
  ..data.themes.map(t => (t.name, fmt(t.index, d: 2), status-badge(t.status, uncertain: t.uncertain), join(t.roles_scored))).flatten(),
)
