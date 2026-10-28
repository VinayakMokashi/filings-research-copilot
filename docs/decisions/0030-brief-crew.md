# ADR-0030: Write briefs with a crew: a Self-Discover plan, the specialists as writers, the validator as critic

- **Status:** Accepted
- **Date:** 2026-10-28
- **Phase:** 7

## Context

The router has recognised requests for briefs since Phase 5 (ADR-0017), and until now answered them with a note to ask about one part at a time; `POST /v1/brief` was deferred to this step (ADR-0020). A brief asks for several things at once (results, segments, risks, liquidity), each found on other pages, so a single retrieval and answer serve it poorly, and whatever writes it must keep the copilot's guarantees: every sentence cites a source, and a check reads it against that source.

## Options considered

| Option | Pros | Cons |
|---|---|---|
| The doc agent or the hybrid answering the whole request at once | No new code; one retrieval | One context for several topics; answers in a few sentences |
| **A crew: a Self-Discover plan, the specialists writing sections in parallel, the validator's checker as critic, an editor's summary** | Each section gets its own retrieval and sources; every sentence is checked; the existing agents do the writing | Every section is a full specialist answer and a check: about $0.015 and 90 seconds a brief |
| A crew with a jury of small models judging each section | More independent checks | The critic already checks every sentence; Groq's free tier can't carry more small-model calls |

## Decision

The brief route runs the crew (`copilot.agents.brief`): one strong-model call plans two to five sections from a fixed list of analyst's modules (Self-Discover's select, adapt and implement), the doc agent and the hybrid write them in parallel, the validator's checker cuts what their sources don't support and drops a section left empty, the sources are numbered once for the brief, and an editor writes a checked summary. `POST /v1/brief` asks for the route directly and streams the crew's steps; the chat has a "Write a brief" switch. A brief is cached apart from answers.

## Evidence

[The brief crew](../eval/brief-crew.md), 12 brief requests of the project's own on dev companies, graded by the evaluation's judge:

- **The crew:** 0.863 of rubric items covered (0.754 to 0.963), 0.916 of sentences supported by their sources, $0.015 and 91 seconds a brief; a second judge (gpt-oss-120b) agrees with the first on 54 of 57 items (kappa 0.70).
- **Against the doc agent answering each request in one shot,** under the same critic (the hybrid sends one-company, one-year questions to the doc agent alone, so its one shot is the same system): rubric 0.658, sentences supported 0.764, 3.0 distinct sources, 97 words, $0.004; the crew's lead on coverage, +0.20, isn't significant on 12 briefs (p = 0.18), its lead on sources is (+4.1, p = 0.0008). The one shot refused 2 of the 12 requests; among the ten it answered, its sentences are supported as often as the crew's (0.917 against 0.929).

## Consequences

- A brief costs about three times an answer, and counts once against the daily quotas; Phase 8 may count it as more.
- The critic's calls run on the `small` role, Groq's free tier, which a set of 12 briefs nearly filled for a day.
- The crew's three failure modes are measured and named: a section the critic empties, a module adapted for the wrong kind of company (a bank's capital as a manufacturer's liquidity), and a list the doc agent won't give. Each is a place to improve: a revision before a cut, modules by industry, and a prompt that allows lists.

## References

- Zhou et al., [Self-Discover: Large Language Models Self-Compose Reasoning Structures](https://arxiv.org/abs/2402.03620), 2024.
- [ADR-0019](0019-validator-loop.md), the validator; [ADR-0020](0020-api-and-streaming.md), the API; the [research briefs guide](../concepts/research-briefs.md).
