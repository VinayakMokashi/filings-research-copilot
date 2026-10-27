# DSPy on the HyDE prompt

Phase 7, step 7.3. Optimisation and validation on synthetic questions about training filings only; nothing reached FinanceBench dev, because the search kept the hand-written prompt.

## Question

HyDE asks the fast model for a passage, in a filing's own words, that would answer the question, and the doc agent searches with that passage (ADR-0012). Its instruction was written by hand. Can DSPy's MIPROv2 find an instruction that makes the passages land nearer the evidence?

## Setup

- **Examples** (`copilot.training.hyde`): the synthetic pairs about training filings. Validation: the 104 pairs of the 20 filings step 7.1 held out. Training: 100 pairs from other filings, whole filings at a time. No FinanceBench question is used.
- **The metric:** the reciprocal rank, counted to ten, of the chunk that answers the question among all of its filing's 480-token chunks, when the passage is the search (bge-small, the passage embedded as a passage, as the doc agent searches with HyDE): 1 at the top, 0 below ten. The 40 filings' 9,291 chunks were embedded once.
- **The search** (`poe optimise-hyde`): MIPROv2 in its light mode, over the instruction alone, with gpt-oss-120b proposing instructions and Qwen3.8 27B (reasoning off, on Cerebras, as the copilot's `fast` role there) writing the passages. Instructions only, and the proposer kept from the training questions: worked examples or an instruction quoting them would carry the pairs' questions, which come from FinanceBench's filings and are never committed.
- **Scoring:** every candidate in DSPy's own message format inside the search (35-question minibatches, and full passes over the validation set), and the result again in this project's own message format against the hand-written prompt.

## Results

| Instruction | Validation, full pass (DSPy's format) |
|---|---|
| **0: the hand-written instruction** | **0.498** (twice) |
| 3: locate "the single most relevant passage" of the filing | 0.497 |
| 1: a long list of rules, with a worked example | minibatches only (0.47, 0.52, 0.54) |
| 2: "retrieve" the passage from a corpus | minibatches only (0.40, 0.52, 0.44) |

The proposer wrote three instructions. Two of them misread the task: they ask the model to retrieve a passage from a corpus it never sees, where HyDE asks it to write one. Over nine trials the minibatch scores ranged from 0.40 to 0.55, noise on 35 questions; on the full validation set no candidate beat the hand-written instruction, and MIPROv2 returned it.

In this project's own format, the hand-written prompt scores 0.484 (0.419 to 0.551) on validation and 0.528 (0.455 to 0.603) on training. The same instruction exported as DSPy runs it, in the system message alone with the question after it (`hyde-2`), writes much shorter passages (49 words against 76) and scores 0.497 on validation (+0.013, p = 0.68) but 0.459 on training (−0.069, −0.134 to −0.004, p = 0.040). The layout of a prompt changes what the model writes as much as its wording does, and here the hand-written layout is the better of the two.

## Decision

**Keep the hand-written HyDE prompt** ([ADR-0028](../decisions/0028-dspy-hyde.md)). The search found nothing better on held-out filings, so there was nothing to carry to FinanceBench dev, and the rule for Phase 7 is to adopt only on a significant gain there. What stays is the means to try again: `HydePrompt` and `--hyde-prompt` swap in another prompt anywhere HyDE runs, `CachedLLM(also_read=...)` lets such a run replay the other rewrites without writing to their cache, and `poe optimise-hyde` runs the search. DSPy is a development tool only; the service images don't install it.

**Limits:** MIPROv2's light mode (four instructions, nine trials); no worked examples, which is where DSPy often gains most but which would carry questions this repository doesn't commit; one metric, the evidence chunk's rank within its filing, on synthetic questions, which step 7.1 found easier than people's.

## Logs

- Scores by pair number: [`eval/results/dspy/hyde-1/`](../../eval/results/dspy/hyde-1/) and [`hyde-2/`](../../eval/results/dspy/hyde-2/), train and val.
- The search's log, the candidates and DSPy's cache stay local (`data/cache/dspy`, `data/processed/dspy/`), since the proposer's drafts quote training questions.
- Reproduce ([runbook](../runbooks/training-models.md)):

  ```bash
  FRC_LLM_STRONG_MODEL=cerebras/gpt-oss-120b FRC_LLM_FAST_MODEL=cerebras/qwen-3.8-27b \
  FRC_LLM_TOKENS_PER_MINUTE=100000 uv run poe optimise-hyde
  ```
