# Optimising a prompt with DSPy

> Treat a prompt as a parameter, and search for the one that scores best on a metric, instead of rewording it by hand.

**Lands in:** Phase 7 · **Code:** `src/copilot/training/hyde.py`, `scripts/optimise_hyde.py`, `src/copilot/retrieval/rewrite.py` (`HydePrompt`)

## What it is

**DSPy** (Khattab et al., 2023) separates what a model call should do from how it is asked. A **signature** names the inputs and outputs ("question → passage"), a **module** such as `dspy.Predict` turns the signature into a prompt, and an **optimiser** changes the prompt, its instruction and its worked examples, to maximise a **metric** on a set of examples. The prompt becomes something measured and searched for, like a model's weights, rather than written once and reread.

**MIPROv2** (Opsahl-Ong et al., 2024) is the optimiser used here. It asks a second model, the proposer, to write candidate instructions from a description of the program and a few tips; it can also bootstrap worked examples from the training set. It then runs trials: each tries one candidate on a minibatch of the validation set, and a Bayesian optimiser (optuna's TPE sampler) chooses the next candidate from the scores so far; every few trials the leading candidate is scored on the whole validation set, and the best whole-set score wins.

## Why we need it here

The rewrites behind the doc agent's search were written by hand in Phase 3 (ADR-0012), and HyDE's passage is one of the four rankings its search fuses. If a better instruction made the passages land nearer the evidence, retrieval would improve with no model or index to change. And HyDE can be scored without reference answers: the synthetic pairs say which chunk answers each question, so a passage is good when that chunk ranks high as it searches.

## How it works

1. **Examples:** the synthetic pairs about training filings, 100 to train on and the 104 of the 20 filings step 7.1 held out to validate; no FinanceBench question.
2. **The metric:** embed the passage as a passage (bge-small, as the doc agent searches with HyDE), rank the filing's chunks by it, and score the reciprocal rank of the answering chunk, counted to ten.
3. **The program:** `dspy.Predict` over the signature "question → passage", starting from the hand-written instruction.
4. **The search:** MIPROv2's light mode, over the instruction only, with gpt-oss-120b proposing and Qwen3.8 27B writing passages, both on Cerebras. Worked examples, and a proposer that reads the training questions, are left out: either would put the pairs' questions, which come from FinanceBench's filings, into a prompt that would have to be committed and shipped.
5. **The result** is exported as a `HydePrompt` (`hyde-2.json`) and scored again in this project's own message format, since DSPy's adapter wraps the instruction in field markers the copilot doesn't use.

## Where it lives in the code

| Piece | What it does |
|---|---|
| `copilot.training.hyde` | Examples and their split, the chunk index, the metric, the exported prompt |
| `scripts/optimise_hyde.py` (`poe optimise-hyde`) | Embeds the filings, scores the hand-written prompt, runs MIPROv2, scores its result |
| `copilot.retrieval.rewrite.HydePrompt` | Another HyDE prompt, loaded from JSON, used wherever HyDE runs |
| `poe run-retrieval --hyde-prompt FILE --cache NAME` | The doc agent's retrieval with another HyDE prompt, its new calls in a cache of their own |

## How we measured it

On the validation set ([report](../eval/dspy-hyde.md)), no candidate beat the hand-written instruction: 0.498 reciprocal rank on a full pass against 0.497 for the best of three proposals, and MIPROv2 returned the hand-written one. The minibatch scores swung from 0.40 to 0.55 over nine trials, which is why the decision rests on whole-set passes. With nothing better found, nothing went to FinanceBench dev, and the prompt stays ([ADR-0028](../decisions/0028-dspy-hyde.md)).

## Pitfalls we hit

- **An optional dependency.** MIPROv2 needs optuna, which `dspy` alone doesn't install; the first run proposed its instructions and stopped at the first trial. The development tools now pin `dspy[optuna]`.
- **A proposer that reads the data.** By default MIPROv2's proposer summarises the training set and its instructions quote it: the first run's drafts named figures and lenders from training questions. Turned off, so nothing derived from the pairs can reach a prompt; one draft still came with a worked example of its own invention.
- **Misread tasks.** Two of three proposals told the model to retrieve "the single most relevant passage" from a corpus it never sees. A search is only as good as its candidates, and a light run has few.
- **Minibatch noise.** 35-question minibatches put the same instruction 0.08 apart; only whole-set passes are worth comparing.

## Review questions

1. What does DSPy optimise, and why must the metric be computed without the model being optimised?
2. Why does a minibatch score need a whole-set pass before a candidate can win?
3. What would worked examples add, and why were they left out here?
4. Why score the exported prompt again in the copilot's own message format?

## References

- Khattab et al., [DSPy: Compiling Declarative Language Model Calls into Self-Improving Pipelines](https://arxiv.org/abs/2310.03714), 2023.
- Opsahl-Ong et al., [Optimizing Instructions and Demonstrations for Multi-Stage Language Model Programs](https://arxiv.org/abs/2406.11695), 2024.
- Akiba et al., [Optuna: A Next-generation Hyperparameter Optimization Framework](https://arxiv.org/abs/1907.10902), 2019.
- [DSPy documentation](https://dspy.ai/).
