# answers: doc-agent-v4-full (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-21 15:48 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| answered | 0.940 | 0.890 to 0.980 |
| retried | 0.160 | 0.090 to 0.230 |
| uncited | 0.030 | 0.000 to 0.070 |
| context_hit | 0.730 | 0.640 to 0.820 |
| cites_evidence | 0.640 | 0.550 to 0.740 |

## By question type

| Question type | Questions | answered | retried | uncited | context_hit | cites_evidence |
|---|---|---|---|---|---|---|
| domain-relevant | 34 | 0.941 (0.85 to 1.00) | 0.176 (0.06 to 0.32) | 0.000 (0.00 to 0.00) | 0.647 (0.47 to 0.79) | 0.588 (0.41 to 0.74) |
| metrics-generated | 33 | 0.939 (0.85 to 1.00) | 0.121 (0.03 to 0.24) | 0.030 (0.00 to 0.09) | 0.939 (0.85 to 1.00) | 0.818 (0.67 to 0.94) |
| novel-generated | 33 | 0.939 (0.85 to 1.00) | 0.182 (0.06 to 0.33) | 0.061 (0.00 to 0.15) | 0.606 (0.45 to 0.76) | 0.515 (0.33 to 0.67) |

## System

```json
{
  "agent": "understood filings, three rewrites, fused dense search, page chunks",
  "answer_model": "groq/openai/gpt-oss-120b",
  "calculation_errors": 0,
  "context_budget_tokens": 3000,
  "invalid_citations": 0,
  "limit": null,
  "mean_completion_tokens": 660,
  "mean_prompt_tokens": 4743,
  "prompt_version": "2",
  "retry": "on a refusal, search for what is missing across the company's filings",
  "retry_budget_tokens": 4500,
  "rewrite_model": "groq/qwen/qwen3.8-27b"
}
```
