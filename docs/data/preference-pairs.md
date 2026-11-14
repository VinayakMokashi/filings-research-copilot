# Data card: preference pairs

| | |
|---|---|
| **What it is** | Pairs of a chosen and a rejected answer to the same prompt, for preference tuning of the answer model |
| **Files** | Not committed. `poe export-preferences` writes `data/processed/preferences/pairs.jsonl` and `pairs-meta.jsonl`, and keeps a copy of the Firestore collections it read under `data/processed/preferences/firestore/` |
| **Sources** | The deployment's ratings (`feedback`) and readers' picks (`preferences`) in Firestore; local evaluation runs of the copilot (`--runs`) |
| **Licence** | Not published. A rated question is a visitor's own. Local runs hold FinanceBench's questions (CC BY-NC 4.0) and the copilot's answers to them, which this project never publishes |
| **Built** | From 2026-11-15, by step 9.2 ([ADR-0035](../decisions/0035-preference-pairs.md)) |
| **Used for** | Preference tuning later; nothing is trained on it yet |

## Fields

`pairs.jsonl`, one pair a line, in TRL's conversational preference format:

| Field | What it holds |
|---|---|
| `prompt` | The answer prompt as chat messages: the doc agent's or the hybrid's instructions as the system message, then the question as read and the numbered sources. When the two answers came from different sources, or the sources weren't kept, only the question, as a user message |
| `chosen` | The better answer, as one assistant message: the text a reader saw |
| `rejected` | The worse answer, the same way |

`pairs-meta.jsonl`, the same line for line:

| Field | What it holds |
|---|---|
| `source` | `retry`, `ratings` or `validator` |
| `labeller` | `a reader`, `readers' ratings`, or `the validator's model` |
| `ids` | The two answers' request ids, or a local run's question id |
| `prompt` | `sources`: the answer prompt rebuilt; `question`: the question alone |

## How the pairs are made

| Source | Chosen | Rejected | Judged by |
|---|---|---|---|
| `retry` | The answer a reader picked over the second answer to its question, or the other way | The other answer; a pick of "neither" makes no pair | A reader |
| `ratings` | An answer rated up | An answer rated down for the same question as read (at most 10 pairs a question) | Readers' ratings |
| `validator` | The revision that passed the validator's check | The draft the check sent back | The validator's model, the `small` role (ADR-0019) |

Pairs whose two answers have the same text are dropped.

## Counts

| Date | `retry` | `ratings` | `validator` | From |
|---|---|---|---|---|
| 2026-11-15 | 0 | 0 | 37 | Copilot v1's and v2's dev runs on the laptop; no rating has come in since the deployment went live |

## Caveats

- **The validator's pairs are judged by a model,** the checker that also decides which drafts to revise. Training on them teaches the answer model what the checker accepts, which is not the same as what readers prefer.
- **The answers are the texts readers saw,** after the calculator filled in the figures, not the model's raw JSON. Tuning the answer model on them would rebuild that format.
- **A pick is one reader's view of one question.** Readers' pairs will be few and uneven across questions; the metadata lets a training run weigh or drop each source.
