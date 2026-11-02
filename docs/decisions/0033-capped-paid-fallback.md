# ADR-0033: When Groq refuses a call, answer on Cerebras until a daily cap

- **Status:** Accepted
- **Date:** 2026-11-02
- **Phase:** 8

## Context

The public demo runs on Groq's free tier ([ADR-0031](0031-google-cloud-topology.md)). Each of its models allows about 200,000 tokens a day and about 8,000 tokens a minute. A doc answer uses about 12,300 tokens across models, so the daily quota covers a few dozen answers, and two visitors asking in the same minute can exhaust a model's minute.

An interactive run doesn't wait for a quota: the API makes one attempt and apologises. Below that, though, LiteLLM retried a refused call twice with a back-off. Measured with a refused call: 3 attempts and 5 seconds before the refusal reached the API.

The owner chose to pay for answers when Groq refuses, within a cap: at most $0.50 a day on Cerebras, which serves the same open weights ([ADR-0024](0024-second-provider.md)).

## Options considered

| Option | For | Against |
|---|---|---|
| Groq only | Free; the quotas bound spending by themselves | A visitor can be turned away on a busy minute even with the day's quota unspent |
| LiteLLM's fallback chain (`FRC_LLM_FALLBACK_MODELS`) | Already in the gateway | No cap: it can't count spending across instances. It falls back on every failure, and it uses one chain for every role, while Cerebras serves no gpt-oss-20b |
| A paid Groq tier | One provider | Spending is limited only by the provider's monthly limit, not per day |
| **A wrapper that sends quota refusals to the same role on Cerebras while the day's spend is under a cap kept in Firestore** | Pays only for the answers the free tier refuses, with a hard daily ceiling shared by every instance | Spending outside Google's budget; an answer may mix providers |

## Decision

- **What falls back.** Only calls the role's own model refused for quota reasons: a rate limit, or Groq's spend limit. A bad request or an outage would spend money to fail again, so it doesn't fall back.
- **Where.** Each role goes to its own paid model, all set in `FRC_LLM_PAID_*_MODEL`:

  | Role | Groq | Cerebras |
  |---|---|---|
  | `strong` | gpt-oss-120b | gpt-oss-120b |
  | `fast` | Qwen3.8 27B | Qwen3.8 27B, without reasoning (ADR-0024) |
  | `small` | gpt-oss-20b | gpt-oss-120b, since Cerebras has no 20b |

- **The cap.** `FRC_LLM_PAID_DAILY_USD`, 0.5 in the deployment, 0 (off) everywhere else.
  - The day's spend is kept in Firestore, as `paid_usd` in the same `quotas/<day>` document as the question counts, so it resets at midnight UTC and expires with them.
  - It is read before each paid call. A paid call whose price LiteLLM doesn't know counts as $0.01, so the cap still holds.
  - If the spend can't be read, nothing is spent.
- **When the paid call fails too,** the caller sees Groq's refusal, so the visitor gets the usual apology.
- **No waiting.** With the fallback on, LiteLLM doesn't retry rate limits (`RateLimitErrorRetries=0`): a refused call reaches the fallback at once. Measured, again with a refused call: 1 attempt and no delay.
- **Only the API.** Batch runs never fall back, and the fallback sits outside the disk cache. So evaluations stay within one provider, and a Cerebras reply is never replayed as Groq's.
- **Readiness.** With the cap above 0, `/ready` also requires the Cerebras key.

## Consequences

- **The worst case is $0.50 a day,** about $15 a month, billed by Cerebras. Google's budget doesn't see it.
  - Calls already in flight when the cap is reached can pass it by a fraction of a cent each: one API instance runs one copilot run at a time.
  - Turning it off is a Terraform change: set `paid_daily_usd = 0`, which also stops the API reading the key's secret.
- **An answer may mix providers.** Each refused call falls back on its own. The trace shows the model of each call and marks paid calls `fallback_used`, and the logs record each one (`llm.paid_fallback`), so how often it happens can be measured.
- **The visitor's question and the retrieved filing text** go to Cerebras when it answers, as they go to Groq otherwise.
- **The cap also holds while Firestore is unreachable,** since no spend can then be read; the visitor gets the apology.

## References

- [ADR-0024](0024-second-provider.md): Cerebras as a second provider for the same open weights, and its defaults.
- [ADR-0031](0031-google-cloud-topology.md): the topology and the free tier first.
- LiteLLM: [router retry policies](https://docs.litellm.ai/docs/routing#advanced---retry-policies-based-on-error-type).
- `src/copilot/llm/fallback.py`, `tests/test_paid_fallback.py`.
