# Semantic caching

> Serve a stored answer when a question has been answered before; the hard part is knowing when two questions are the same.

**Lands in:** Phase 6 · **Code:** `src/copilot/api/cache.py`; `scripts/eval_semantic_cache.py`

## What it is

A model call costs time, money and quota, and people ask the same things. A **cache** keeps each answer under its question and serves it again when the question comes back. An exact cache matches the question's text; a **semantic cache** embeds the question and serves the stored answer whose question is nearest in embedding space, above a similarity threshold, so a rewording hits as well as a repeat. GPTCache popularised the idea for LLM applications.

The risk is the mirror of the gain. Two questions can be close in embedding space and still ask for different things, and a hit then serves the wrong answer, confidently and instantly.

## Why we need it here

On the free tier each model allows about 200,000 tokens a day, a few dozen answers. Demo visitors click the suggested questions, so the same questions arrive again and again. Every repeat served from a cache is a doc agent's run, about 7,000 tokens, kept for a new question.

## How we measured it

Before building one, we measured what a semantic cache would serve, on the [routing set](../data/routing-set.md)'s doc, data and hybrid questions, embedded with bge-small as the semantic router embeds them (`poe eval-semantic-cache`):

- **Should hit:** pairs from one seed group, a seed and its two reviewed paraphrases, which ask the same thing in different words.
- **Must miss:** each question with its measure swapped for another ("operating income" for "revenue"), the same company, years and every other word.
- **Must miss:** questions from different seed groups that name the same companies and years.

A hit needed the same companies, years, quarters and dates as well as the similarity threshold ([dev](../../eval/results/cache/similarity/dev/summary.md), [test](../../eval/results/cache/similarity/test/summary.md)):

| Threshold | Dev: paraphrases hit (of 81) | Dev: measure swaps hit (of 104) | Test: paraphrases hit (of 39) | Test: measure swaps hit (of 52) |
|---|---|---|---|---|
| 0.85 | 73 | 102 | 37 | 52 |
| 0.90 | 53 | 89 | 29 | 43 |
| 0.93 | 37 | 67 | 14 | 36 |
| 0.95 | 16 | 42 | 7 | 29 |
| 0.97 | 7 | 10 | 1 | 2 |

**At every threshold that lets paraphrases through, a swapped measure is more likely to hit than a paraphrase.** "Hey, can you tell me if Boeing's revenue bounced back after 2020 and what reasons the company lists in its 10-K filing?" and its operating-income twin sit at 0.976, while a seed and its own paraphrases have a median similarity of 0.926 on dev. Embeddings measure what a question is about, here Boeing after 2020, and the measure is one word among many. The same-cue questions from other seed groups never hit, because they differ in more words.

Requiring the same measures too, read from a list of terms, removes the swaps, but only by construction: the embedding still can't tell them apart, and a question whose measure the list misses, or one that differs in some other single word ("the highest" for "the lowest", "2019" spelled out), would hit as the swaps did.

## How it works

So the copilot caches **exact repeats**, never similar questions:

1. **The key** is the question with case, spacing, curly quote marks and a trailing question mark evened out (`normalise_question`), so "What was 3M's capex?" and "what was 3M’s capex" are one question, and "in 2019" never meets "in 2018".
2. **Only a new conversation from an anonymous caller** is looked up or stored: a follow-up depends on its conversation, and a named user's question may be rewritten from their notes.
3. **Only answers** are stored: never a refusal, a decline, an error or "try again later".
4. **A hit** streams `meta`, an `event` saying where the answer came from and how old it is, the stored `response` marked `cached`, and `done`. It costs no quota, and the turn is written into the new conversation, so a follow-up on that thread builds on it as on any answer.
5. **Answers live for seven days** (`FRC_API_CACHE_DAYS`; 0 turns the cache off), in memory or, with `FRC_API_STATE=postgres`, in a Postgres table.

## Where it lives in the code

| Piece | What it does |
|---|---|
| `copilot.api.cache.normalise_question` | The key: one question however it is cased, spaced or quoted |
| `copilot.api.cache.MemoryCache`, `PostgresCache` | The stored answers, with their time to live |
| `copilot.api.cache.reusable` | Whether a response may be served again |
| `copilot.api.app.admit` | A stored answer for a repeated question, else the question counted against the quotas |
| `copilot.agents.runner.Copilot.record` | A served answer added to its conversation without a run |
| `scripts/eval_semantic_cache.py` (`poe eval-semantic-cache`) | The measurement above, for any threshold and split |

## Pitfalls we hit

- **Similar is not the same.** The design we set out to build, a semantic cache, would have answered operating-income questions with revenue answers; measuring it first, on pairs we could label, is what showed it.
- **A cached answer is missing from its conversation.** A hit skips the graph, so the checkpointer never saw the turn and a follow-up would lose its context; the answer is now recorded into the conversation when it is served.
- **The quota check ran first.** A repeated question would have counted against the visitor's quota although it cost nothing; the cache lookup now comes before the quota.

## Review questions

1. Why do embeddings place "revenue" and "operating income" versions of the same question closer together than two paraphrases of one question?
2. Why would a list of measures in the cache key not be enough on its own?
3. Why are follow-ups and named users' questions never served from the cache?
4. What must happen to a conversation when its first answer comes from the cache?

## References

- Zilliz, [GPTCache](https://github.com/zilliztech/GPTCache), a semantic cache for LLM applications.
- The [semantic routing guide](semantic-routing.md), where the same embeddings group questions by topic rather than by what they ask.
- The [SSE streaming guide](sse-streaming.md) for the events a hit streams.
