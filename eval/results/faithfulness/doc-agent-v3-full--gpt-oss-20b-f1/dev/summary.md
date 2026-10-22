# faithfulness: doc-agent-v3-full--gpt-oss-20b-f1 (dev)

94 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-21 15:46 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| faithful | 0.691 | 0.596 to 0.777 |
| supported_share | 0.813 | 0.743 to 0.874 |

## By question type

| Question type | Questions | faithful | supported_share |
|---|---|---|---|
| domain-relevant | 32 | 0.438 (0.28 to 0.62) | 0.711 (0.60 to 0.82) |
| metrics-generated | 31 | 0.903 (0.81 to 1.00) | 0.919 (0.82 to 1.00) |
| novel-generated | 31 | 0.742 (0.58 to 0.87) | 0.812 (0.68 to 0.92) |

## System

```json
{
  "answers_run": "doc-agent-v3-full",
  "citation_precision": 0.8643,
  "citations": 258,
  "judge_errors": 0,
  "judge_model": "groq/openai/gpt-oss-20b",
  "judge_tokens": 151332,
  "prompt_version": "1"
}
```
