# Cognitive pretest protocol

Before the survey is used for the first time, 3–5 people answer it aloud while an interviewer watches. The aim is
not their answers but the questions: whether each one is understood as intended, whether people can answer it from
what they know, and how long it takes. One round of 3–5 interviews finds most serious problems; a second round after
revising the questions confirms the fixes.

## Who takes part

| Role | Why | Survey version |
|---|---|---|
| A software engineer on the system | Longest survey; most technical questions | Engineering (ENG) |
| An operations or platform engineer | Hosting and operations questions | Operations (OPS) |
| A business stakeholder | Least technical vocabulary; tests plain language | Business (BUS) |
| Someone from Finance | Cost and funding questions; tests the hosting economics wording | Finance (FIN) |
| Optional: a product manager or a technology leader | Product (PRD) or Technology leadership (TEC) | |

Choose people who will **not** take part in the real survey of the same organisation, and who have no stake in the
outcome of a pending decision. Colleagues from another department or a friendly organisation are fine.

## Preparation

1. Create the interviewer sheets — one per group, every question in order, with an estimated answering time:
   ```bash
   mra pretest engagements/acme/engagement.yaml --out pretest/
   ```
   The estimates assume 10 s per grid row, 20 s per choice, 45 s per scenario and 60 s per open question. They are
   assumptions; the pretest replaces them with measured times.
2. Build the forms with `mra forms` in a test account, so participants answer the real form, on their own device.
3. Allow 60–75 minutes per interview: about 20 minutes answering, the rest for probes.

## During the interview

**Think aloud.** Ask the participant to say whatever goes through their mind as they read and answer: *"There are no
wrong answers — we are testing the questions, not you. If something is unclear, that is exactly what we need to
know."* Do not explain any question. If they ask what something means, say *"What do you think it means?"* and
note it.

**Time each page** with a stopwatch, without probing, on a first pass through the page. Write the seconds in
`seconds_measured` for the first question of the page (or per question, if practical).

**Then probe**, page by page, using the standard probes:

| Stage | Probe |
|---|---|
| Comprehension | "In your own words, what is this question asking?" · "What does *{term}* mean to you here?" |
| Retrieval | "How did you arrive at your answer?" · "How sure are you?" · "Would anyone in your role know this?" |
| Judgement | "Was it hard to choose? Between which answers?" · "Did you want to answer something in between?" |
| Response options | "Was your answer among the options?" · "Was 'Don't know' the honest answer anywhere?" |
| Sensitivity | "Was any question uncomfortable to answer honestly? Why?" |

Additional probes for the questions where misunderstanding would matter most:

- **Lead time (AN01)** — "Think of a typical change: where did the time actually go?" The answer drives whether the
  delay is read as process or as coordination between teams.
- **Scenarios** — "Which situation in your own work did you have in mind?" Scenarios fail when people answer for an
  imagined ideal rather than their experience.
- **Preferences and personal impact (page 5)** — "Did it feel safe to answer this page?" · "Did you understand that
  it is optional and never used to weight anyone's answers?"
- **Words that technical and business readers understand differently** — *deployable*, *module*, *release train*,
  *right-size*, *hybrid*, *domain*: ask the business and Finance participants what each means to them.

## Recording

In the sheet, mark each problem in the column of its stage, with a short note in the participant's words. Use one
line per question; leave columns empty where nothing was observed. Also note:

- questions answered "Don't know" by people who should know;
- questions skipped, re-read several times or answered after long hesitation;
- anything the participant expected to be asked and was not.

## Deciding what to change

After each round, list every question with a problem and classify it:

| Classification | Rule | Action |
|---|---|---|
| **Serious** | Misunderstood, or unanswerable for the intended group, by two or more participants — or by one participant in a way that would reverse the answer | Rewrite, re-test in the next round |
| **Moderate** | Hesitation, a missing option, or a term needing explanation | Rewrite or add a short clarification |
| **Minor** | Wording preference, one participant | Note; change only if trivial |

Timing: if a group's median measured time exceeds the time promised on the cover screen (*"about 15 minutes"*), either
change the promise or shorten that group's survey — remove questions with the weakest contribution first (questions
that are not used by any decision rule, then those with the most "Don't know" answers). Never cut the "Don't know"
option to save time.

## Applying changes

1. Edit the question in `instrument/items.csv` (or its options); keep the item id unless the meaning changes —
   then retire the id and add a new one.
2. Run `mra validate` and `pytest`.
3. Record what changed and why in the pilot log (`docs/pilot/pilot-log.yaml`), with the round number.
4. Re-test serious changes in the next round.
