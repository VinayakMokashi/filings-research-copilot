# Data card: memory set

| | |
|---|---|
| **What it is** | 10 short conversations from 6 users, 20 turns in all: each turn says what its standalone form must name, and each user's notes have terms they should and shouldn't mention |
| **Files** | [`eval/memory/conversations.jsonl`](../../eval/memory/conversations.jsonl), [`eval/memory/notes.jsonl`](../../eval/memory/notes.jsonl) |
| **Licence** | MIT, like the rest of the repository; written for this project |
| **Built** | 2026-10-23; the notes checks extended on 2026-10-24 |
| **Used for** | Follow-up rewriting and the notes kept about users (step 5.5): `poe run-memory` ([guide](../concepts/agent-memory.md)) |

## What's in it

A conversation is a list of turns, each with:

- the question as the user asks it;
- a short written answer, standing in for the copilot's, so that the set tests memory rather than answering;
- its kind: `standalone`, `follow-up` (it depends on earlier turns) or `from notes` (it depends on what an earlier conversation taught);
- the companies, years and terms its standalone form must name, and only those companies.

| Kind | Turns | Example |
|---|---|---|
| `standalone` | 11 | "Compare Coca-Cola's and PepsiCo's net income in 2022." must come back as asked |
| `follow-up` | 7 | "And what was its revenue that year?" after a question about Netflix's 2022 10-K must name Netflix and 2022 |
| `from notes` | 2 | "How did their operating income change from 2021 to 2022?", in a new conversation, from a user who said they follow Netflix |

The users test different things:

| User | Conversations | What it tests |
|---|---|---|
| u1 | 2 | A followed company and a unit preference, both stated, then used in a new conversation |
| u2 | 2 | A stated role ("I cover Boeing as an analyst"), then "the company" in a new conversation |
| u3 | 1 | Two companies in one question, a follow-up that keeps both, and thanks that must stay as they are |
| u4 | 1 | A switch from 3M to Amcor: the follow-up must take the latest company, not the first |
| u5 | 2 | A length preference stated with a question, then a question about another company |
| u6 | 2 | A followed company that the user later replaces: the old note must go |

## The notes checks

`notes.jsonl` lists, for each user, terms their final notes should mention (`present`) and terms they shouldn't (`absent`). A check is a case-insensitive substring test over the user's notes joined together.

- **First version, 6 checks:** Netflix, billion, Boeing, short and AMD present; "follows Intel" absent.
- **Second version, 15 checks (2026-10-24):** the first run's notes passed all 6, but they also said that users followed companies they had only asked about, and gave one user a preference they never stated. The second version adds those as `absent` terms: the companies u3, u4 and u5 only asked about, and "concise" and "737" for u2. It also expects "analyst" for u2. **These checks were written after reading the first run's notes,** so they and the second extraction prompt share that knowledge; a run on a fresh set would test the prompt more fairly.

## Limits

- **Small.** Twenty turns and six users: the intervals are wide, and one turn moves a rate by five points.
- **Written answers.** The answers are short stand-ins, so a rewrite never sees the copilot's real, longer replies.
- **Term checks are proxies.** They catch a named company or word, not a paraphrase of it: "prefers brief replies" would pass the "concise" check.
- **English, and one style of user.** Every user states facts plainly; none jokes, hedges or changes their mind mid-sentence.
