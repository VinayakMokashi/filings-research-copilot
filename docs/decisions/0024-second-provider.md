# ADR-0024: Finish Phase 5's evaluations on a second provider, with each model called as it was measured

- **Status:** Accepted
- **Date:** 2026-10-27
- **Phase:** 5

## Context

Every evaluation so far ran on Groq's free tier, which allows about 200,000 tokens a day for each model. Phase 5's last work, the copilot's end-to-end run over FinanceBench's 100 dev questions and four judging passes over its answers, needs well over a million tokens. Shared with the other Phase 5 runs, the daily caps had stretched those runs over three days, and the end-to-end run had answered fewer than a fifth of its questions. Groq's paid plan wasn't taking new sign-ups.

Cerebras serves two of the gateway's three models, from the same open weights: gpt-oss-120b (the `strong` role) and Qwen3.8 27B (the `fast` role, which is also the judges' model). It doesn't serve gpt-oss-20b (the `small` role, the validator's checker).

Open weights don't make two providers' models interchangeable, because each provider chooses its own defaults, and the first check found one that matters. Groq's Qwen3.8 27B answers without reasoning, while Cerebras's reasons at high effort unless told not to. When the doc agent's 100 dev answers were graded again on Cerebras, the correctness judge's median reply grew from 41 completion tokens to 194, and 9 replies ran out of tokens before the verdict. The faithfulness check lost 31 of its 94 replies the same way. An unreadable verdict counts against the answer, so the same answers scored 0.61 correct instead of 0.65 and 0.52 faithful instead of 0.63: the measuring instrument had changed, not the answers.

## Options considered

| Option | Pros | Cons |
|---|---|---|
| Stay on Groq's free tier | Every number from one provider | Days more for the end-to-end run and its judges, with the next phases waiting |
| Move every role to Cerebras by default | One provider for the new runs | No gpt-oss-20b on Cerebras; every earlier result came from Groq; the demo's provider is Phase 8's choice |
| A larger output budget for Cerebras's Qwen, reasoning left on | No new setting | A different judge from the one behind every earlier result: slower, costlier, and with different verdicts |
| **Cerebras for the strong and fast roles in these runs, each model called as it was measured, comparisons kept within one provider** | Hours instead of days, and the judge stays the same instrument | The gateway has to know each provider's defaults, and costs differ by provider |

## Decision

1. **The remaining Phase 5 runs use Cerebras for the `strong` and `fast` roles.** Each run sets them in its environment (`FRC_LLM_STRONG_MODEL=cerebras/gpt-oss-120b`, `FRC_LLM_FAST_MODEL=cerebras/qwen-3.8-27b`). The configured defaults stay on Groq, and the `small` role stays on Groq's gpt-oss-20b.
2. **Each model is called the way it was measured.** `MODEL_PARAMS` in the gateway holds the settings sent with every call to a model, and Qwen on Cerebras gets `reasoning_effort: "none"`, as Groq serves it. gpt-oss-120b reasons at medium effort on both providers by default, so it needs no setting. The settings are part of the cache key, so a reply made under other settings is never replayed. Calls without settings keep their keys, so every cached Groq reply still replays.
3. **Comparisons stay within one provider.** A run on Cerebras is compared with a baseline graded by the same judge on Cerebras. Where the answers themselves come from different providers, the baseline is answered again on the new one. The doc agent's 100 dev answers, graded again by the Cerebras judges, are the end-to-end run's baseline.
4. **A judge moved to another provider is checked first.** `poe compare-judges` on the doc agent's dev answers shows whether the two copies' verdicts agree as closely as one judge's would.

## Evidence

The doc agent's dev answers (Phase 3), graded by Qwen3.8 27B on Groq and on Cerebras with reasoning off ([results](../../eval/results/judge-agreement/)):

| | Answers | Agree | Cohen's kappa | Positive, Groq / Cerebras | Unreadable replies |
|---|---|---|---|---|---|
| Correctness, prompt 2 | 100 | 0.99 | 0.98 (0.93 to 1.00) | correct 0.65 / 0.64 | 0 / 0 |
| Faithfulness, prompt 1 | 94 | 0.97 | 0.93 (0.84 to 1.00) | faithful 0.63 / 0.62 | 0 / 0 |

With Cerebras's default reasoning, the same comparisons agreed on 0.94 (kappa 0.88) and 0.83 (kappa 0.66) of the answers, with 9 and 31 unreadable replies. Faithful answers fell to 0.52 (McNemar p = 0.021).

- **Tests:** the router's deployment of Cerebras's Qwen carries the setting, and the other deployments don't. A cached reply for Cerebras's Qwen made without the setting isn't replayed, while a Groq reply's key is unchanged.
- **Live:** the same prompt drew 84 completion tokens with reasoning from Cerebras's Qwen by default, and 22 without. gpt-oss-120b on Cerebras gave the same reply with no setting and with medium effort, as gpt-oss-20b does on Groq.

## Consequences

- **The end-to-end run takes hours instead of days.** Only the validator's checks still wait on Groq's daily cap for gpt-oss-20b.
- **Prices differ by provider.** Per million tokens, gpt-oss-120b costs $0.35 in and $0.75 out on Cerebras, against $0.15 and $0.60 on Groq. Qwen3.8 27B costs $0.99 and $1.49, against $0.80 and $4.00. Reports say which provider a cost comes from.
- **Results name their provider** through the model id: a Cerebras judge's results are `qwen-3.8-27b-p2`, and Groq's `qwen3.8-27b-p2`.
- **Another provider means another check.** A new provider, or a new model version, can bring other defaults; `poe compare-judges` and a look at reply lengths find them.
- **Groq's default for gpt-oss-120b is inferred, not documented.** Its docs list the efforts without naming a default, and gpt-oss-20b on Groq gives the same reply with no setting and with medium effort.

## References

- Cerebras, [Reasoning](https://inference-docs.cerebras.ai/capabilities/reasoning).
- Groq, [Reasoning](https://console.groq.com/docs/reasoning).
- [ADR-0005](0005-llm-gateway.md) and the [LLM gateway guide](../concepts/llm-gateway.md).
