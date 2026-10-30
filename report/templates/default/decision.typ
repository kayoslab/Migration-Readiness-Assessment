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

#let state-text(s) = {
  let c = if s == "applies" { theme.status.GREEN } else if s == "applies after preparation" { theme.status.AMBER } else { theme.muted }
  text(fill: c, s)
}

#let options(dec) = [
  == Options considered
  Every path open from the current state, assessed on the same evidence. Programme size, reversibility and time to
  value are stated judgements; all other columns come from the assessment.
  #data-table(
    columns: if dec.id == "hosting" { (2.6fr, 0.8fr, 1.5fr, 0.8fr, 2fr, 0.7fr) } else { (2.8fr, 0.8fr, 1.6fr, 2.2fr, 0.7fr) },
    align: if dec.id == "hosting" { (left, right, left, right, left, right) } else { (left, right, left, left, right) },
    header: if dec.id == "hosting" { ("Option", "Applies", "Status", "Cost", "Programme · reversibility · time", "Gates") }
            else { ("Option", "Applies", "Status", "Programme · reversibility · time", "Gates") },
    ..dec.options.map(o => {
      let name = if o.is_verdict { strong(o.label) } else { o.label }
      let judgement = text(size: 8pt, o.programme + " · " + o.reversibility + " · " + o.time_to_value)
      if dec.id == "hosting" {
        (name, pct(o.probability), state-text(o.state), if o.cost_vs_today == none [–] else [#fmt(o.cost_vs_today)×], judgement, str(o.preconditions))
      } else {
        (name, pct(o.probability), state-text(o.state), judgement, str(o.preconditions))
      }
    }).flatten(),
  )
  #v(2pt)
  #text(size: 7.5pt, fill: theme.muted)[Applies: share of draws. #if dec.id == "hosting" [Cost: five-year cost relative to today's setup as it is. ]Gates: preconditions to attest before committing.]

  == What you would need to believe
  For each alternative, the conditions under which it — rather than the recommended path — would apply.
  #for o in dec.options.filter(o => not o.is_verdict and o.beliefs.len() > 0) [
    #v(1mm)
    #block(sticky: true)[#text(weight: "semibold", fill: theme.primary, o.label)]
    #set text(size: 9pt)
    #for b in o.beliefs [- #b \ ]
  ]
]

// An exhibit in advisory style: number, action title (the insight), chart, source, and "so what".
#let exhibit-counter = counter("exhibit")
#let exhibit(path, insight, source: none) = {
  exhibit-counter.step()
  block(width: 100%, breakable: false, above: 6mm)[
    #eyebrow[Exhibit #context exhibit-counter.display()]
    #v(1pt)
    #text(size: 10.5pt, weight: "semibold", fill: theme.primary, insight.title)
    #v(4pt)
    #image(path, width: 100%)
    #if source != none [#v(-2pt) #text(size: 7pt, fill: theme.muted, source)]
    #block(width: 100%, inset: (left: 10pt, y: 5pt), stroke: (left: 2pt + theme.accent), above: 3mm, below: 5mm)[
      #text(size: 8pt, weight: "semibold", fill: theme.accent, tracking: 0.06em)[SO WHAT]
      #v(1pt)
      #set text(size: 9pt)
      #if insight.interpretation != none [#insight.interpretation] else [#insight.points.join(" ")]
    ]
  ]
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
  #text(size: 20pt, weight: "regular", fill: theme.primary)[Important notice]
  #v(6mm)
  #set text(size: 9pt)
  #for p in data.notice [#p #v(2mm)]
]

#page(header: none)[
  #v(12mm)
  #text(size: 20pt, weight: "regular", fill: theme.primary)[Contents]
  #v(8mm)
  #outline(title: none, depth: 1, indent: 0pt)
]

= Executive summary

#if data.narrative != none [
  #for p in data.narrative.executive [
    #text(size: 10pt, p)
    #v(3mm)
  ]
  #v(2mm)
]

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

#if data.narrative != none and data.narrative.chapters.at("architecture", default: "") != "" [
  #text(size: 10pt, data.narrative.chapters.architecture)
  #v(2mm)
]

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
  #options(dec)

  #v(3mm)
  #exhibit(dec.charts.probabilities, dec.insights.probabilities,
    source: "Share of bootstrap draws in which each path applies. Respondents resampled within group; fact-sheet ranges sampled. The verdict requires " + pct(data.rules.confidence) + ".")
  #if "map" in dec.charts [
    #v(3mm)
    #exhibit(dec.charts.map, dec.insights.map,
      source: "Need for change against the weakest capability. Each dot is one bootstrap draw; the large dot is the point estimate.")
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

#if data.narrative != none and data.narrative.chapters.at("hosting", default: "") != "" [
  #text(size: 10pt, data.narrative.chapters.hosting)
  #v(2mm)
]

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
  #options(dec)

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
    #text(size: 7.5pt, fill: theme.muted)[Five-year net present value of each option relative to today's setup as it is;
      "saving / year" in fully loaded salaries. The decision rules compare a move with an improved current setup, so
      moving must also beat what improving would achieve. All inputs from the fact sheet with their ranges.]
    #v(3mm)
    #exhibit(dec.charts.tco, dec.insights.tco,
      source: "Five-year net present value relative to the current setup; dot = likely value, line = 90% range.")
    #if "scenarios" in dec and dec.scenarios.len() > 0 [
      == Scenarios
      #data-table(
        columns: (2.2fr, 1fr, 1fr, 1fr),
        align: (left, right, right, right),
        header: ("Option", "Conservative", "Base", "Favourable"),
        ..dec.scenarios.rows.map(r => (r.option, fmt(r.conservative) + "×", fmt(r.base) + "×", fmt(r.favourable) + "×")).flatten(),
      )
      #v(2pt)
      #text(size: 7.5pt, fill: theme.muted)[Five-year cost relative to today's setup as it is. Conservative and favourable
        put every estimate at the end of its range that hurts or helps the option — bounds, not forecasts.]
      #for b in dec.scenarios.breakeven [- #b.sentence \ ]
    ]
    #if "tornado" in dec.charts [
      #v(3mm)
      #exhibit(dec.charts.tornado, dec.insights.tornado,
        source: "Cost ratio of " + dec.tornado_option + " with each input at its low and high estimate, all others at their likely value.")
    ]
  ]
  #v(3mm)
  #exhibit(dec.charts.probabilities, dec.insights.probabilities,
    source: "Share of bootstrap draws in which each hosting path applies.")
]

= Organisational readiness

#if data.narrative != none and data.narrative.chapters.at("readiness", default: "") != "" [
  #text(size: 10pt, data.narrative.chapters.readiness)
  #v(2mm)
]

Whatever path is chosen, it depends on how ready each part of the organisation is. This chapter shows how each
stakeholder group rates the capabilities, ways of working, alignment and governance it can judge; higher always
means more ready. Each group answers only the questions it can judge, so cells are empty where a group was not asked.

#if "matrix" in data.readiness.charts [
  #v(3mm)
  #exhibit(data.readiness.charts.matrix, data.readiness.insights.matrix,
    source: "Readiness as seen by each group: mean of the group's own respondents (1–5). Hatched: fewer respondents than the minimum; shown, not counted.")
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
  #exhibit(data.readiness.charts.weakest, data.readiness.insights.weakest,
    source: "Lowest-scoring statements: group-weighted score (1–5) on the right; bars show the share of answers scoring low, middle and high.")
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

#if data.narrative != none and data.narrative.chapters.at("people", default: "") != "" [
  #text(size: 10pt, data.narrative.chapters.people)
  #v(2mm)
]

Preferences and personal stakes never influence the recommendation. They are reported at group level only, to help
plan how a decision is communicated and supported.

#if data.stakes.findings.len() > 0 [
  #callout(title: "Findings")[
    #for f in data.stakes.findings [- #f \ ]
  ]
]
#for n in data.stakes.suppressed [#text(size: 7.5pt, fill: theme.muted, n)]
#for c in data.stakes.charts [
  #exhibit(c.path, c.insight, source: c.source)
]
#if "divergence_chart" in data.stakes [
  == Perception and measurement
  Where respondents' perception differs from the measured value by more than one point, the difference itself is a
  finding worth discussing.
  #exhibit(data.stakes.divergence_chart, data.stakes.divergence_insight,
    source: "Measured value (fact sheet) against perception (survey), where they differ by more than one point.")
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

= Risks, assumptions and dependencies

Each entry follows from a finding in this report; likelihood and impact are rated by rule (high · medium · low),
owners and mitigations come from the action library.

#data-table(
  columns: (3.2fr, 0.45fr, 0.45fr, 1.4fr, 3fr),
  align: (left, center, center, left, left),
  header: ("Risk", "L", "I", "Owner", "Mitigation"),
  ..data.risks.risks.map(r => ([#r.title #linebreak() #text(size: 7.5pt, fill: theme.muted, r.cause)],
    upper(r.likelihood.slice(0, 1)), upper(r.impact.slice(0, 1)), text(size: 8pt, r.owner), text(size: 8pt, r.mitigation))).flatten(),
)

== Key assumptions
#data-table(
  columns: (3.4fr, 1.6fr, 1.8fr),
  header: ("Assumption", "Basis", "Sensitivity"),
  ..data.risks.assumptions.map(a => (text(size: 8.5pt, a.assumption), text(size: 8pt, fill: theme.muted, a.basis),
    text(size: 8pt, a.sensitivity))).flatten(),
)

#if data.risks.dependencies.len() > 0 [
  == Dependencies
  #data-table(
    columns: (1fr, 3fr, 1.6fr, 1fr),
    header: ("Decision", "Depends on", "Owner", "Status"),
    ..data.risks.dependencies.map(x => (x.decision, x.dependency, x.owner, x.status)).flatten(),
  )
]

= Recommended next steps

#if data.roadmap.chart != none [
  #exhibit(data.roadmap.chart, data.roadmap.insight,
    source: "Indicative sequencing from the next steps below; hatched = high estimate of the migration duration.")
  #v(2mm)
  #data-table(columns: (0.5fr, 0.8fr, 5fr), align: (left, right, left), header: ("", "Month", "Review point"),
    ..data.roadmap.gates.enumerate().map(((i, g)) => ("R" + str(i + 1), str(g.month), g.label)).flatten())
  #v(3mm)
]

#if data.measures.len() > 0 [
  == Success measures
  The measures by which the decision should be judged at each review point. Proposed targets move one performance
  band; targets agreed with the sponsor replace them.
  #data-table(
    columns: (0.9fr, 3.4fr, 0.9fr, 1.3fr, 1.4fr),
    align: (left, left, right, left, left),
    header: ("Decision", "Measure", "Today", "Target", "Basis"),
    ..data.measures.map(m => (m.decision, text(size: 8.5pt, m.measure), m.baseline, m.target,
      text(size: 8pt, fill: theme.muted, m.basis))).flatten(),
  )
  #v(3mm)
]

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
#data-table(columns: (2fr, 1fr, 1fr, 1fr), align: (left, right, right, right),
  header: ("Group", "Respondents", "Invited", "Response rate"),
  ..data.participation.map(p => (p.group, str(p.n), if p.invited == none [–] else [#p.invited],
    if p.rate == none [not recorded] else [#pct(p.rate)])).flatten())

= Evidence

#data-table(
  columns: (3.4fr, 1fr, 0.8fr, 1.2fr),
  align: (left, left, right, center),
  header: ("Measure", "Axis", "Score", "95% range"),
  ..data.evidence.map(r => (r.signal, r.group, fmt(r.value), r.range)).flatten(),
)

#if data.glossary.len() > 0 [
  = Glossary
  #for g in data.glossary [
    #text(weight: "semibold", fill: theme.primary, g.term) \
    #text(size: 9pt, g.definition)
    #v(2mm)
  ]
]
