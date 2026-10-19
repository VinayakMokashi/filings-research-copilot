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
| 13 | `llm-as-judge.md` | Judging answers, and checking the judge | Zheng et al., *Judging LLM-as-a-Judge* (2023) | 3 | Planned |
| 14 | [corrective-rag.md](corrective-rag.md) | Grading the evidence, and searching more widely when it falls short | Yan et al., CRAG (2024); Asai et al., Self-RAG (2023) | 3 | Written |
| 15 | `text-to-sql-agent.md` | Schema retrieval, guardrails, self-correction | Liu et al., NL2SQL survey (2025) | 4 | Planned |
| 16 | `value-linking.md` | Matching names and synonyms to database values | Talaei et al., CHESS (2024) | 4 | Planned |
| 17 | `langgraph-orchestration.md` | State graphs, branches, loops, checkpoints | LangGraph docs | 5 | Planned |
| 18 | `semantic-routing.md` | Routing by embedding similarity | Semantic Router library docs | 5 | Planned |
| 19 | `validator-loop.md` | Reflection and retry with feedback | Madaan et al., Self-Refine (2023) | 5 | Planned |
| 20 | `self-consistency.md` | Sampling several answers and voting | Wang et al., Self-Consistency (2023) | 5 | Planned |
| 21 | `agent-memory.md` | Short-term state and long-term memory | Chhikara et al., Mem0 (2025) | 5 | Planned |
| 22 | `sse-streaming.md` | Streaming tokens and events to the UI | MDN, *Using server-sent events* | 6 | Planned |
| 23 | `mcp-server.md` | Hosts, clients and servers; tools, resources and prompts | Model Context Protocol specification | 6 | Planned |
| 24 | `semantic-cache.md` | Reusing answers to near-duplicate questions | GPTCache docs | 6 | Planned |
| 25 | `prompt-injection.md` | Treating retrieved text as data | Greshake et al. (2023); OWASP Top 10 for LLM Applications | 6 | Planned |
| 26 | `observability.md` | Traces, spans, token and cost metrics | Langfuse docs | 6 | Planned |
| 27 | `contrastive-finetuning.md` | MNRL, in-batch negatives, hard negatives | Henderson et al. (2017); Neelakantan et al. (2022) | 7 | Planned |
| 28 | `lora-classifier.md` | LoRA adapters for a fast router | Hu et al., LoRA (2021) | 7 | Planned |
| 29 | `dspy.md` | Optimising prompts against a metric | Khattab et al., DSPy (2023) | 7 | Planned |
| 30 | `bandit-routing.md` | ε-greedy exploration for choosing models | Sutton and Barto, *Reinforcement Learning* (2018), ch. 2 | 7 | Planned |
| 31 | `research-briefs.md` | Self-Discover plans and an agent crew | Zhou et al., Self-Discover (2024) | 7 | Planned |
| 32 | `ecs-fargate.md` | Containers, services, tasks, load balancers | AWS ECS docs | 8 | Planned |
| 33 | `terraform-basics.md` | Infrastructure as code, state, plans | Terraform docs | 8 | Planned |
| 34 | `github-oidc.md` | Deploying without stored AWS keys | GitHub docs, OpenID Connect in AWS | 8 | Planned |
| 35 | `online-evaluation.md` | Nightly evals, interleaving, drift checks | Chapelle et al., interleaved evaluation (2012) | 9 | Planned |
| 36 | `preference-data.md` | From thumbs-up/down to preference tuning | Rafailov et al., DPO (2023) | 9 | Planned |
