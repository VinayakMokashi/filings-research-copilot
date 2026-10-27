# answers: doc-agent-v4-cerebras (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-27 01:55 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| answered | 0.930 | 0.880 to 0.980 |
| retried | 0.190 | 0.120 to 0.270 |
| uncited | 0.010 | 0.000 to 0.030 |
| context_hit | 0.710 | 0.620 to 0.800 |
| cites_evidence | 0.630 | 0.540 to 0.720 |

## By question type

| Question type | Questions | answered | retried | uncited | context_hit | cites_evidence |
|---|---|---|---|---|---|---|
| domain-relevant | 34 | 0.941 (0.85 to 1.00) | 0.206 (0.09 to 0.35) | 0.000 (0.00 to 0.00) | 0.676 (0.53 to 0.82) | 0.647 (0.47 to 0.79) |
| metrics-generated | 33 | 0.970 (0.91 to 1.00) | 0.152 (0.03 to 0.27) | 0.030 (0.00 to 0.09) | 0.909 (0.82 to 1.00) | 0.879 (0.76 to 0.97) |
| novel-generated | 33 | 0.879 (0.76 to 0.97) | 0.212 (0.09 to 0.36) | 0.000 (0.00 to 0.00) | 0.545 (0.39 to 0.73) | 0.364 (0.21 to 0.52) |

## System

```json
{
  "agent": "understood filings, three rewrites, fused dense search, page chunks",
  "answer_model": "cerebras/gpt-oss-120b",
  "calculation_errors": 0,
  "context_budget_tokens": 3000,
  "invalid_citations": 2,
  "limit": null,
  "mean_completion_tokens": 702,
  "mean_prompt_tokens": 4905,
  "prompt_version": "2",
  "retry": "on a refusal, search for what is missing across the company's filings",
  "retry_budget_tokens": 4500,
  "rewrite_model": "cerebras/qwen-3.8-27b"
}
```
