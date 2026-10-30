// Migration Readiness Assessment — default report template
//
// To brand the report for an organisation, copy this folder, change `theme` below
// (colours, fonts, optional logo) and point `report.template` in assessment.yaml at the copy.
// Fonts placed in a `fonts/` folder next to this file are picked up automatically.

#let theme = (
  font: ("Source Sans 3", "Inter", "Helvetica Neue", "Arial"),
  ink: rgb("#1f2933"),
  muted: rgb("#6b7280"),
  rule: rgb("#d9dce1"),
  subtle: rgb("#f4f5f7"),
  primary: rgb("#0b2545"),     // headings, cover, rules
  accent: rgb("#1c7c8c"),      // section numbers, call-out bars
  logo: none,                  // e.g. "logo.svg" (path relative to this folder)
  status: (
    RED: rgb("#d03b3b"),
    AMBER: rgb("#e0a100"),
    GREEN: rgb("#0c8a0c"),
  ),
  tone: (
    positive: rgb("#0c8a0c"),
    caution: rgb("#e0a100"),
    negative: rgb("#d03b3b"),
    neutral: rgb("#6b7280"),
  ),
)

// ----------------------------------------------------------------------------- components

#let eyebrow(body) = text(size: 7.5pt, weight: "semibold", fill: theme.muted, tracking: 0.08em, upper(body))

#let status-badge(status, uncertain: false) = {
  if status == none { return text(fill: theme.muted)[–] }
  let c = theme.status.at(status)
  box(baseline: 0.12em, circle(radius: 0.28em, fill: if uncertain { white } else { c }, stroke: 1pt + c))
  h(0.35em)
  text(weight: "semibold", size: 8.5pt, fill: theme.ink, status)
  if uncertain { text(size: 8pt, fill: theme.muted)[ (uncertain)] }
}

#let callout(title: none, body) = block(
  width: 100%, inset: (left: 14pt, rest: 12pt), fill: theme.subtle,
  stroke: (left: 3pt + theme.accent), breakable: true,
)[
  #if title != none [#eyebrow(title) #v(4pt)]
  #body
]

#let kpi(value, label, color: none) = block(width: 100%)[
  #text(size: 22pt, weight: "light", fill: if color == none { theme.primary } else { color }, value)
  #v(-8pt)
  #text(size: 8pt, fill: theme.muted, label)
]

#let data-table(columns: auto, align: left, header: (), ..rows) = {
  set text(size: 8.5pt)
  table(
    columns: columns,
    align: align,
    stroke: (x, y) => (bottom: if y == 0 { 0.8pt + theme.primary } else { 0.4pt + theme.rule }),
    inset: (x: 5pt, y: 6pt),
    table.header(..header.map(h => text(size: 7pt, weight: "semibold", fill: theme.muted, upper(h)))),
    ..rows,
  )
}

#let figure-block(path, caption: none, source: none) = block(width: 100%, breakable: false)[
  #if caption != none [#text(weight: "semibold", size: 9pt, fill: theme.primary, caption) #v(2pt)]
  #image(path, width: 100%)
  #if source != none [#v(-2pt) #text(size: 7pt, fill: theme.muted, source)]
]

// ----------------------------------------------------------------------------- document

#let mra-report(engagement: (:), body) = {
  let title = engagement.at("title", default: "Migration Readiness Assessment")
  let org = engagement.at("organisation", default: "")
  let classification = engagement.at("classification", default: "")

  set document(title: title + " — " + org)
  set text(font: theme.font, size: 9.5pt, fill: theme.ink, lang: "en", region: "gb")
  set par(leading: 0.72em, spacing: 1.1em, justify: false)
  set list(indent: 0.4em, body-indent: 0.6em, marker: text(fill: theme.accent)[▪])
  set enum(indent: 0.4em, body-indent: 0.6em)

  // ---- cover
  page(margin: (x: 25mm, top: 30mm, bottom: 25mm), header: none, footer: none)[
    #grid(columns: (1fr, auto),
      eyebrow(org),
      if theme.logo != none { image(theme.logo, height: 12mm) } else { eyebrow(classification) },
    )
    #v(1fr)
    #block(width: 42mm, height: 3pt, fill: theme.accent)
    #v(10pt)
    #block(width: 85%, par(leading: 0.35em, text(size: 32pt, weight: "light", fill: theme.primary, title)))
    #v(4pt)
    #text(size: 13pt, fill: theme.muted, engagement.at("subtitle", default: ""))
    #v(1fr)
    #grid(columns: (1fr, 1fr, 1fr), column-gutter: 12pt,
      [#eyebrow[Prepared for] \ #engagement.at("prepared_for", default: "")],
      [#eyebrow[Prepared by] \ #engagement.at("prepared_by", default: "")],
      [#eyebrow[Date] \ #engagement.at("date", default: "")],
    )
    #if engagement.at("sample_data", default: false) [
      #v(14pt)
      #text(size: 8pt, fill: theme.muted)[This report was produced from synthetic sample data for illustration only.]
    ]
  ]

  // ---- body pages
  set page(
    paper: "a4",
    margin: (x: 25mm, top: 30mm, bottom: 26mm),
    header: context {
      set text(size: 7.5pt, fill: theme.muted)
      grid(columns: (1fr, auto), title, org)
      v(-4pt)
      line(length: 100%, stroke: 0.4pt + theme.rule)
    },
    footer: context {
      set text(size: 7.5pt, fill: theme.muted)
      grid(columns: (1fr, auto), classification, counter(page).display())
    },
  )
  counter(page).update(1)

  set heading(numbering: "1.1")
  show heading.where(level: 1): it => {
    pagebreak(weak: true)
    block(width: 100%, below: 7mm)[
      #if it.numbering != none {
        text(size: 11pt, weight: "semibold", fill: theme.accent, numbering(it.numbering, ..counter(heading).get()))
        h(8pt)
        box(width: 24pt, height: 1pt, fill: theme.accent, baseline: -0.3em)
        linebreak()
      }
      #text(size: 20pt, weight: "regular", fill: theme.primary, it.body)
    ]
  }
  show heading.where(level: 2): it => block(sticky: true, above: 7mm, below: 3mm,
    text(size: 12pt, weight: "semibold", fill: theme.primary, it.body))
  show outline.entry.where(level: 1): it => {
    v(6pt)
    strong(it)
  }

  body
}
