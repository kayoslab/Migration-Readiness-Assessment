# Briefing for the data-protection officer and the works council

This briefing describes what the assessment collects, how it is processed and what protects the people who answer.
It is written to support the review by the data-protection officer (DPO) and, where one exists, the works council
before any survey is sent. It does not replace their assessment: the legal basis, any data-protection impact
assessment and any works agreement are theirs to decide. The participant information that respondents see is in
[`instrument/participant-information.md`](../../instrument/participant-information.md).

## 1. Purpose

To decide, on evidence, how a named software system should develop — including the option of keeping it as it is.
The survey asks employees about their day-to-day experience with the system, their preferred direction, and how
each option might affect their own role. The result is a report to the leadership team, at group level only.

**Not a purpose:** assessing individuals, their performance or their positions. The sponsor confirms in writing that
no decision about individual roles is taken on the basis of the survey (participant information, section 2).

## 2. What is collected

| Data | Source | Personal? | Notes |
|---|---|---|---|
| Group (e.g. Engineering, Finance) | Which form the person opens | Group membership | One form per group; no role question |
| Seniority band and closeness to the system | Two questions on page 1 | Yes, in combination | Used only for breakdowns of at least five people |
| Ratings and choices about the system | Survey pages 2–4 | Opinions about work | No questions about colleagues or managers |
| Preferred direction and expected effect on one's own role | Page 5, separate and optional | Yes — sensitive in context | Reported for groups only; never used to weight answers |
| Free-text answers | Open questions | May contain anything | Redacted before automated analysis (section 4) |
| A self-chosen withdrawal word | Optional, last page | Pseudonymous | Never sent to the language model |
| Facts about the system (costs, metrics) | Fact sheet, completed by named owners | Names of attesters | Business data; attesters are named by design |

Not collected: names, e-mail addresses, IP-linked sign-in, timestamps beyond what the form platform records. Forms
are set up without sign-in ("collect email addresses" off; "limit to one response" off).

## 3. Protections built into the analysis

- **Minimum group size of five.** Groups with fewer respondents are pooled with other small groups or not shown,
  and figures from which a small group could be calculated by difference are suppressed.
- **Group-level reporting only.** Every figure and quotation in the report is attributed to a group, never to a
  person; quotations are chosen by the analyst and checked for identifying details.
- **Personal stakes are not held against anyone.** The report may show that a group's preferences track how options
  affect its roles; it never discounts or weights answers on that basis, and the wording is checked for neutrality.
- **Stakeholder map off by default.** The page that places groups by support and influence is only included when the
  engagement switches it on, after discussion with the sponsor.
- **Access.** Only the named analyst(s) see individual responses; line managers and the sponsor do not.

## 4. Automated analysis of free text (optional)

If the engagement uses it, free-text answers are coded (themes, sentiment, stance) by a language model, reached through
the Vercel AI Gateway; the model provider and region are configured per engagement.

- Before sending, e-mail addresses, phone numbers, links and names listed by the analyst are replaced with
  "[redacted]"; the withdrawal word is never sent.
- Coded results are cached on disk in the engagement folder (`Output/llm_cache`), so that repeated report runs do not
  resend data. **The cache contains the redacted answers and must be deleted together with the raw responses.**
- The language model also drafts parts of the report's narrative from aggregated findings; these contain no
  individual answers. Every sentence it drafts is checked before use.
- Processors to list: the survey platform, Vercel, the model provider and the analyst or firm.

Questions for the DPO: whether the provider's data-processing terms, region and retention settings are acceptable;
whether a transfer outside the EEA occurs and on which safeguard; and whether a data-protection impact assessment is
required for this processing.

## 5. Retention and rights

- Raw responses, the cache and the interviewer sheets of any pretest are deleted on a date set per engagement; the
  aggregated report is kept.
- A respondent who recorded a withdrawal word can have their response removed before that date. Without the word, an
  individual response cannot be identified, and so cannot be removed or disclosed.

## 6. For the works council

- Where a works council exists, it should be involved before the survey is sent. In some jurisdictions (for example
  Germany and Austria) surveys of employees, or tools that could be used to assess behaviour or performance, are
  subject to co-determination; the works council decides whether an agreement is needed.
- Points the works council typically asks about, and where the answer is:
  - **Can results identify individuals?** Minimum group size of five; pooling; suppression by difference
    (section 3).
  - **Can results be used for decisions about individuals?** No — written confirmation by the sponsor.
  - **Is participation voluntary?** Yes; every question is optional, including the whole of page 5.
  - **Who is asking?** A neutral sender, not an advocate of any option (participant information, section 4).
  - **Will the works council see the results?** Agree this in advance; the group-level report is suitable for
    sharing.

## 7. Checklist before the survey is sent

- [ ] Legal basis recorded in the participant information.
- [ ] Decision on a data-protection impact assessment recorded.
- [ ] Processors and their terms confirmed (survey platform; if used: Vercel and the model provider, region,
      retention).
- [ ] Works council consulted; agreement in place where required.
- [ ] Sponsor's written confirmation that no individual decisions follow from the survey.
- [ ] Deletion date for raw responses and the cache set and entered in the participant information.
- [ ] Forms checked: no sign-in, no e-mail collection, separate links per group.
