# ADR-0010: Index chunks in Qdrant with bge-small and BM25 vectors

- **Status:** Accepted
- **Date:** 2026-10-17
- **Phase:** 2

## Context

The doc agent needs semantic search and keyword search over the filings, restricted by company, fiscal year, form, section or document, and fused into one ranking. The store has to run the same way on a laptop and in the AWS demo windows ([ADR-0003](0003-aws-demo-windows.md)). Everything is embedded on a laptop CPU (8 cores, no GPU): one chunking strategy over the 84 question documents is 20,000 to 40,000 chunks and about 10 million tokens. Several chunking strategies have to be compared, so re-indexing must be cheap to restart and safe to repeat.

## Options considered

**Vector store**

| Option | Pros | Cons |
|---|---|---|
| **Qdrant** | Dense and sparse vectors on the same point; IDF for BM25 computed by the server; hybrid queries with fusion in one call; payload indexes and filter-aware search; an in-memory mode for tests; one Docker image; Apache 2.0 | One more service to run |
| pgvector in the existing Postgres | No new service; SQL filters | Keyword search needs `tsvector` and a hand-written fusion query; its HNSW index filters after the scan, so a selective filter can return too few rows |
| Chroma | Embedded, simple | No sparse vectors, so BM25 would live elsewhere |
| FAISS plus `rank_bm25` in process | Fast, no service | Persistence, filtering and fusion all hand-built; nothing to deploy for the app |
| OpenSearch | Mature BM25 and k-NN | A heavy JVM service for a laptop and a short demo window |

**Dense embedding model**

| Option | Pros | Cons |
|---|---|---|
| **BAAI/bge-small-en-v1.5** (33M parameters, 384 dimensions) | Close to bge-base on the MTEB retrieval average (51.7 against 53.3) at a third of the size; ONNX build in FastEmbed | 512-token limit |
| bge-base-en-v1.5 (110M, 768 dimensions) | Somewhat better retrieval | About three times the compute: roughly two and a half hours per strategy on this CPU |
| jina-embeddings-v2-small-en (33M, 512 dimensions, 8,192 tokens) | Long context, which late chunking needs | Kept for the late-chunking experiment rather than as the default |
| A hosted embedding API | No local compute | Per-token cost and a third-party dependency for every rebuild |

## Decision

- **Qdrant 1.19**, run from Docker locally and from the same image in demo windows. One collection per chunking strategy and embedding model, named `fb_<strategy>_<model>`, so each experiment is independent and can be dropped on its own.
- **Each point** holds a named dense vector `dense` (cosine distance), a sparse vector `bm25` with Qdrant's IDF modifier, and the chunk as payload: text, pages, section, company, fiscal period, form, document and character span.
- **Payload indexes** on `doc_name`, `company`, `doc_type` and `section` (keywords) and `doc_period` (integer), for filtered search.
- **HNSW** at m = 16 and ef_construct = 100. These are Qdrant's defaults, set explicitly so any change shows up in code review.
- **Point ids** are UUIDs made from the chunk's SHA-256 content id, so storing a chunk twice changes nothing. A run first asks which ids exist and embeds only the rest, so an interrupted run simply starts again.
- **Dense vectors** from bge-small-en-v1.5 through FastEmbed on ONNX Runtime. Passages are embedded as they are; queries get bge's retrieval instruction. Texts go through one at a time (see Evidence).
- **Sparse vectors** from FastEmbed's `Qdrant/bm25`: term frequencies with BM25's length normalisation on the client, IDF from the collection on the server.
- **Ingestion as jobs**, one per document. A local runner works through them in order, logs each result as a JSON line, and records a failure without stopping the run; Phase 8 swaps in an SQS-driven worker with the same handler.
- **An index card** per collection (`data/processed/indexes/<collection>.json`) records the models, query prefix, vector settings, HNSW settings, payload indexes, counts and timing.

## Evidence

- **Batch size.** On 64 chunks of about 440 tokens, FastEmbed embedded 9.0 chunks a second one at a time and 5.5 in batches of 16. Short units (45 tokens) ran at 73 a second singly and 49 in sorted batches of 16. A batch is padded to its longest text, and larger batches spill out of the CPU caches.
- **No hidden overhead.** Calling ONNX Runtime directly on FastEmbed's model file gave 8.2 chunks a second and the same vectors (largest difference 6e-8), so the library costs nothing worth removing. Setting the thread count changed nothing.
- **Main index.** `tokens-480` over the 84 question documents: 21,899 chunks in about 47 minutes, BM25 and upserts included.
- **Tests** run the same hybrid query against Qdrant's in-memory mode, with deterministic hashing embedders in place of the models.
- Retrieval quality, and the choice between chunking strategies, are measured in step 2.5 and recorded in the next ADR.

## Consequences

- A query must use the collection's own model and query prefix; the index card says which.
- BM25 statistics belong to each collection. The experiment collections hold only the 58 documents behind dev questions, so their keyword scores are comparable with each other but not exactly with the 84-document main collection. Dense scores within one document don't depend on the rest of the collection.
- Re-indexing the main collection costs about 45 minutes of CPU, so experiments index the dev documents only and every job can resume.
- The late-chunking experiment needs token-level output, which FastEmbed doesn't expose, so it runs jina-small through ONNX Runtime directly (`copilot.ingest.late_chunking`).

## References

- Malkov and Yashunin, [Efficient and robust approximate nearest neighbor search using Hierarchical Navigable Small World graphs](https://arxiv.org/abs/1603.09320), 2016.
- Qdrant documentation: [hybrid queries](https://qdrant.tech/documentation/concepts/hybrid-queries/), [sparse vectors and the IDF modifier](https://qdrant.tech/documentation/concepts/vectors/#sparse-vectors), [indexing](https://qdrant.tech/documentation/concepts/indexing/).
- Xiao et al., [C-Pack: Packaged Resources To Advance General Chinese Embedding](https://arxiv.org/abs/2309.07597), 2023 (the BGE models), and the [bge-small-en-v1.5 model card](https://huggingface.co/BAAI/bge-small-en-v1.5).
- Robertson and Zaragoza, The Probabilistic Relevance Framework: BM25 and Beyond, 2009.
