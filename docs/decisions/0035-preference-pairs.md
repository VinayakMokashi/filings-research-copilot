# ADR-0035: Keep each rated answer with what produced it, and turn ratings into preference pairs

- **Status:** Accepted
- **Date:** 2026-11-15
- **Phase:** 9

## Context

The web UI's thumbs reach `POST /v1/feedback` as a conversation's id, a turn number, a rating and an optional comment. That says that an answer was liked or not, but not which answer. The conversation lives in the API's memory (ADR-0031) and is gone when the instance stops, so the rating can't be traced back to a question, an answer or the model that wrote it.

Step 9.2 asks for feedback stored as **preference pairs**: the same prompt with a chosen and a rejected answer, the input that preference tuning such as DPO (Rafailov et al., 2023) learns from.

The constraints:

- **Traffic is low.** From 3 to 15 November the live API answered 3 questions and received no rating, so pairs from visitors will come slowly, and any other source of pairs matters.
- **Privacy.** A visitor's question can say anything. Keeping every question would keep far more than the ratings need.
- **The licence.** Answers to FinanceBench's questions are never published (CC BY-NC 4.0), wherever they come from.
- **One API instance.** It holds conversations in memory and runs one answer at a time (ADR-0031).

## Options considered

| Option | Pros | Cons |
|---|---|---|
| Store every exchange in Firestore when it is served, with an expiry | Survives a restart; a late rating still finds its answer | Keeps every visitor's question for a day, rated or not |
| **Keep recent exchanges in the API's memory; store one only when it is rated** | Nothing is kept unless a visitor rates it; no extra writes | A rating after the instance stopped finds no exchange |
| The UI sends the exchange with its rating | No server state | The API would store what a client says it served; the MCP server's clients couldn't rate |
| Pairs only from visitors (retries and ratings) | All human-judged | Very few at this traffic |
| **Also the validator's failed draft against its passing revision** | Many, from every revised answer; they cost nothing | Judged by a model, not a person, so labelled apart |
| An LLM judge comparing two answers | As many pairs as wanted | A judge's preferences, with its biases, presented as a reader's |

## Decision

1. **The API remembers what it served.** For each answer it keeps the exchange in memory, the newest 256:
   - the question as asked and as read, the route, and the arm that wrote it (ADR-0029);
   - the answer, its citations, and the numbered sources it was written from;
   - the validator's verdict and its first draft, read from the graph's checkpoints;
   - the models, the tokens and the cost, from the run's usage events.

   Nothing reaches storage unless it is rated.
2. **A rating keeps its exchange.** `POST /v1/feedback` finds the exchange by the answer's request id and stores both in `feedback/<id>`, with no expiry, as ratings were. If the instance has restarted since, the rating is stored alone and flagged.
3. **"Try another answer."** After a thumbs down on a doc or hybrid answer, the UI asks for a fresh answer to the same question (`POST /v1/ask` with `retry_of`, the first answer's request id):
   - **the question as the copilot read it,** on the same route, in a new conversation, so the visitor's own conversation is unchanged;
   - **written by another arm.** The bandit chooses it on Cerebras when it is on and under its cap (ADR-0036); otherwise it is another of the three settings on Groq's free tier;
   - **never from the cache, and never into it,** and counted against the quotas like any question.

   The visitor then picks the better answer, or neither, and `POST /v1/preference` keeps both exchanges and the pick in `preferences/<id>`.
4. **`poe export-preferences`** reads both collections, and with `--runs` the drafts of local evaluation runs. It writes TRL's conversational preference format, `prompt`, `chosen` and `rejected`, to a git-ignored file. The prompt is the answer prompt rebuilt with the sources the answers were written from. A metadata file beside it gives each pair's source and labeller. The three sources:
   - **a retry's pick:** a visitor compared the two answers;
   - **opposite ratings of the same question as read:** an answer rated up against one rated down;
   - **the validator's draft that failed its check against the revision that passed:** labelled as judged by a model.
5. **The UI says what a rating keeps:** the question, the answer and how it was made, and nothing that identifies the visitor.

## Consequences

- **A rated question is kept without an expiry.** No address or visitor id is stored with it. The conversation's id is random.
- **Firestore:** a few kilobytes a rating, up to about 25 KB with the sources, which is far inside the free tier.
- **A retry costs an answer.** It uses the visitor's quota and, with the bandit on, money inside the bandit's cap.
- **Answers to FinanceBench's questions stay local.** The validator's pairs from evaluation runs, and any FinanceBench question a visitor rates, reach only the git-ignored export.
- **Pairs from visitors will be few at this traffic,** and the validator's will dominate. The export names every pair's source, so training can weigh or drop them.
- **The chosen and rejected answers are the texts readers saw,** after the calculator filled in the figures, not the model's raw JSON. Tuning the answer model on them would rebuild that format.

## References

- Rafailov et al., [Direct Preference Optimization: Your Language Model is Secretly a Reward Model](https://arxiv.org/abs/2305.18290), NeurIPS 2023.
- Hugging Face TRL, [dataset formats](https://huggingface.co/docs/trl/dataset_formats) (preference, conversational).
- [ADR-0019](0019-validator-loop.md) (the validator's loop), [ADR-0029](0029-bandit-routing.md) (the arms), [ADR-0031](0031-google-cloud-topology.md) (one API instance, Firestore).
