# faithfulness: doc-agent-v4-full--gpt-oss-20b-f1 (dev)

94 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-21 15:54 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| faithful | 0.681 | 0.585 to 0.777 |
| supported_share | 0.794 | 0.721 to 0.859 |

## By question type

| Question type | Questions | faithful | supported_share |
|---|---|---|---|
| domain-relevant | 32 | 0.406 (0.25 to 0.59) | 0.664 (0.54 to 0.78) |
| metrics-generated | 31 | 0.903 (0.81 to 1.00) | 0.919 (0.82 to 1.00) |
| novel-generated | 31 | 0.742 (0.58 to 0.87) | 0.804 (0.67 to 0.92) |

## System

```json
{
  "answers_run": "doc-agent-v4-full",
  "citation_precision": 0.8411,
  "citations": 258,
  "judge_errors": 1,
  "judge_model": "groq/openai/gpt-oss-20b",
  "judge_tokens": 151708,
  "prompt_version": "1"
}
```
