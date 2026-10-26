# Concept guides

One guide per concept, written when its component lands. Each guide follows [_template.md](_template.md) and ends with review questions.

| # | Guide | Covers | Key reference | Phase | Status |
|---|---|---|---|---|---|
| 1 | [llm-gateway.md](llm-gateway.md) | Model roles, retries, fallbacks, token and cost accounting | LiteLLM router docs | 0 | Written |
| 2 | [xbrl-and-financial-metrics.md](xbrl-and-financial-metrics.md) | What XBRL facts are and why their tags need normalising | SEC EDGAR API docs | 1 | Written |
| 3 | [evaluation-statistics.md](evaluation-statistics.md) | Bootstrap confidence intervals and paired tests | Efron and Tibshirani, *An Introduction to the Bootstrap* (1993) | 1 | Written |
| 4 | [chunking.md](chunking.md) | Chunk size, overlap, page, token-window and semantic chunking | LangChain text-splitter docs | 2 | Written |
| 5 | [late-chunking.md](late-chunking.md) | Embedding long stretches of the document before splitting it | Günther et al., *Late Chunking* (2024) | 2 | Written |
| 6 | [hybrid-search-and-rrf.md](hybrid-search-and-rrf.md) | BM25 plus dense search, and reciprocal rank fusion | Robertson and Zaragoza (2009); Cormack et al. (2009) | 2 | Written |
| 7 | [reranking.md](reranking.md) | Bi-encoders vs cross-encoders | Nogueira and Cho, *Passage Re-ranking with BERT* (2019) | 2 | Written |
| 8 | [hnsw-and-qdrant.md](hnsw-and-qdrant.md) | How the vector index finds neighbours quickly, and when it doesn't need to | Malkov and Yashunin, HNSW (2018) | 2 | Written |
| 9 | [retrieval-metrics.md](retrieval-metrics.md) | Recall@k, hit@k, MRR, scored by page | Manning et al., *Introduction to Information Retrieval* (2008) | 2 | Written |
| 10 | [query-understanding.md](query-understanding.md) | Company, period and form as search filters | FinanceBench (Islam et al., 2023); Qdrant filtering docs | 3 | Written |
| 11 | [query-rewriting.md](query-rewriting.md) | Multi-query, HyDE, decomposition, fused | Gao et al., HyDE (2022) | 3 | Written |
| 12 | [grounded-generation.md](grounded-generation.md) | Numbered sources, citations, abstention, context budgets, the calculator | Gao et al., *Enabling LLMs to Generate Text with Citations* (2023) | 3 | Written |
| 13 | [llm-as-judge.md](llm-as-judge.md) | Judging answers with a rubric and computed comparisons, and checking the judge | Zheng et al., *Judging LLM-as-a-Judge* (2023) | 3 | Written |
| 14 | [corrective-rag.md](corrective-rag.md) | Grading the evidence, and searching more widely when it falls short | Yan et al., CRAG (2024); Asai et al., Self-RAG (2023) | 3 | Written |
| 15 | [text-to-sql-agent.md](text-to-sql-agent.md) | Table selection, guardrails, repair, and a typed answer with exact statistics | Liu et al., NL2SQL survey (2025) | 4 | Written |
| 16 | [value-linking.md](value-linking.md) | Matching names, metric values and coverage to the database, as hints | Talaei et al., CHESS (2024) | 4 | Written |
| 17 | [hybrid-answers.md](hybrid-answers.md) | Figures from a database query and explanations from the filing, in one cited answer | Zhu et al., TAT-QA (2021) | 4 | Written |
| 18 | [langgraph-orchestration.md](langgraph-orchestration.md) | State graphs, branches, loops, checkpoints, streamed events and traces | LangGraph docs | 5 | Written |
| 19 | [semantic-routing.md](semantic-routing.md) | Routing by embedding similarity or by a model, measured leaving one seed group out | Semantic Router library docs | 5 | Written |
| 20 | [validator-loop.md](validator-loop.md) | Checking every cited sentence, revising what fails, and keeping only what holds | Madaan et al., Self-Refine (2023) | 5 | Written |
| 21 | `self-consistency.md` | Sampling several answers and voting | Wang et al., Self-Consistency (2023) | 5 | Planned |
| 22 | [agent-memory.md](agent-memory.md) | Follow-up rewriting, and notes about users kept across conversations | Chhikara et al., Mem0 (2025) | 5 | Written |
| 23 | [sse-streaming.md](sse-streaming.md) | Streaming an answer's events over one HTTP response | MDN, *Using server-sent events* | 6 | Written |
| 24 | [mcp-server.md](mcp-server.md) | Hosts, clients and servers; tools, resources and prompts; transports | Model Context Protocol specification | 6 | Written |
| 25 | [semantic-cache.md](semantic-cache.md) | Reusing answers: why near-duplicates were measured and rejected, and exact repeats kept | GPTCache docs | 6 | Written |
| 26 | [prompt-injection.md](prompt-injection.md) | Treating retrieved text as data: layers, a red-team set and a corpus scan | Greshake et al. (2023); OWASP Top 10 for LLM Applications | 6 | Written |
| 27 | `observability.md` | Traces, spans, token and cost metrics | Langfuse docs | 6 | Planned |
| 28 | `contrastive-finetuning.md` | MNRL, in-batch negatives, hard negatives | Henderson et al. (2017); Neelakantan et al. (2022) | 7 | Planned |
| 29 | `lora-classifier.md` | LoRA adapters for a fast router | Hu et al., LoRA (2021) | 7 | Planned |
| 30 | `dspy.md` | Optimising prompts against a metric | Khattab et al., DSPy (2023) | 7 | Planned |
| 31 | `bandit-routing.md` | ε-greedy exploration for choosing models | Sutton and Barto, *Reinforcement Learning* (2018), ch. 2 | 7 | Planned |
| 32 | `research-briefs.md` | Self-Discover plans and an agent crew | Zhou et al., Self-Discover (2024) | 7 | Planned |
| 33 | `cloud-run.md` | Containers, services, revisions, scaling to zero | Cloud Run docs | 8 | Planned |
| 34 | `terraform-basics.md` | Infrastructure as code, state, plans | Terraform docs | 8 | Planned |
| 35 | `workload-identity-federation.md` | Deploying without stored keys | Google Cloud docs, Workload Identity Federation with deployment pipelines | 8 | Planned |
| 36 | `online-evaluation.md` | Nightly evals, interleaving, drift checks | Chapelle et al., interleaved evaluation (2012) | 9 | Planned |
| 37 | `preference-data.md` | From thumbs-up/down to preference tuning | Rafailov et al., DPO (2023) | 9 | Planned |
