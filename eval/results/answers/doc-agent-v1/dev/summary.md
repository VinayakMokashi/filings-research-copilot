# answers: doc-agent-v1 (dev)

10 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-19 17:41 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| answered | 0.800 | 0.500 to 1.000 |
| retried | 0.000 | 0.000 to 0.000 |
| context_hit | 0.500 | 0.200 to 0.800 |
| cites_evidence | 0.200 | 0.000 to 0.500 |

## By question type

| Question type | Questions | answered | retried | context_hit | cites_evidence |
|---|---|---|---|---|---|
| domain-relevant | 4 | 1.000 (1.00 to 1.00) | 0.000 (0.00 to 0.00) | 0.750 (0.25 to 1.00) | 0.500 (0.00 to 1.00) |
| metrics-generated | 4 | 0.500 (0.00 to 1.00) | 0.000 (0.00 to 0.00) | 0.250 (0.00 to 0.75) | 0.000 (0.00 to 0.00) |
| novel-generated | 2 | 1.000 (1.00 to 1.00) | 0.000 (0.00 to 0.00) | 0.500 (0.00 to 1.00) | 0.000 (0.00 to 0.00) |

## System

```json
{
  "agent": "understood filings, three rewrites, fused dense search, page chunks",
  "answer_model": "groq/openai/gpt-oss-120b",
  "calculation_errors": 0,
  "context_budget_tokens": 3000,
  "invalid_citations": 0,
  "limit": 10,
  "mean_completion_tokens": 460,
  "mean_prompt_tokens": 3839,
  "prompt_version": "1",
  "rewrite_model": "groq/qwen/qwen3.8-27b"
}
```
