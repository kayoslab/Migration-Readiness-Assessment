// v3 report: recommended path per decision. Branding lives in template.typ (shared with the v2 report).
#import "template.typ": *

#let data = json(sys.inputs.data)
#let e = data.engagement
#let anchor(name) = [#metadata(name)#label(name)]
#let caveat-box(items) = if items.len() > 0 {
  block(width: 100%, inset: (left: 10pt, y: 5pt), stroke: (left: 2pt + theme.status.AMBER), above: 2mm, below: 4mm)[
    #text(size: 8pt, weight: "semibold", fill: theme.muted, tracking: 0.06em)[CAVEAT]
    #v(1pt)
    #set text(size: 8.5pt)
    #for c in items [*#c.title.* #c.message \ ]
  ]
}

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
  #anchor("options-" + dec.id)
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
// cross-references in a "so what": exhibits by number, steps, risks, checkpoints and sections by anchor
#let xref(lbl, body) = context {
  if query(lbl).len() > 0 { link(lbl, body) } else { body }
}
#let so-what(segments) = for s in segments {
  if "t" in s { s.t }
  else if s.ref == "exhibit" {
    context {
      let q = query(label("exh-" + s.id))
      if q.len() > 0 {
        let loc = q.first().location()
        link(loc)[Exhibit #exhibit-counter.at(loc).first()]
      } else [a related exhibit]
    }
  }
  else if s.ref == "step" { xref(label("step-" + str(s.no)), [step #s.no]) }
  else if s.ref == "risk" { xref(label("risk-" + s.id), if s.at("short", default: false) [#s.id] else [risk #s.id]) }
  else if s.ref == "checkpoint" { xref(label("checkpoint-" + str(s.no)), if s.at("short", default: false) [C#s.no] else [checkpoint C#s.no]) }
  else { xref(label(s.id), s.name) }
}

#let exhibit(path, insight, source: none) = {
  exhibit-counter.step()
  block(width: 100%, breakable: false, above: 6mm)[
    #metadata(insight.id)#label("exh-" + insight.id)
    #eyebrow[Exhibit #context exhibit-counter.display()#if insight.at("role", default: "") != "" [ · #insight.role]]
    #v(1pt)
    #text(size: 10.5pt, weight: "semibold", fill: theme.primary, insight.title)
    #v(4pt)
    #if path != none [#image(path, width: 100%)]
    #if source != none [#v(-2pt) #text(size: 7pt, fill: theme.muted, source)]
    #block(width: 100%, inset: (left: 10pt, y: 5pt), stroke: (left: 2pt + theme.accent), above: 3mm, below: 5mm)[
      #text(size: 8pt, weight: "semibold", fill: theme.accent, tracking: 0.06em)[SO WHAT]
      #v(1pt)
      #set text(size: 9pt)
      #show link: set text(fill: theme.accent)
      #if "so_what" in insight [#so-what(insight.so_what)] else if insight.interpretation != none [#insight.interpretation] else [#insight.points.join(" ")]
    ]
    #caveat-box(insight.at("caveats", default: ()))
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
  #if data.at("review", default: none) != none [
    #if data.review.by != none [Quality review: #data.review.by#if data.review.on != "" [, #data.review.on].] else [#text(fill: theme.muted)[This report has not yet been through quality review.]]
    #v(2mm)
  ]
  #if data.integrity.issues.len() > 0 [
    #v(4mm)
    #text(size: 12pt, fill: theme.primary)[Qualifications]
    #v(2mm)
    The sources behind this report were read against each other. Where they disagree, the finding concerned is
    qualified below and beside the finding itself.
    #v(2mm)
    #for i in data.integrity.issues [
      #text(weight: "semibold", fill: if i.severity == "block" { theme.status.RED } else { theme.primary })[#i.title]
      #text(size: 8pt, fill: theme.muted)[ · #if i.severity == "block" [prevents a final report] else if i.severity == "caveat" [qualifies findings] else [for information]] \
      #i.message
      #v(2mm)
    ]
  ]
]

#page(header: none)[
  #v(12mm)
  #text(size: 20pt, weight: "regular", fill: theme.primary)[Contents]
  #v(8mm)
  #outline(title: none, depth: 1, indent: 0pt)
]

#anchor("decision")
= Decision requested

#if data.integrity.draft [
  #text(weight: "semibold", fill: theme.status.RED)[Draft — not for decision until the conditions below are resolved.]
  #v(2mm)
]
#for r in data.brief.requests [
  #block(breakable: false, below: 4mm)[
    #eyebrow[#r.decision · #text(fill: theme.tone.at(r.tone), r.status)]
    #v(1pt)
    #text(size: 10.5pt, weight: "semibold", fill: theme.primary, r.ask)
    #set text(size: 9pt)
    #if r.not_yet != none [\ *Not approved now:* #r.not_yet]
    #if r.budget != none [\ *Budget:* #r.budget]
  ]
]

#set text(size: 9pt)
#grid(columns: (24mm, 1fr), row-gutter: 2.5mm, column-gutter: 4mm,
  text(weight: "semibold", fill: theme.primary)[Situation], data.brief.scr.situation,
  text(weight: "semibold", fill: theme.primary)[Complication], data.brief.scr.complication,
  text(weight: "semibold", fill: theme.primary)[Resolution], data.brief.scr.resolution,
)
#v(3mm)
#grid(columns: (1fr, 1fr), column-gutter: 8mm,
  [
    #if data.brief.money.len() > 0 [
      #text(weight: "semibold", fill: theme.primary)[The money] \
      #for m in data.brief.money [- #m \ ]
      #v(2mm)
    ]
    #if data.brief.conditions.len() > 0 [
      #text(weight: "semibold", fill: theme.primary)[Conditions] \
      #for c in data.brief.conditions [- #c \ ]
      #text(size: 8pt, fill: theme.muted)[Explained in the Important notice and beside the findings they affect.]
    ]
  ],
  [
    #text(weight: "semibold", fill: theme.primary)[When the decision is taken again] \
    #for g in data.brief.again [- #g \ ]
  ],
)
#set text(size: 9.5pt)

= Executive summary

#if data.integrity.draft [
  #block(width: 100%, inset: 8pt, stroke: 1pt + theme.status.RED, below: 4mm)[
    #text(weight: "semibold", fill: theme.status.RED)[Draft — not for decision.]
    #for b in data.integrity.blocks [#b.message ]
  ]
]

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
#if data.integrity.caveats.len() > 0 [
  #v(2mm)
  #text(size: 8.5pt, weight: "semibold", fill: theme.primary)[Qualifications: ]
  #text(size: 8.5pt)[#data.integrity.caveats.map(c => c.title).join("; "). Each is explained in the Important notice
    and beside the findings it affects.]
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

#v(4mm)
#text(size: 7.5pt, fill: theme.muted, data.evidence_note)

= Architecture

#if data.narrative != none and data.narrative.chapters.at("architecture", default: "") != "" [
  #text(size: 10pt, data.narrative.chapters.architecture)
  #v(2mm)
]

#for dec in data.decisions.filter(d => d.id == "architecture") [
  #text(size: 10pt)[Current state: #dec.current. Recommended: *#dec.verdict_label* — #dec.status_label.]
  #caveat-box(dec.at("caveats", default: ()))

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
  #if "investment" in dec [
    == What it takes
    #let inv = dec.investment
    #if inv.estimated [
      The first steps on the recommended path take about #fmt(inv.effort, d: 0) person-months over
      #fmt(inv.months, d: 0) months (up to #fmt(inv.months_high, d: 0) at the high estimate) — about
      #fmt(inv.fte, d: 0) FTE#if inv.show_amounts [, costing #text(weight: "semibold")[€#fmt(inv.cost / 1000, d: 0)k]
      (90% range €#fmt(inv.cost_low / 1000, d: 0)k–€#fmt(inv.cost_high / 1000, d: 0)k) including external support].
      #if inv.start > 0 [They start once the preconditions are in place, after checkpoint C1.]
      #text(size: 8pt, fill: theme.muted)[Estimated independently by #(inv.estimators.join(" and ")); the model uses
        both ranges#if inv.reference_class != none [, with the high end raised to at least the organisation's typical
        past overrun of #fmt(inv.reference_class, d: 0)%]. The estimate informs the approval; it does not change the
        recommendation.]
    ] else [
      Not yet estimated: #inv.missing.map(m => lower(m)).join("; "). The technology lead and a second, independent
      estimator provide these before checkpoint C1.
    ]
  ]

  #v(3mm)
  #exhibit(dec.charts.probabilities, dec.insights.probabilities,
    source: "Share of " + str(data.rules.draws) + " draws in which each path applies; each draw resamples the respondents within their group and every estimate within its range. The verdict requires " + pct(data.rules.confidence) + ".")
  #if "map" in dec.charts [
    #v(3mm)
    #exhibit(dec.charts.map, dec.insights.map,
      source: "Need for change against the weakest of the delivery capabilities a larger change relies on (pipeline, platform basics, operations), from fact sheet and survey. Each dot is one draw; the large dot is the point estimate.")
  ]
  #if "leadtime" in dec.charts [
    #exhibit(dec.charts.leadtime, dec.insights.leadtime,
      source: "Answers to “where does most of the time go between code complete and running in production?”, grouped as in the decision rules; asked of the groups that work on releases.")
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
  #caveat-box(dec.at("caveats", default: ()))

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
    #if dec.show_amounts [
      #data-table(
        columns: (2fr, 1fr, 1.5fr, 0.8fr, 1.1fr, 1.3fr),
        align: (left, right, right, right, right, right),
        header: ("Option", "5-year cost", "90% range", "vs today", "Payback", "Saving / year"),
        ..dec.economics.map(r => (r.option, r.eur, r.eur_range, fmt(r.ratio) + "×",
          if r.payback == none [–] else [#r.payback months #text(size: 7.5pt, fill: theme.muted, r.payback_from)],
          if r.saving_eur == none [–] else [#r.saving_eur (≈ #fmt(r.saving_fte, d: 1) FTE)])).flatten(),
      )
    ] else [
      #data-table(
        columns: (2.2fr, 1fr, 1.3fr, 1.4fr, 1.2fr),
        align: (left, right, center, right, right),
        header: ("Option", "Cost ratio", "90% range", "Payback after cut-over", "Saving / year"),
        ..dec.economics.map(r => (r.option, fmt(r.ratio), r.range,
          if r.payback == none [–] else [#r.payback months], fmt(r.saving_fte, d: 1) + " FTE")).flatten(),
      )
    ]
    #v(2pt)
    #text(size: 7.5pt, fill: theme.muted)[Five-year cost as present value, each option against today's setup as it is.
      The saving per year is also expressed in fully loaded salaries (FTE) for scale; it is not a headcount figure. The decision rules compare a move with an improved
      current setup, so moving must also beat what improving would achieve. All inputs from the fact sheet with
      their ranges.]
    #if dec.at("inaction", default: none) != none [
      #v(2mm)
      *If nothing changes.* #dec.inaction
    ]
    #if dec.at("calendar", default: ()).len() > 0 [
      #anchor("calendar")
      == Decision calendar
      #data-table(
        columns: (0.6fr, 1.6fr, 4fr),
        align: (right, left, left),
        header: ("Month", "Event", "What to decide or do"),
        ..dec.calendar.map(c => (fmt(c.month, d: 0), c.event, text(size: 8.5pt, c.action))).flatten(),
      )
    ]
    #v(3mm)
    #exhibit(dec.charts.tco, dec.insights.tco,
      source: "Five-year net present value relative to the current setup; dot = likely value, line = 90% range.")
    #if "scenarios" in dec and dec.scenarios.len() > 0 [
      #anchor("scenarios-hosting")
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
        source: "Cost of " + lower(dec.tornado_option) + " relative to an improved current setup — the comparison the decision rules make — with each input at its low and high estimate, all others at their likely value.")
    ]
  ]
  #v(3mm)
  #exhibit(dec.charts.probabilities, dec.insights.probabilities,
    source: "Share of " + str(data.rules.draws) + " draws in which each hosting path applies; each draw resamples the respondents and every estimate within its range.")
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
    source: "Readiness as seen by each group: mean of the group's own respondents (1–5), survey answers only — elsewhere the assessment combines them with measured facts, so scores there can differ. Hatched: fewer respondents than the minimum; shown, not counted.")
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

#if "benchmark" in data.readiness [
  #let bm = data.readiness.benchmark
  #block(breakable: false)[
    == Delivery performance against the industry
    The fact sheet's delivery measures compared with DORA's #bm.source.edition industry benchmarks: for the
    #(bm.industry) industry#if bm.industry == "All industries" [ as a whole], and for organisations of
    #lower(bm.organisation_size).
    #exhibit(bm.chart, bm.insight,
      source: "Scores on DORA's scale from 0 to 10 (10 best). Grey band: industry average, plus or minus one standard deviation.")
  ]
  #v(2mm)
  #data-table(
    columns: (2fr, 2.3fr, 2fr, 0.9fr, 1fr, 1.1fr),
    align: (left, left, left, left, left, left),
    header: ("Measure", "Measured", "Industry average", "vs industry", "vs same size", "2024 level"),
    ..bm.rows.map(r => (r.label, text(size: 8.5pt, r.shown),
      text(size: 8.5pt, r.industry_typical + " (score " + fmt(r.industry_mean, d: 1) + ")"),
      r.position, if r.size_position == none [–] else [#r.size_position],
      if r.level_2024 == none [–] else [#r.level_2024])).flatten(),
  )
  #v(2pt)
  #text(size: 7.5pt, fill: theme.muted)[
    Position: above or below when more than half a standard deviation from the group's average on DORA's scale;
    "same size" compares with organisations of #lower(bm.organisation_size) across all industries.
    DORA's figures are what survey respondents report; this organisation's come from its fact sheet, so the
    comparison is indicative. See Method.
  ]
  #v(3mm)
]

#anchor("preconditions")
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
#text(size: 9pt, fill: theme.muted)[Groups: #data.group_names.pairs().map(((k, v)) => k + " " + v).join(" · ").]
#if "pooled_note" in data.stakes [#text(size: 9pt, fill: theme.muted, data.stakes.pooled_note)]

#if data.stakes.findings.len() > 0 [
  #callout(title: "Findings")[
    #for f in data.stakes.findings [- #f \ ]
  ]
]
#for n in data.stakes.suppressed [#text(size: 7.5pt, fill: theme.muted, n)]
#for c in data.stakes.charts [
  #exhibit(c.path, c.insight, source: c.source)
]
#if "map" in data.stakes [
  #block(breakable: false)[
    == Stakeholder map
    Where each group stands on the recommended path, and how much influence it has on the decision. The map plans
    engagement; it never weights anyone's answers.
    #exhibit(data.stakes.map_chart, data.stakes.map_insight,
      source: "Support: share of the group preferring the recommended path or its interim step. Influence: agreed with the sponsor, or a stated default.")
  ]
  #v(2mm)
  #data-table(
    columns: (1fr, 1fr, 1.2fr, 1.2fr, 2fr),
    align: (left, right, left, right, left),
    header: ("Group", "Support", "Influence", "Role concern", "Approach"),
    ..data.stakes.map.map(r => (r.group, pct(r.support), r.influence + if r.influence_source == "default" [ (default)] else [],
      if r.concern == none [–] else [#pct(r.concern)], r.approach)).flatten(),
  )
  #if "pooled_note" in data.stakes [#text(size: 7.5pt, fill: theme.muted, data.stakes.pooled_note)]
]
#if "divergence_chart" in data.stakes [
  #block(breakable: false)[
    == Perception and measurement
    Where respondents' perception differs from the measured value by more than one point, the difference itself is a
    finding worth discussing.
    #exhibit(data.stakes.divergence_chart, data.stakes.divergence_insight,
      source: "Measured value (fact sheet) against perception (survey), where they differ by more than one point.")
  ]
]
#if data.text != none [
  #anchor("free-text")
  == In respondents' own words
  #block(breakable: false, callout(title: "What respondents say")[
    #for (n, m) in data.text.key_messages.enumerate() [
      - #m #for c in data.text.at("key_message_caveats", default: ()).at(n, default: ()) [#text(size: 8pt, fill: theme.status.AMBER)[Caveat:] #text(size: 8.5pt, c)] \
    ]
  ])
  #for th in data.text.themes [
    #v(2mm)
    #block(sticky: true)[#text(weight: "semibold", fill: theme.primary, th.theme)]
    #th.finding
    #caveat-box(th.at("caveats", default: ()).map(c => (title: "Caveat", message: c)))
    #for q in th.quotes [
      #block(inset: (left: 12pt, y: 4pt), stroke: (left: 1.5pt + theme.rule))[
        #text(style: "italic")[“#q.text”] #h(4pt) #text(size: 8pt, fill: theme.muted)[— #q.role]
      ]
    ]
  ]
]

#anchor("risks")
= Risks, assumptions and dependencies

Each entry follows from a finding in this report; likelihood and impact are rated by rule (high · medium · low),
owners and mitigations come from the action library.

#data-table(
  columns: (0.45fr, 3.2fr, 0.4fr, 0.4fr, 1.3fr, 2.9fr),
  align: (left, left, center, center, left, left),
  header: ("", "Risk", "L", "I", "Owner", "Mitigation"),
  ..data.risks.risks.map(r => ([#metadata(r.id)#label("risk-" + r.id)#text(weight: "semibold", r.id)], [#r.title #linebreak() #text(size: 7.5pt, fill: theme.muted, r.cause)],
    upper(r.likelihood.slice(0, 1)), upper(r.impact.slice(0, 1)), text(size: 8pt, r.owner), text(size: 8pt, r.mitigation))).flatten(),
)

#anchor("assumptions")
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
  #data-table(columns: (0.5fr, 0.8fr, 5fr), align: (left, right, left), header: ("", "Month", "Checkpoint"),
    ..data.roadmap.gates.enumerate().map(((i, g)) => ([#metadata(i)#label("checkpoint-" + str(i + 1))C#(i + 1)],
      str(g.month), g.label)).flatten())
  #v(3mm)
]

#if data.at("budget", default: none) != none [
  #anchor("budget")
  == Budget by phase
  Both decisions together, by months from the decision#if data.budget.show_amounts [ (likely values)].
  #data-table(
    columns: (3fr,) + data.budget.phases.map(_ => 1fr) + (1.1fr,),
    align: (left,) + data.budget.phases.map(_ => right) + (right,),
    header: ("",) + data.budget.phases.map(p => "Months " + p) + ("Total",),
    ..data.budget.rows.map(r => (r.item,) + r.cells_text + (r.total_text,)).flatten(),
    text(weight: "semibold")[Total], ..data.budget.totals_text.map(t => text(weight: "semibold", t)),
    text(weight: "semibold", data.budget.total_text),
  )
  #v(2pt)
  #text(size: 7.5pt, fill: theme.muted)[#for r in data.budget.rows.filter(r => r.range != none) [#r.item: 90% range
    #r.range. ] One-off costs only; running costs are in the cost case. Hosting amounts follow the decision calendar.]
  #v(3mm)
]

#if data.roadmap.at("load", default: ()).len() > 0 [
  #callout(title: "Capacity")[#for n in data.roadmap.load [- #n \ ]]
  #v(3mm)
]

#if data.triggers.len() > 0 [
  #anchor("triggers")
  == When to reopen the decision
  Agreed now, so that disagreement becomes a test rather than a debate: each decision is reopened only if one of these
  conditions holds when it is checked.
  #for tr in data.triggers [
    #v(1mm)
    #block(breakable: false)[
      #text(weight: "semibold", fill: theme.primary)[#upper(tr.decision.slice(0, 1))#tr.decision.slice(1)]: reopen
      “#tr.alternative” at #tr.when if
      #for (i, c) in tr.conditions.enumerate() [- #if i > 0 [or ]#c \ ]
      #if tr.own_tests.len() > 0 [
        #text(size: 8.5pt, fill: theme.muted)[Respondents named their own test:]
        #for q in tr.own_tests [
          #block(inset: (left: 12pt, y: 3pt), stroke: (left: 1.5pt + theme.rule))[
            #text(size: 8.5pt, style: "italic")[“#q.text”] #h(4pt) #text(size: 8pt, fill: theme.muted)[— #q.role]
          ]
        ]
      ]
    ]
  ]
  #v(3mm)
]

#if data.measures.len() > 0 [
  #anchor("measures")
  == Success measures
  The measures by which the decision should be judged at each checkpoint. Proposed targets move one performance
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
  #for s in data.steps.filter(s => s.phase_label == ph) [
    #metadata(s.no)#label("step-" + str(s.no))
    #grid(columns: (9mm, 1fr),
      text(size: 12pt, weight: "light", fill: theme.accent, (if s.no < 10 { "0" } else { "" }) + str(s.no)),
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

#if "benchmark" in data.readiness [
  #let bm = data.readiness.benchmark
  == Benchmarks
  Delivery measures are compared with the #bm.source.edition industry benchmarks of DORA, Google Cloud's
  long-running research programme on software delivery. For each industry and company size, DORA publishes the
  average result and how widely results vary, not a ranking; the report therefore places each measure above, around
  or below the average rather than giving a percentile. The organisation's figures are converted to DORA's scoring
  scale in the same way as DORA's own online Quick Check. The performance level (elite, high, medium, low) comes from
  DORA's 2024 report; DORA has since stopped publishing levels and stresses that steady improvement matters more than
  reaching one.
]

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
  ..data.participation.map(p => ([#p.group #text(size: 8pt, fill: theme.muted, data.group_names.at(p.group, default: ""))], str(p.n), if p.invited == none [–] else [#p.invited],
    if p.rate == none [not recorded] else [#pct(p.rate)])).flatten())

= Evidence

Each score combines the fact sheet (counted twice) with the survey, across all groups equally; the readiness chapter
shows survey answers alone, by group, which is why the same area can score differently there.
#v(2mm)
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
