# memory: memory-v1 (dev)

20 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-23 22:24 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| resolved | 1.000 | 1.000 to 1.000 |
| rewritten | 0.500 | 0.300 to 0.700 |

## By kind

| Kind | Questions | resolved | rewritten |
|---|---|---|---|
| follow-up | 7 | 1.000 (1.00 to 1.00) | 1.000 (1.00 to 1.00) |
| from notes | 2 | 1.000 (1.00 to 1.00) | 1.000 (1.00 to 1.00) |
| standalone | 11 | 1.000 (1.00 to 1.00) | 0.091 (0.00 to 0.27) |

## System

```json
{
  "note_checks_passed": "7 of 15",
  "notes_model": "groq/openai/gpt-oss-20b",
  "prompt_version": "1",
  "rewrite_model": "groq/openai/gpt-oss-120b",
  "set": "eval/memory, 10 conversations, 6 users",
  "standalone_turns": 11,
  "tokens_by_model": {
    "groq/openai/gpt-oss-120b": [
      4167,
      1981
    ],
    "groq/openai/gpt-oss-20b": [
      8542,
      7012
    ]
  },
  "unchanged_when_standalone": 10.0
}
```
