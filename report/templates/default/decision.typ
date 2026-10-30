// v3 report: recommended path per decision. Branding lives in template.typ (shared with the v2 report).
#import "template.typ": *

#let data = json(sys.inputs.data)
#let e = data.engagement

#let fmt(x, d: 2) = {
  if x == none { return "–" }
  let s = str(calc.round(float(x), digits: d))
  let parts = s.split(".")
  let frac = if parts.len() > 1 { parts.at(1) } else { "" }
  if d == 0 { parts.at(0) } else { parts.at(0) + "." + frac + "0" * (d - frac.len()) }
}
#let pct(x) = if x == none { "–" } else { str(int(calc.round(float(x) * 100))) + "%" }
#let status-colour = (pass: theme.status.GREEN, unresolved: theme.status.AMBER, fail: theme.status.RED)
#let gate-badge(s) = {
  box(baseline: 0.12em, circle(radius: 0.28em, fill: status-colour.at(s)))
  h(0.35em)
  text(weight: "semibold", size: 8.5pt, upper(s))
}

#let uncertainty(dec) = if dec.uncertain.len() > 0 [
  == Where the evidence is uncertain
  #for u in dec.uncertain [
    - #u.text #if u.facts.len() > 0 [#text(fill: theme.muted)[Firm up: #u.facts.join("; ")#if u.items > 0 [; or more survey responses]].] \
  ]
]

#show: mra-report.with(engagement: e)

#page(header: none)[
  #v(12mm)
  #text(size: 20pt, weight: "regular", fill: theme.primary)[Contents]
  #v(8mm)
  #outline(title: none, depth: 1, indent: 0pt)
]

= Executive summary

#callout(title: "Key messages")[
  #for m in data.key_messages [- #m \ ]
]

#for dec in data.decisions [
  #v(6mm)
  #block(breakable: false, width: 100%)[
    #eyebrow[#dec.title · currently #dec.current]
    #v(2pt)
    #grid(columns: (1fr, auto), column-gutter: 12pt,
      [
        #par(leading: 0.35em, text(size: 17pt, weight: "light", fill: theme.primary, dec.verdict_label))
        #if dec.leaning_label != none [
          #v(-4pt) #text(size: 9pt, fill: theme.muted)[Leaning towards: #dec.leaning_label]
        ]
      ],
      align(right)[
        #text(size: 13pt, weight: "regular", fill: theme.tone.at(dec.tone), dec.status_label) \
        #text(size: 8pt, fill: theme.muted)[#pct(dec.probability) of draws · evidence #data.evidence_strength]
      ],
    )
    #v(2pt)
    #text(size: 9pt, dec.summary)
    #if dec.hard_stops.len() + dec.capabilities.len() + dec.gates.filter(g => g.status != "pass").len() > 0 [
      #v(3pt)
      #text(size: 8.5pt, weight: "semibold", fill: theme.primary)[Before committing:]
      #set text(size: 8.5pt)
      #for h in dec.hard_stops [- #h \ ]
      #for c in dec.capabilities [- Build: #c \ ]
      #for g in dec.gates.filter(g => g.status != "pass") [- #g.label (#if g.status == "fail" [not met] else [unresolved]) \ ]
      #if dec.interim_label != none [#text(fill: theme.muted)[Interim step: #dec.interim_label]]
    ]
  ]
]

= Architecture

#for dec in data.decisions.filter(d => d.id == "architecture") [
  #text(size: 10pt)[Current state: #dec.current. Recommended: *#dec.verdict_label* — #dec.status_label.]

  == Why this path
  #if dec.why.len() == 0 [No single path reaches the agreed confidence.] else [
    #for w in dec.why [- #w \ ]
  ]

  == What would change the recommendation
  #if dec.flips.len() == 0 [No single change to one input would switch the recommendation.] else [
    #for f in dec.flips [- #f \ ]
  ]
  #uncertainty(dec)

  #v(3mm)
  #figure-block(dec.charts.probabilities, caption: "Exhibit 1 — How often each path applies across bootstrap draws",
    source: "Respondents resampled within group; fact-sheet ranges sampled. The verdict requires " + pct(data.rules.confidence) + ".")
  #if "map" in dec.charts [
    #v(3mm)
    #figure-block(dec.charts.map, caption: "Exhibit 2 — Need for change against the weakest capability",
      source: "Each dot is one bootstrap draw; the large dot is the point estimate.")
  ]
  #if "fit" in dec and dec.fit.len() > 0 [
    == Operating-model fit
    Fit describes how current ways of working match what each path requires — not maturity.
    #data-table(
      columns: (2.2fr, 2.4fr, 0.8fr, 0.8fr, 0.6fr),
      align: (left, left, right, right, center),
      header: ("Path", "Requirement", "Needed", "Current", "Met"),
      ..dec.fit.map(f => (f.outcome, f.requirement, fmt(f.threshold, d: 1), fmt(f.current, d: 1),
        if f.met == none [–] else if f.met [✓] else [#text(fill: theme.status.RED)[✗]])).flatten(),
    )
  ]
  #if dec.shadow_label != none [
    #callout(title: "Shadow verdict")[Under the unmodified default rules the recommendation would be “#dec.shadow_label”.]
  ]
]

= Hosting

#for dec in data.decisions.filter(d => d.id == "hosting") [
  #text(size: 10pt)[Current state: #dec.current. Recommended: *#dec.verdict_label* — #dec.status_label.]

  == Why this path
  #if dec.why.len() == 0 [The current setup is kept because no alternative meets the agreed need or cost criteria.] else [
    #for w in dec.why [- #w \ ]
  ]
  #for n in dec.notes [#callout(title: "Unmet need")[#n]]
  #for x in dec.excluded [- Excluded by a legal or regulatory constraint: #x \ ]

  == What would change the recommendation
  #if dec.flips.len() == 0 [No single change to one input would switch the recommendation.] else [
    #for f in dec.flips [- #f \ ]
  ]
  #uncertainty(dec)

  #if "economics" in dec [
    == Cost case
    #data-table(
      columns: (2.2fr, 1fr, 1.3fr, 1.4fr, 1.2fr),
      align: (left, right, center, right, right),
      header: ("Option", "Cost ratio", "90% range", "Payback after cut-over", "Saving / year"),
      ..dec.economics.map(r => (r.option, fmt(r.ratio), r.range,
        if r.payback == none [–] else [#r.payback months], fmt(r.saving_fte, d: 1) + " FTE")).flatten(),
    )
    #v(2pt)
    #text(size: 7.5pt, fill: theme.muted)[Five-year net present value relative to the current setup; "saving / year"
      in fully loaded salaries. All inputs from the fact sheet with their ranges.]
    #v(3mm)
    #figure-block(dec.charts.tco, caption: "Exhibit 3 — Cost of each option relative to the current setup")
    #if "tornado" in dec.charts [
      #v(3mm)
      #figure-block(dec.charts.tornado, caption: "Exhibit 4 — Inputs that move the cost case most (" + dec.tornado_option + ")")
    ]
  ]
  #v(3mm)
  #figure-block(dec.charts.probabilities, caption: "Exhibit 5 — How often each hosting path applies across draws")
]

= Organisational readiness

Whatever path is chosen, it depends on how ready each part of the organisation is. This chapter shows how each
stakeholder group rates the capabilities, ways of working, alignment and governance it can judge; higher always
means more ready. Each group answers only the questions it can judge, so cells are empty where a group was not asked.

#if "matrix" in data.readiness.charts [
  #v(3mm)
  #figure-block(data.readiness.charts.matrix, caption: "Exhibit 6 — Readiness as seen by each stakeholder group",
    source: "Mean of each group's own respondents (1–5). Hatched: fewer respondents than the minimum; shown, not counted.")
]

#if data.readiness.differences.len() > 0 [
  == Where groups see things differently
  #data-table(
    columns: (3fr, 1.3fr, 1.3fr, 0.7fr, 1.2fr),
    align: (left, left, left, right, left),
    header: ("Area", "Most positive", "Most negative", "Spread", "Difference"),
    ..data.readiness.differences.map(d => (d.sub_area, d.high, d.low, fmt(d.spread, d: 1),
      if d.significant { strong(d.effect) } else { text(fill: theme.muted, d.effect + ", not significant") })).flatten(),
  )
  #v(2pt)
  #text(size: 7.5pt, fill: theme.muted)[Kruskal–Wallis test across groups on respondents' scores, effect size ε²,
    false-discovery-rate adjusted (q < 0.05).]
]

#if "weakest" in data.readiness.charts [
  == Weakest areas
  #figure-block(data.readiness.charts.weakest, caption: "Exhibit 7 — Lowest-scoring statements and how answers were distributed",
    source: "Group-weighted score (1–5) on the right; bars show the share of answers scoring low, middle and high.")
]

= Preconditions

Preconditions are attested with evidence by the sponsor, Finance, the technology lead and risk and compliance, and
checked for the recommended path after the verdict.

#for dec in data.decisions [
  == #dec.title
  #if dec.gates.len() == 0 [The recommended path requires no programme preconditions.] else [
    #data-table(
      columns: (3.6fr, 1.2fr, 2.6fr),
      header: ("Precondition", "Status", "Note"),
      ..dec.gates.map(g => (g.label, gate-badge(g.status), text(fill: theme.muted, g.corroboration.join("; ")))).flatten(),
    )
  ]
  #if dec.conditions.len() > 0 [
    #text(size: 8.5pt)[Conditions for success (not blocking): #dec.conditions.map(c => c.label + " (" + c.status + ")").join("; ").]
  ]
]

= Stakeholder perspectives

Preferences and personal stakes never influence the recommendation. They are reported at group level only, to help
plan how a decision is communicated and supported.

#if data.stakes.findings.len() > 0 [
  #callout(title: "Findings")[
    #for f in data.stakes.findings [- #f \ ]
  ]
]
#for n in data.stakes.suppressed [#text(size: 7.5pt, fill: theme.muted, n)]
#for c in data.stakes.charts [
  #v(3mm)
  #figure-block(c.path, caption: c.title)
]
#if "divergence_chart" in data.stakes [
  == Perception and measurement
  Where respondents' perception differs from the measured value by more than one point, the difference itself is a
  finding worth discussing.
  #figure-block(data.stakes.divergence_chart, caption: "Measured value against perception")
]
#if data.text != none [
  == In respondents' own words
  #block(breakable: false, callout(title: "What respondents say")[
    #for m in data.text.key_messages [- #m \ ]
  ])
  #for th in data.text.themes [
    #v(2mm)
    #block(sticky: true)[#text(weight: "semibold", fill: theme.primary, th.theme)]
    #th.finding
    #for q in th.quotes [
      #block(inset: (left: 12pt, y: 4pt), stroke: (left: 1.5pt + theme.rule))[
        #text(style: "italic")[“#q.text”] #h(4pt) #text(size: 8pt, fill: theme.muted)[— #q.role]
      ]
    ]
  ]
]

= Recommended next steps

#let phases = data.steps.map(s => s.phase_label).dedup()
#for ph in phases [
  == #ph
  #for (i, s) in data.steps.filter(s => s.phase_label == ph).enumerate() [
    #grid(columns: (9mm, 1fr),
      text(size: 12pt, weight: "light", fill: theme.accent, numbering("01", i + 1)),
      [#s.action \ #text(size: 8pt, fill: theme.muted)[Owner: #s.owner#if s.reason != "" [ · #s.reason]]],
    )
    #v(2mm)
  ]
]

#counter(heading).update(0)
#set heading(numbering: "A.1")

= Method

The assessment combines a fact sheet, completed and attested by named owners, with a survey of every stakeholder
group. Facts carry twice the weight of perceptions. Respondents are resampled within their group and fact-sheet
ranges sampled #data.rules.draws times; a path is recommended only if it applies in at least
#pct(data.rules.confidence) of these draws. Groups with fewer than #data.rules.min_role_n respondents are not scored.
The decision rules (version #data.rules.version) were
#if data.rules.signed_off_by == none [#text(fill: theme.status.RED)[not recorded as signed off]] else [signed off by #data.rules.signed_off_by]
before results were seen.

#if data.problems.len() > 0 [
  == Data gaps
  #for p in data.problems [- #p \ ]
]

#if data.fact_checks.len() > 0 [
  == Fact-sheet checks
  These do not change the recommendation; they indicate how far the inputs can be trusted and what to fix before
  the next run.
  #for f in data.fact_checks [- #if f.severity == "problem" [#text(fill: theme.status.RED)[Independence:]] else [Evidence:] #f.message \ ]
]

== Participation
#data-table(columns: (2fr, 1fr), align: (left, right), header: ("Group", "Respondents"),
  ..data.participation.map(p => (p.group, str(p.n))).flatten())

= Evidence

#data-table(
  columns: (3.4fr, 1fr, 0.8fr, 1.2fr),
  align: (left, left, right, center),
  header: ("Measure", "Axis", "Score", "95% range"),
  ..data.evidence.map(r => (r.signal, r.group, fmt(r.value), r.range)).flatten(),
)
