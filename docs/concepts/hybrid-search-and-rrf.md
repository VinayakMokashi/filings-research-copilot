# Hybrid search and reciprocal rank fusion

> Keyword search and semantic search fail on different questions. Running both and merging their rankings by rank, not by score, catches more of the evidence than either alone.

**Lands in:** Phase 2 · **Code:** `src/copilot/retrieval/search.py`, `src/copilot/ingest/embed.py`

## What it is

**Dense search** embeds the question and every chunk as vectors and returns the chunks whose vectors point the most nearly the same way (cosine similarity). It matches meaning: "How much did 3M spend on new equipment?" can find "Purchases of property, plant and equipment".

**BM25** is keyword search. A chunk scores higher when it contains the question's words, especially rare ones, more often, in fewer words:

```
score(q, d) = sum over words w in q of  IDF(w) * tf(w, d) * (k1 + 1) / (tf(w, d) + k1 * (1 - b + b * |d| / avgdl))
```

where `tf` is how often the word appears in the chunk, `|d|` the chunk's length, `avgdl` the average length, and IDF grows as the word gets rarer across the collection. It matches exact strings: a ticker, "Item 7A", "goodwill impairment", a figure such as "1,577".

**Hybrid search** runs both and merges the two ranked lists. **Reciprocal rank fusion (RRF)** merges by position alone:

```
RRF(d) = sum over rankings r that contain d of  1 / (k + rank_r(d))
```

A chunk ranked 1st by BM25 and 5th by dense search scores 1/61 + 1/65 with k = 60; one found by only one list scores at most 1/61.

## Why we need it here

Filings mix both kinds of question. "What drove the change in operating margin?" is semantic. "What is the FY2018 capital expenditure for 3M?" depends on matching a line item's exact label, and dense search on a small model blurs it with every other cash-flow line. Neither search alone is reliably better, so the plan measures dense, BM25 and their fusion on the same questions.

Fusing by rank avoids a hard problem: dense cosine scores (around 0.6 to 0.9) and BM25 scores (0 to 30 or more) are on unrelated scales, and the scales shift from question to question. Ranks are always comparable.

## How it works

```mermaid
flowchart LR
    Q["Question"] --> DE["bge-small<br/>query vector"]
    Q --> SE["BM25 query<br/>(word ids)"]
    DE --> P1["Top 50 by cosine"]
    SE --> P2["Top 50 by BM25"]
    P1 --> F["RRF, k = 60"]
    P2 --> F
    F --> R["Top chunks"]
```

1. **Index time.** Each chunk stores a dense vector and a sparse vector: the BM25 term weights for the words it contains (FastEmbed's `Qdrant/bm25` computes term frequency with length normalisation). The collection's sparse vectors use Qdrant's IDF modifier, so IDF comes from the collection's live statistics and never goes stale as documents are added.
2. **Query time.** One Qdrant call carries two *prefetches* (top 50 by the dense vector, top 50 by BM25), both restricted by the same filter, and a fusion query that merges them with RRF.
3. **k.** k = 60 follows Cormack, Clarke and Büttcher (2009), who found it robust across collections. Qdrant's default is k = 2, which makes the first one or two ranks of either list dominate; a larger k gives agreement between the lists more weight than position at the very top.

## Where it lives in the code

| Piece | What it does |
|---|---|
| `copilot.ingest.embed.FastEmbedBM25` | Sparse BM25 vectors for chunks and queries |
| `copilot.ingest.index.ensure_collection` | The `bm25` sparse vector with `Modifier.IDF` |
| `copilot.retrieval.search.Searcher.search` | `mode="dense"`, `"bm25"` or `"hybrid"` (two prefetches and `RrfQuery(k=60)`), with an optional document filter |
| `scripts/run_retrieval.py` | `poe run-retrieval --mode ...` scores a configuration on FinanceBench dev |

## How we measured it

Dense, BM25 and hybrid search on the 100 dev questions, over the same `tokens-480` chunks ([report](../eval/retrieval-baseline.md)):

| Mode | recall@10, own filing | recall@10, all 84 filings |
|---|---|---|
| Dense | **0.608** | **0.345** |
| BM25 | 0.425 (significantly worse) | 0.155 (significantly worse) |
| Hybrid, RRF k = 60 | 0.540 (not significantly different) | 0.210 (significantly worse) |

Hybrid search didn't help on FinanceBench's questions as asked. Two thirds of them come from templates that add instructions ("Round your answer to two decimal places", "If operating margin is not a useful metric for a company like this, then state that and explain why"), and to BM25 those words count as much as the actual subject. On the human-written questions, which carry no template, BM25 and hybrid both beat dense search (0.758 against 0.697 within the filing). Phase 3 rewrites questions before searching, and hybrid search gets another look after that.

## Pitfalls we hit

- **Score fusion looks tempting.** A weighted sum of cosine and BM25 scores needs both normalised per query, and the weight then has to be tuned; RRF has one parameter with a well-tested default.
- **Filters on both branches.** The document filter goes on each prefetch as well as on the fused query, so neither ranking spends its 50 candidates on other filings.
- **RRF weights don't multiply scores.** Qdrant's RRF takes a weight per prefetch, which suggests `w / (k + rank)`. Probing the 1.19 server showed fused orders that match `1 / (k + rank / w)` instead: a weight rescales a list's ranks. With k = 60, a larger weight flattens that list's contribution, so the *other* list's order decides more. A dense weight of 2 therefore made results worse, not better (recall@10 0.470 against 0.540 with equal weights). Weights of 0 and 1 behave as expected.

## Review questions

1. Why can't you add a cosine similarity of 0.82 to a BM25 score of 14.6 and rank by the sum?
2. A chunk is 1st in the BM25 list and absent from the dense list; another is 3rd in both. With k = 60, which ranks higher after fusion? With k = 2?
3. Why does BM25 find "Purchases of property, plant and equipment" for the query "purchases of PP&E" but not for "capital expenditure", and what would?
4. Why does Qdrant compute IDF at query time instead of storing it in each chunk's sparse vector?
5. The hybrid query fetches 50 candidates from each list. What happens to recall at 20 if that drops to 10?

## References

- Robertson and Zaragoza, The Probabilistic Relevance Framework: BM25 and Beyond, *Foundations and Trends in Information Retrieval*, 2009.
- Cormack, Clarke and Büttcher, [Reciprocal Rank Fusion outperforms Condorcet and individual rank learning methods](https://dl.acm.org/doi/10.1145/1571941.1572114), SIGIR 2009.
- Qdrant documentation, [hybrid and multi-stage queries](https://qdrant.tech/documentation/concepts/hybrid-queries/).
