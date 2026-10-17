# HNSW against exact search: fb_tokens-480_bge-small

21,899 dense vectors, 100 dev questions, top 10; HNSW m = 16, ef_construct = 100; graph built in 1 s. Latency is measured from the client, HTTP included. Segment searches by path (Qdrant telemetry): unfiltered_exact 700, unfiltered_hnsw 3,500.

| Search | Recall@10 against exact | p50 ms | p95 ms |
|---|---|---|---|
| exact | 1.000 | 21.6 | 30.0 |
| hnsw ef=8 | 0.883 | 17.7 | 25.0 |
| hnsw ef=16 | 0.940 | 20.0 | 29.8 |
| hnsw ef=32 | 0.986 | 22.4 | 33.8 |
| hnsw ef=64 | 0.996 | 19.8 | 43.0 |
| hnsw ef=128 | 0.999 | 19.0 | 30.1 |
