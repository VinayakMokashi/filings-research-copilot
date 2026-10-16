# Glossary

Terms used in this project, in alphabetical order. New terms are added as they come up.

| Term | Meaning |
|---|---|
| **10-K / 10-Q** | Annual and quarterly reports that US public companies file with the SEC. |
| **ADR** | Architecture Decision Record: a short note recording one decision, the options considered and why. |
| **BM25** | A keyword-ranking formula that scores documents by term frequency, term rarity and document length. Strong for exact terms such as tickers and line items. |
| **Bootstrap confidence interval** | Resample the eval questions with replacement many times, recompute the metric each time, and take percentiles to see how uncertain the number is. |
| **Chunk** | A piece of a document that gets its own embedding and can be retrieved on its own. |
| **CIK** | Central Index Key, the SEC's unique ID for each filer. |
| **Citation precision** | The share of cited sources that actually support the claim they're attached to. |
| **Corrective RAG** | Grade the retrieved documents before generating; if they're weak, rewrite the query or fall back. |
| **Cross-encoder** | A model that reads the query and a passage together to score relevance. Slower than embedding search, but more precise. |
| **Data card** | A short document describing a dataset: source, licence, size, checksums, fields, splits and known issues. |
| **Demo window** | A period when the full AWS stack is brought up for a demo and torn down afterwards, so idle time costs nothing. |
| **DSPy** | A framework that treats prompts as programs and optimises them against a metric. |
| **ECS Fargate** | AWS's service for running containers without managing servers. |
| **Embedding** | A vector that represents meaning; similar texts get nearby vectors. |
| **Execution accuracy (EX)** | Generated SQL counts as correct when it returns the same result as the gold query. |
| **Fallback chain** | Models tried in order when a role's own model keeps failing after retries. |
| **FinanceBench** | A benchmark of questions over real company filings, with answers and evidence pages. |
| **Git blob id** | The SHA-1 hash git computes over a file's contents. Used here to check every downloaded file against a manifest. |
| **Grouped split** | A split that keeps every item of a group (here, a company) on the same side, so nothing about the group leaks across. |
| **Held-out test set** | Questions set aside while building and opened only at milestones, so the reported result isn't tuned to them. |
| **HNSW** | A graph-based index for fast approximate nearest-neighbour search. |
| **Hybrid search** | Combining keyword (BM25) and semantic (dense) search. |
| **HyDE** | Hypothetical Document Embeddings: write a hypothetical answer, embed it, and search with that instead of the raw question. |
| **LangGraph** | A library for building LLM workflows as state graphs with branches, loops and checkpoints. |
| **Late chunking** | Run the whole document through a long-context embedding model, then average token vectors per chunk, so each chunk keeps document context. |
| **LiteLLM** | A library and proxy that gives one interface to many LLM providers, with retries and fallbacks. |
| **LLM-as-judge** | Using a model to grade answers. The judge itself has to be checked against human labels. |
| **LoRA** | Low-Rank Adaptation: fine-tuning by training small low-rank adapter matrices instead of all the weights. |
| **MCP** | Model Context Protocol: a standard for connecting AI apps (hosts) to tools and data (servers). |
| **MNRL** | MultipleNegativesRankingLoss: a contrastive loss that treats the other examples in a batch as negatives. |
| **Model role** | A named job (`strong` or `fast`) that code asks for instead of a specific model; settings decide which model fills it. |
| **MRR** | Mean Reciprocal Rank: the average of 1/rank of the first relevant result. |
| **OIDC (for deploys)** | Lets GitHub Actions assume an AWS role with short-lived tokens, so no AWS keys are stored anywhere. |
| **Paired test** | Comparing two systems on the same questions, so that question-to-question noise cancels out. |
| **Qdrant** | A vector database with dense and sparse vectors, filtering and hybrid queries. |
| **Recall@k** | The share of relevant items that appear in the top k results. |
| **RRF** | Reciprocal Rank Fusion: merge ranked lists by summing 1/(k + rank) for each item. |
| **Self-consistency** | Sample several reasoning paths and keep the majority answer. |
| **Self-Discover** | The model selects, adapts and structures reasoning modules into a plan, then follows the plan. |
| **Semantic cache** | Reuse a stored answer when a new question is close enough to an old one in embedding space. |
| **Semantic routing** | Pick a route by comparing the query's embedding with labelled example queries. |
| **SSE** | Server-Sent Events: a simple one-way HTTP stream from server to browser, used here for streaming answers. |
| **Stratified split** | A split that keeps each category's share (here, question type) the same on both sides. |
| **Text-to-SQL** | Turning a natural-language question into a SQL query. |
| **XBRL** | The tagged data format companies use to file financial statements. Each number carries a concept tag, a period and a unit. |
