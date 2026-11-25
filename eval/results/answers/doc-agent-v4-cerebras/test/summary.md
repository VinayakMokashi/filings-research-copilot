# answers: doc-agent-v4-cerebras (test)

50 questions, 95% bootstrap intervals (10,000 resamples), 2026-11-24 06:17 UTC. The held-out test split was opened for this run.

| Metric | Mean | 95% interval |
|---|---|---|
| answered | 0.960 | 0.900 to 1.000 |
| retried | 0.260 | 0.140 to 0.380 |
| uncited | 0.000 | 0.000 to 0.000 |
| context_hit | 0.720 | 0.600 to 0.840 |
| cites_evidence | 0.620 | 0.480 to 0.740 |

## By question type

| Question type | Questions | answered | retried | uncited | context_hit | cites_evidence |
|---|---|---|---|---|---|---|
| domain-relevant | 16 | 1.000 (1.00 to 1.00) | 0.250 (0.06 to 0.50) | 0.000 (0.00 to 0.00) | 0.688 (0.44 to 0.88) | 0.625 (0.38 to 0.88) |
| metrics-generated | 17 | 0.882 (0.71 to 1.00) | 0.294 (0.12 to 0.53) | 0.000 (0.00 to 0.00) | 0.941 (0.82 to 1.00) | 0.765 (0.53 to 0.94) |
| novel-generated | 17 | 1.000 (1.00 to 1.00) | 0.235 (0.06 to 0.47) | 0.000 (0.00 to 0.00) | 0.529 (0.29 to 0.76) | 0.471 (0.24 to 0.71) |

## System

```json
{
  "agent": "understood filings, three rewrites, fused dense search, page chunks",
  "answer_model": "cerebras/gpt-oss-120b",
  "calculation_errors": 0,
  "context_budget_tokens": 3000,
  "invalid_citations": 0,
  "limit": null,
  "mean_completion_tokens": 657,
  "mean_prompt_tokens": 5291,
  "prompt_version": "2",
  "retry": "on a refusal, search for what is missing across the company's filings",
  "retry_budget_tokens": 4500,
  "rewrite_model": "cerebras/qwen-3.8-27b"
}
```
