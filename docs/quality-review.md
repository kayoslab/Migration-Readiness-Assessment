# Quality review before a report is final

A second person — not the analyst who ran the assessment, and without a stake in the outcome — reviews every report
before it is issued as final, in the way an advisory firm's engagement quality reviewer does. The automated checks
(`mra report` prints them; `--final` enforces them) cover what software can check; this list covers the rest.

When the review is complete, record it in `engagement.yaml`:

```yaml
report:
  reviewed_by: "Name, role"
  reviewed_on: 2026-11-04
```

and build with `mra report <engagement.yaml> --final`. The notice page then names the reviewer.

## 1. Basis

- [ ] The decision rules were signed off, with names and date, before the fact sheet was frozen and before results
      were seen. Any change to thresholds after that is recorded and explained.
- [ ] The fact-sheet owner is not the sponsor of the change; facts that carry the outcome have a second attester.
- [ ] The scope (system, decisions, groups invited) matches what was agreed with the sponsor.

## 2. Numbers tie out

Pick at least five figures from the decision page and the executive summary and trace each to its source:

- [ ] today's run cost and the reconciliation with the invoiced total;
- [ ] the five-year cost of the recommended hosting path and of keeping today's setup;
- [ ] the architecture investment and both estimators' ranges;
- [ ] one survey share quoted in the text (to the group-level table);
- [ ] one delivery measure (to the system it was measured in, with date).

## 3. Qualifications

- [ ] Every caveat on the notice page is understood and agreed with the sponsor; none is a surprise to them.
- [ ] Where Finance or another owner must act (allocating a cost difference, verifying measures), the action and
      its owner are in the next steps.
- [ ] Groups below the minimum size are named, and nobody can be identified from the stakeholder pages.

## 4. Neutrality and language

- [ ] The decision page requests what the evidence supports and nothing more; alternatives and what one would need
      to believe for them are presented fairly.
- [ ] Wording about people's stakes is neutral: views attributed to groups, never to individuals, no motives.
- [ ] No technical identifiers, field names or codes in the text (the automated check covers most; read the
      decision page and executive summary in full).
- [ ] If the narrative was drafted with a language model, the dropped sentences listed by `mra report` were read,
      and the narrative was compared with the decision page for consistency.

## 5. Read-through

- [ ] The sponsor has read the decision page and the qualifications before the report goes to the board.
- [ ] Someone who did not work on the assessment has read the decision page alone and can say what is being asked,
      what it costs, and when it is decided again.
