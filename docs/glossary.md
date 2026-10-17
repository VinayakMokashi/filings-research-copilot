# Glossary

Terms used in this project, in alphabetical order. New terms are added as they come up.

| Term | Meaning |
|---|---|
| **10-K / 10-Q** | Annual and quarterly reports that US public companies file with the SEC. |
| **10-K item** | A numbered section of an annual report, such as Item 1A (Risk Factors) or Item 7 (Management's Discussion and Analysis). |
| **52/53-week fiscal year** | A fiscal year that ends on the same weekday each year (for example the last Saturday of December), so it runs 52 or 53 weeks. |
| **Accession number** | SEC's unique id for one filing, such as `0000066740-24-000016`. |
| **ADR** | Architecture Decision Record: a short note recording one decision, the options considered and why. |
| **Bi-encoder** | A model that embeds the query and each passage separately, so passage vectors can be computed ahead of time and searched quickly. The embedding models here are bi-encoders. |
| **BM25** | A keyword-ranking formula that scores documents by term frequency, term rarity and document length. Strong for exact terms such as tickers and line items. |
| **Bootstrap confidence interval** | Resample the eval questions with replacement many times, recompute the metric each time, and take percentiles to see how uncertain the number is. |
| **Chunk** | A piece of a document that gets its own embedding and can be retrieved on its own. |
| **CIK** | Central Index Key, the SEC's unique ID for each filer. |
| **Citation precision** | The share of cited sources that actually support the claim they're attached to. |
| **Company facts** | SEC's per-company JSON of every XBRL fact the company has filed, without dimensions, from `data.sec.gov/api/xbrl/companyfacts`. |
| **Corrective RAG** | Grade the retrieved documents before generating; if they're weak, rewrite the query or fall back. |
| **Cross-encoder** | A model that reads the query and a passage together to score relevance. Slower than embedding search, but more precise. |
| **Data card** | A short document describing a dataset: source, licence, size, checksums, fields, splits and known issues. |
| **Demo window** | A period when the full AWS stack is brought up for a demo and torn down afterwards, so idle time costs nothing. |
| **DSPy** | A framework that treats prompts as programs and optimises them against a metric. |
| **Duration and instant facts** | A duration fact covers a period with a start and end date (revenue for a year); an instant fact is measured on one date (total assets at the year end). |
| **ECS Fargate** | AWS's service for running containers without managing servers. |
| **Embedding** | A vector that represents meaning; similar texts get nearby vectors. |
| **Execution accuracy (EX)** | Generated SQL counts as correct when it returns the same result as the gold query. |
| **Fallback chain** | Models tried in order when a role's own model keeps failing after retries. |
| **FinanceBench** | A benchmark of questions over real company filings, with answers and evidence pages. |
| **Git blob id** | The SHA-1 hash git computes over a file's contents. Used here to check every downloaded file against a manifest. |
| **Grouped split** | A split that keeps every item of a group (here, a company) on the same side, so nothing about the group leaks across. |
| **Held-out test set** | Questions set aside while building and opened only at milestones, so the reported result isn't tuned to them. |
| **Hit@k** | Whether at least one relevant item appears in the top k results: 1 or 0 for each question. |
| **HNSW** | A graph-based index for fast approximate nearest-neighbour search. |
| **Holm–Bonferroni correction** | Adjusts p-values when several comparisons are made at once, so the chance of any false win stays at the chosen level. |
| **Hybrid search** | Combining keyword (BM25) and semantic (dense) search. |
| **HyDE** | Hypothetical Document Embeddings: write a hypothetical answer, embed it, and search with that instead of the raw question. |
| **IDF** | Inverse document frequency: how rare a term is across the collection. BM25 multiplies each term's weight by it, so a rare word like a ticker counts for more than "the". |
| **Index card** | A JSON file kept beside each Qdrant collection, recording its models, query prefix, vector and HNSW settings, payload indexes, counts and timing. |
| **LangGraph** | A library for building LLM workflows as state graphs with branches, loops and checkpoints. |
| **Late chunking** | Run long stretches of a document through a long-context embedding model, then average each chunk's token vectors, so the chunk's vector keeps the surrounding context. |
| **LiteLLM** | A library and proxy that gives one interface to many LLM providers, with retries and fallbacks. |
| **LLM-as-judge** | Using a model to grade answers. The judge itself has to be checked against human labels. |
| **LoRA** | Low-Rank Adaptation: fine-tuning by training small low-rank adapter matrices instead of all the weights. |
| **McNemar's test** | A paired test for two systems' right-or-wrong outcomes that looks only at the questions where they disagree. |
| **MCP** | Model Context Protocol: a standard for connecting AI apps (hosts) to tools and data (servers). |
| **Mean pooling** | Turning a model's per-token vectors into one vector for the text by averaging them. |
| **MNRL** | MultipleNegativesRankingLoss: a contrastive loss that treats the other examples in a batch as negatives. |
| **Model role** | A named job (`strong` or `fast`) that code asks for instead of a specific model; settings decide which model fills it. |
| **MRR** | Mean Reciprocal Rank: the average of 1/rank of the first relevant result. |
| **OIDC (for deploys)** | Lets GitHub Actions assume an AWS role with short-lived tokens, so no AWS keys are stored anywhere. |
| **ONNX Runtime** | An engine that runs neural networks exported in the ONNX format quickly on a CPU. FastEmbed runs its models with it. |
| **Oracle-document setting** | A retrieval evaluation in which each question searches only the filing its evidence is in, isolating finding the page from finding the filing. |
| **Paired test** | Comparing two systems on the same questions, so that question-to-question noise cancels out. |
| **Payload index** | An index on a field stored with each Qdrant point, such as `company`, that makes searches filtered on that field fast. |
| **pdfium** | Google's PDF engine (used in Chrome); pypdfium2 is its Python binding and this project's parser. |
| **Permutation test** | A significance test that randomly swaps which system produced which score (here, flips the sign of each paired difference) to see how often chance alone gives a gap as large as the real one. |
| **Qdrant** | A vector database with dense and sparse vectors, filtering and hybrid queries. |
| **Recall@k** | The share of relevant items that appear in the top k results. |
| **Restatement** | A company revising a figure it reported earlier. The facts database keeps the first-reported value and the latest one. |
| **RRF** | Reciprocal Rank Fusion: merge ranked lists by summing 1/(k + rank) for each item. |
| **Running header** | Text repeated at the top or bottom of most pages, such as a "Table of Contents" link or a page number. The parser removes it. |
| **Self-consistency** | Sample several reasoning paths and keep the majority answer. |
| **Self-Discover** | The model selects, adapts and structures reasoning modules into a plan, then follows the plan. |
| **Semantic cache** | Reuse a stored answer when a new question is close enough to an old one in embedding space. |
| **Semantic routing** | Pick a route by comparing the query's embedding with labelled example queries. |
| **Sparse vector** | A vector stored as its few non-zero dimensions, such as one weight for each word in a text. Qdrant stores BM25 this way. |
| **SSE** | Server-Sent Events: a simple one-way HTTP stream from server to browser, used here for streaming answers. |
| **Stratified split** | A split that keeps each category's share (here, question type) the same on both sides. |
| **Text-to-SQL** | Turning a natural-language question into a SQL query. |
| **Transition report (10-KT)** | An annual report covering a short period, filed when a company changes its fiscal year end. |
| **XBRL** | The tagged data format companies use to file financial statements. Each number carries a concept tag, a period and a unit. |
