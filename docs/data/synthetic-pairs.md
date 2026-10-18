# Data card: synthetic question-to-chunk pairs

| | |
|---|---|
| **What it is** | 1,006 questions written by an LLM, each paired with the 480-token chunk of a filing that answers it |
| **Files** | `data/processed/synthetic/pairs.jsonl` (kept pairs) and `rejected.jsonl` (replies that failed a check, with the reason); both local and git-ignored. [`data/reference/synthetic_pairs_manifest.json`](../../data/reference/synthetic_pairs_manifest.json) records counts and checksums |
| **Licence** | Derived from FinanceBench's filings (CC BY-NC 4.0), so the pairs are never committed; rebuild them with `uv run poe generate-pairs` |
| **Built** | 2026-10-17 to 2026-10-18 |
| **Used for** | Fine-tuning the embedding model in Phase 7 (contrastive training with in-batch and hard negatives) |

## Which filings

Training filings are kept apart from evaluation:

- no filing of a **test company** (12 companies), so nothing about the held-out test set leaks into training ([ADR-0006](../decisions/0006-evaluation-splits.md));
- no filing that a **dev question** uses (58 filings), so a model trained on the pairs can still be compared fairly on dev.

That leaves 198 of the 368 FinanceBench PDFs, from 27 companies: other years and forms of the 19 dev companies, and all filings of the 8 companies that have no questions (Apple, eBay, FedEx, Intel, McDonald's, Oracle, PG&E and Salesforce). Two of them, Intel 8-Ks, are truncated in FinanceBench's repository and can't be parsed, so 196 filings are used. One of those, McDonald's Q4 2022 earnings release, is almost all tables, so none of its chunks passes the sampling rules below; the pairs come from the other 195.

## How it was built

1. **Chunks.** Each filing is chunked like the main index (`tokens-480`: up to 480 bge-small tokens, 64 tokens of overlap).
2. **Sampling.** Up to 6 chunks per filing, chosen at random with a fixed seed per filing, from chunks of at least 200 tokens in which at least 55% of the visible characters are letters. The second rule skips financial tables and exhibit lists, which rarely support a natural question. 1,138 chunks were sampled.
3. **Order.** Chunks are asked about in an interleaved order: each company's chunks dealt round-robin across its filings, and the companies dealt round-robin, so a run cut short by a quota still covers every company. (The first day's run went filing by filing and stopped at the quota with nine companies uncovered, which is why the order was changed.)
4. **Generation.** `uv run poe generate-pairs` sends each chunk, with its company, form and fiscal year, to a model with this instruction (prompt version 1): write one question an equity analyst might ask that the excerpt answers; name the company and fiscal period; use your own words; ask about a specific fact, figure, cause, risk or change, not about the excerpt. Calls alternate between `openai/gpt-oss-120b` and `qwen/qwen3.8-27b` on Groq at temperature 0.7, which spreads the load over two free-tier quotas and varies the phrasing; `openai/gpt-oss-20b` answers when one of them is out of quota. Each pair records the model that wrote it.
5. **Checks.** A reply is kept if it is one line, ends with a question mark, has 8 to 45 words, doesn't refer to "the excerpt" or "the document", and doesn't repeat 8 or more consecutive words of its chunk. Questions are normalised to plain quotes, hyphens and spaces.

## Contents

| | |
|---|---|
| Pairs kept | 1,006, from 195 filings of 27 companies |
| Replies rejected | 132 of 1,138: 128 copied, 4 format |
| Questions by model | openai/gpt-oss-120b 391, openai/gpt-oss-20b 158, qwen/qwen3.8-27b 457 |
| Questions by form | 10k 748, 10k_annualreport 21, 10q 66, 8k 77, Earnings 94 |
| Question length | 9 to 44 words, median 22 |
| Checksum | SHA-256 of `pairs.jsonl`: `33100b0b7cc08e15…` (full value in the manifest) |

"Format" rejections broke a rule a script can check (several lines, no question mark, or a question about "the excerpt"); "copied" ones repeated 8 or more consecutive words of their chunk. Generation ran over two days, because each model on Groq's free tier allows about 200,000 tokens a day: `gpt-oss-120b` and `qwen3.8-27b` alternated, and `gpt-oss-20b` stood in when one of them hit its cap.

## Known issues

- **Machine-written questions.** They are fluent but more uniform than real users' questions, and some ask about details no analyst would care about (an executive's earlier job title, for example). Phase 7 will measure whether training on them helps on FinanceBench's human-written dev questions.
- **Easy pairs.** A question generated from a chunk tends to reuse its vocabulary, which makes the pair easier than a real query. The copy check removes the most literal ones; hard negatives mined from the same filing in Phase 7 counter the rest.
- **One chunk per question.** The answer may also appear elsewhere in the filing (the income statement and MD&A repeat figures), so a "negative" chunk can sometimes answer the question too.
- **Rejected replies are kept.** `rejected.jsonl` keeps every rejected reply with its reason, so the rules can be revisited without new model calls.
