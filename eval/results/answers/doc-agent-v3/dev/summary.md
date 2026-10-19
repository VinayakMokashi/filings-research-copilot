# answers: doc-agent-v3 (dev)

10 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-19 18:00 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| answered | 0.900 | 0.700 to 1.000 |
| retried | 0.200 | 0.000 to 0.500 |
| uncited | 0.100 | 0.000 to 0.300 |
| context_hit | 0.700 | 0.400 to 1.000 |
| cites_evidence | 0.500 | 0.200 to 0.800 |

## By question type

| Question type | Questions | answered | retried | uncited | context_hit | cites_evidence |
|---|---|---|---|---|---|---|
| domain-relevant | 4 | 1.000 (1.00 to 1.00) | 0.000 (0.00 to 0.00) | 0.000 (0.00 to 0.00) | 0.750 (0.25 to 1.00) | 0.500 (0.00 to 1.00) |
| metrics-generated | 4 | 0.750 (0.25 to 1.00) | 0.500 (0.00 to 1.00) | 0.000 (0.00 to 0.00) | 0.750 (0.25 to 1.00) | 0.500 (0.00 to 1.00) |
| novel-generated | 2 | 1.000 (1.00 to 1.00) | 0.000 (0.00 to 0.00) | 0.500 (0.00 to 1.00) | 0.500 (0.00 to 1.00) | 0.500 (0.00 to 1.00) |

## System

```json
{
  "agent": "understood filings, three rewrites, fused dense search, page chunks",
  "answer_model": "groq/openai/gpt-oss-120b",
  "calculation_errors": 0,
  "context_budget_tokens": 3000,
  "invalid_citations": 0,
  "limit": 10,
  "mean_completion_tokens": 702,
  "mean_prompt_tokens": 5037,
  "prompt_version": "2",
  "retry": "on a refusal, search for what is missing across the company's filings",
  "retry_budget_tokens": 4500,
  "rewrite_model": "groq/qwen/qwen3.8-27b"
}
```
