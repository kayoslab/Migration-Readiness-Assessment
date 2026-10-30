# Participant pack (template — v0.2 draft)

Replace `{…}` placeholders per engagement. Have the data-protection officer and, where one exists, the works
council review this pack before the survey is sent. In some jurisdictions (e.g. Germany, Austria) surveys that
capture employee attitudes require works-council consultation.

---

## 1. Cover screen (first page of the survey)

> **The future of {system}**
>
> {organisation} is reviewing how {system} should develop over the coming years. **No option has been chosen.**
> Keeping the current setup as it is, improving it, restructuring it, or changing where it runs are all on the
> table, and each will be judged against the same evidence.
>
> This survey asks about your day-to-day experience. There are no right or wrong answers. We do not collect names
> or e-mail addresses, and results are only reported for groups of five or more. Every question is optional; skip
> anything you prefer not to answer. "Don't know" is a useful answer — please use it rather than guess.
>
> It takes about {15} minutes. Thank you.

## 2. Participant information

**Who is asking and why.** The review is commissioned by {sponsor role} and run by {analyst / firm}. Its purpose
is to establish, from evidence, which direction for {system} fits the organisation best — including the option
of keeping it as it is.

**What happens to your answers.**
- Only {named analyst(s)} see individual responses. Line managers and the sponsor never do.
- Results are reported for groups of at least five people. Smaller breakdowns, including by seniority, are
  suppressed, and so are any figures from which a smaller group could be calculated.
- The questions about your preferences and how options might affect you are on a separate page and entirely
  optional. They help the organisation plan support for people affected by any change and, at group level only,
  show whether views differ between people who would be affected in different ways. They are never used to weight
  or discount anyone's answers.
- {sponsor} confirms in writing that **no decisions about individual roles will be taken on the basis of this
  survey**.

**Free-text answers** are analysed with the help of an automated language model, accessed through the Vercel AI
Gateway (provider: {model provider}, region: {region}, retention: {retention}). E-mail addresses, phone numbers,
links and names listed by the analyst are removed before processing. Quotations in the report are anonymous and
attributed to groups only.

**Data protection.**
- Controller: {organisation}, contact {DPO contact}.
- Processors: Google (survey platform), Vercel (AI gateway), {model provider}, {analyst / firm}.
- Legal basis: {e.g. legitimate interest, GDPR Art. 6(1)(f); works-council agreement of {date}}.
- Raw responses are deleted on {date}; the aggregated report is kept.
- At the end of the survey you may enter a word of your choice. If you later want your answers removed, quote that
  word to {contact} before {date}. Without it, an individual response cannot be identified or removed.

## 3. Survey platform settings (Google Forms)

- "Collect email addresses": **off**. "Limit to 1 response": **off** (it requires sign-in).
- One form per stakeholder group (separate links), so that no role question is needed.
- Shuffle option order for MD01, MD02, MD03, MD06 and MO04 only. Ordered options (e.g. RQ01, MO02, frequencies) keep their order.
- Page order: context → experience (need, capability, fit) → governance and alignment → preference →
  how options affect you (separate page, with a "skip this page" note) → open questions.
- Show "Don't know" and "Not applicable" visually separated from the scale.
- S03 shows a row only for a preference answered with a direction; S04/S05 show only the options offered for the
  current state.
- Replace `{consistency_example}` in RQ01 with an example from the organisation's own business (agree in pretest).

## 4. Invitation e-mail (to be sent by a neutral sender)

The invitation sets the tone for every answer. It should come from the analyst or a neutral party — **not** from
an advocate of any particular option.

> Subject: Your experience with {system} — 15-minute survey
>
> {organisation} is reviewing how {system} should develop. No option has been chosen, and keeping the current setup
> is one of the options. We would value your experience, whatever your view.
>
> We do not collect names or e-mail addresses, every question is optional, and results are only reported for
> groups of five or more.
> {link} — open until {date}.

## 5. Sampling frame

Invite **all members** of each defined group, not a selection. The report states the response rate per group.
