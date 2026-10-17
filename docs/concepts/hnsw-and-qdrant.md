# HNSW and Qdrant

> Qdrant stores each chunk as a point with a dense vector, a sparse vector and its metadata. HNSW is the graph that lets it find nearest neighbours without comparing the query with every vector, at the cost of occasionally missing one.

**Lands in:** Phase 2 · **Code:** `src/copilot/ingest/index.py`, `src/copilot/retrieval/search.py`, `scripts/check_hnsw.py`

## What it is

**Qdrant** is a vector database. A *collection* holds *points*; each point has an id, one or more vectors and a JSON *payload*. Here every point is one chunk, with:

- `dense`: the chunk's 384-number bge-small embedding, compared by cosine similarity;
- `bm25`: a sparse vector, one weight per word the chunk contains;
- the payload: the chunk's text, pages, section, company, fiscal period, form and document.

**Nearest-neighbour search** finds the points whose vectors are most similar to the query's. Done exactly, that means comparing the query with every vector, which grows linearly with the collection. **HNSW** (Hierarchical Navigable Small World) is an approximate method: a layered graph in which each vector links to a few close neighbours. A search enters at the sparse top layer, walks greedily toward the query, drops a layer, and repeats, so it visits a small fraction of the points. It can miss a true neighbour when the greedy walk takes a wrong turn.

## Why we need it here

The doc agent needs three things from its store, in one query: semantic search, keyword search, and filters such as "only Pfizer's 2021 10-K". Qdrant does all three: dense and sparse vectors live on the same point, payload indexes make filters cheap, and the Query API fuses rankings server-side ([ADR-0010](../decisions/0010-vector-store-and-embeddings.md)). Knowing how HNSW trades accuracy for speed tells us when approximate search is safe to use for evaluation.

## How it works

**The graph's settings.**

| Setting | Value | Effect |
|---|---|---|
| `m` | 16 | Links per node. More links: better recall, more memory, slower builds |
| `ef_construct` | 100 | Candidates considered while building. Higher: a better graph, slower builds |
| `hnsw_ef` (per query) | defaults to `ef_construct` | Candidates kept during a search. Higher: better recall, slower queries |

**When the graph is used.** Qdrant splits a collection into segments, and two thresholds decide whether a segment's graph is used. A segment builds its HNSW graph only once its vectors pass the *indexing threshold* (10 MB by default), and even with a graph it is searched exactly while it is under the *full-scan threshold* (also 10 MB). The main collection's 21,899 vectors take 34 MB, spread over 8 segments of about 4 MB, so at this project's size every dense search is exact. Filtered searches follow the same logic per query: when the filter leaves few points (one filing is a few hundred chunks), Qdrant scans them directly instead of walking the graph.

**Sparse vectors** are stored in an inverted index (word id → points containing it), which is always exact. The IDF modifier tells Qdrant to weight each query word by its rarity in the collection at query time.

**Payload indexes** on `doc_name`, `company`, `doc_type`, `section` and `doc_period` let Qdrant find the points that pass a filter without reading every payload, and estimate how many there are, which decides between the graph and a direct scan.

## Where it lives in the code

| Piece | What it does |
|---|---|
| `copilot.ingest.index.ensure_collection` | Creates a collection: named dense vector, sparse vector with IDF, HNSW m and ef_construct, payload indexes |
| `copilot.ingest.index.missing`, `upsert`, `index_chunks` | Resumable, idempotent indexing keyed by content hash |
| `copilot.retrieval.search.Searcher` | Dense, BM25 and hybrid queries with document filters |
| `scripts/check_hnsw.py` | `poe check-hnsw`: HNSW recall and latency against exact search |

## How we measured it

`poe check-hnsw` copies the main index's 21,899 dense vectors into a scratch collection with both thresholds lowered, so that every search walks the graph, and runs the 100 dev questions through exact search and through HNSW at several `hnsw_ef` values. Qdrant's telemetry confirmed the paths: 3,500 segment searches through the graph, 700 exact. Latency was measured from the client, HTTP included, while another indexing job was using the CPU ([results](../../eval/results/indexing/hnsw-fb_tokens-480_bge-small.md)).

| Search | Recall@10 against exact | p50 ms | p95 ms |
|---|---|---|---|
| Exact | 1.000 | 21.6 | 30.0 |
| HNSW, ef = 8 | 0.883 | 17.7 | 25.0 |
| HNSW, ef = 16 | 0.940 | 20.0 | 29.8 |
| HNSW, ef = 32 | 0.986 | 22.4 | 33.8 |
| HNSW, ef = 64 | 0.996 | 19.8 | 43.0 |
| HNSW, ef = 128 | 0.999 | 19.0 | 30.1 |

Two conclusions. At ef near the default, HNSW misses about one true neighbour in a thousand, so evaluation results on an HNSW index would match exact search almost everywhere. And at 22,000 vectors exact search already answers in about 20 ms, so the graph saves nothing measurable; it starts to matter when the corpus grows by an order of magnitude or more.

## Pitfalls we hit

- **"Indexed" didn't mean HNSW.** The main collection reported every point as indexed while its dense vectors were still searched by brute force: the count was of sparse vectors, and the segments were too small for a graph. Qdrant's telemetry shows each segment's index type (`plain` or `hnsw`) and how many searches took each path.
- **A graph that isn't used.** The first run of the check scored recall 1.000 at every ef, even ef = 8. The scratch collection had graphs, but its segments were under the full-scan threshold, so Qdrant still searched them exactly. Lowering that threshold too (to its minimum, 10 KB) and checking the telemetry fixed the measurement.
- **In-memory mode for tests.** `QdrantClient(":memory:")` runs the same API in the test process, including hybrid queries, but ignores payload indexes (and warns about them).
- **Batch sizes.** Upserts go in batches of 256 points with `wait=True`, so a crash never leaves the client believing points were stored when they weren't.

## Review questions

1. Why is HNSW search approximate, and which setting would you raise to reduce misses at query time?
2. The main collection's dense searches are exact today. At roughly what collection size would that change, and what would you check then?
3. Why is filtered search inside one filing exact even when a graph exists?
4. What does a payload index on `company` add, given that filters work without one?
5. Why are sparse vectors searched exactly, while dense vectors need an approximate index to scale?

## References

- Malkov and Yashunin, [Efficient and robust approximate nearest neighbor search using Hierarchical Navigable Small World graphs](https://arxiv.org/abs/1603.09320), 2016.
- Qdrant documentation: [indexing](https://qdrant.tech/documentation/concepts/indexing/), [optimizer and segments](https://qdrant.tech/documentation/concepts/optimizer/), [filtering](https://qdrant.tech/documentation/concepts/filtering/).
