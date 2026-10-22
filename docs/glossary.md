# Glossary

Terms used in this project, in alphabetical order. New terms are added as they come up.

| Term | Meaning |
|---|---|
| **10-K / 10-Q** | Annual and quarterly reports that US public companies file with the SEC. |
| **10-K item** | A numbered section of an annual report, such as Item 1A (Risk Factors) or Item 7 (Management's Discussion and Analysis). |
| **52/53-week fiscal year** | A fiscal year that ends on the same weekday each year (for example the last Saturday of December), so it runs 52 or 53 weeks. |
| **Abstention** | Saying that the sources don't contain what the question needs, and what is missing, instead of guessing. Here the answer's `answerable` flag is false. |
| **Accession number** | SEC's unique id for one filing, such as `0000066740-24-000016`. |
| **ADR** | Architecture Decision Record: a short note recording one decision, the options considered and why. |
| **Bi-encoder** | A model that embeds the query and each passage separately, so passage vectors can be computed ahead of time and searched quickly. The embedding models here are bi-encoders. |
| **BM25** | A keyword-ranking formula that scores documents by term frequency, term rarity and document length. Strong for exact terms such as tickers and line items. |
| **Bootstrap confidence interval** | Resample the eval questions with replacement many times, recompute the metric each time, and take percentiles to see how uncertain the number is. |
| **Chunk** | A piece of a document that gets its own embedding and can be retrieved on its own. |
| **CIK** | Central Index Key, the SEC's unique ID for each filer. |
| **Citation precision** | The share of cited sources that actually support the claim they're attached to. |
| **Cohen's kappa** | Agreement between two raters corrected for the agreement chance alone would give: 1 is perfect, 0 is no better than chance. |
| **Company facts** | SEC's per-company JSON of every XBRL fact the company has filed, without dimensions, from `data.sec.gov/api/xbrl/companyfacts`. |
| **Context budget** | The most retrieved text, in tokens, that the answer prompt may hold: 3,000 here. |
| **Context hit** | Whether at least one evidence page is among the sources the answer model sees. An answer can't be better than its context. |
| **Corrective RAG** | Grade the retrieved documents before generating; if they're weak, rewrite the query or fall back. Here the answer model's own refusal is the grade, and the fallback is one search across all of the company's filings. |
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
| **Grounded answer** | An answer whose every claim cites a retrieved source that states it, so a reader can check it. |
| **Grouped split** | A split that keeps every item of a group (here, a company) on the same side, so nothing about the group leaks across. |
| **Held-out test set** | Questions set aside while building and opened only at milestones, so the reported result isn't tuned to them. |
| **Hit@k** | Whether at least one relevant item appears in the top k results: 1 or 0 for each question. |
| **HNSW** | A graph-based index for fast approximate nearest-neighbour search. |
| **Holm–Bonferroni correction** | Adjusts p-values when several comparisons are made at once, so the chance of any false win stays at the chosen level. |
| **Hybrid search** | Combining keyword (BM25) and semantic (dense) search. |
| **HyDE** | Hypothetical Document Embeddings: write a hypothetical answer, embed it, and search with that instead of the raw question. |
| **IDF** | Inverse document frequency: how rare a term is across the collection. BM25 multiplies each term's weight by it, so a rare word like a ticker counts for more than "the". |
| **Index card** | A JSON file kept beside each Qdrant collection, recording its models, query prefix, vector and HNSW settings, payload indexes, counts and timing. |
| **JSON mode** | A provider option that makes the model reply with one valid JSON object, so code can read the answer's fields. |
| **LangGraph** | A library for building LLM workflows as state graphs with branches, loops and checkpoints. |
| **Late chunking** | Run long stretches of a document through a long-context embedding model, then average each chunk's token vectors, so the chunk's vector keeps the surrounding context. |
| **LiteLLM** | A library and proxy that gives one interface to many LLM providers, with retries and fallbacks. |
| **LLM-as-judge** | Using a model to grade answers against a reference by a written rubric. The judge itself has to be checked against human labels. |
| **LoRA** | Low-Rank Adaptation: fine-tuning by training small low-rank adapter matrices instead of all the weights. |
| **McNemar's test** | A paired test for two systems' right-or-wrong outcomes that looks only at the questions where they disagree. |
| **MCP** | Model Context Protocol: a standard for connecting AI apps (hosts) to tools and data (servers). |
| **Model-call cache** | A file of model responses keyed by model, messages and parameters, so repeated experiment runs replay answers instead of spending quota. |
| **Mean pooling** | Turning a model's per-token vectors into one vector for the text by averaging them. |
| **MNRL** | MultipleNegativesRankingLoss: a contrastive loss that treats the other examples in a batch as negatives. |
| **Model role** | A named job (`strong` or `fast`) that code asks for instead of a specific model; settings decide which model fills it. |
| **Multi-query retrieval** | Asking a model for several rewordings of a question, searching each, and fusing the rankings. |
| **MRR** | Mean Reciprocal Rank: the average of 1/rank of the first relevant result. |
| **OIDC (for deploys)** | Lets GitHub Actions assume an AWS role with short-lived tokens, so no AWS keys are stored anywhere. |
| **ONNX Runtime** | An engine that runs neural networks exported in the ONNX format quickly on a CPU. FastEmbed runs its models with it. |
| **Oracle-document setting** | A retrieval evaluation in which each question searches only the filing its evidence is in, isolating finding the page from finding the filing. |
| **Paired test** | Comparing two systems on the same questions, so that question-to-question noise cancels out. |
| **Payload index** | An index on a field stored with each Qdrant point, such as `company`, that makes searches filtered on that field fast. |
| **pdfium** | Google's PDF engine (used in Chrome); pypdfium2 is its Python binding and this project's parser. |
| **Permutation test** | A significance test that randomly swaps which system produced which score (here, flips the sign of each paired difference) to see how often chance alone gives a gap as large as the real one. |
| **Program-aided arithmetic** | The model writes a calculation as an expression and a safe evaluator computes it, instead of the model doing the arithmetic in its head (after PAL, Gao et al. 2022). |
| **Qdrant** | A vector database with dense and sparse vectors, filtering and hybrid queries. |
| **Recall@k** | The share of relevant items that appear in the top k results. |
| **Reference labels** | Labels a judge is checked against, made by someone or something other than the judge: ideally a person, here a stronger model. |
| **Restatement** | A company revising a figure it reported earlier. The facts database keeps the first-reported value and the latest one. |
| **Query decomposition** | Splitting a question into the separate facts it needs (both parts of a ratio, both years of a change) and searching for each. |
| **Query understanding** | Reading the company, period and form out of a question and searching only the filings that match. |
| **RRF** | Reciprocal Rank Fusion: merge ranked lists by summing 1/(k + rank) for each item. |
| **Running header** | Text repeated at the top or bottom of most pages, such as a "Table of Contents" link or a page number. The parser removes it. |
| **Self-consistency** | Sample several reasoning paths and keep the majority answer. |
| **Self-Discover** | The model selects, adapts and structures reasoning modules into a plan, then follows the plan. |
| **Self-preference bias** | A model judge's tendency to rate text like its own more highly; one reason the judge here is a different model family from the answer model. |
| **Semantic cache** | Reuse a stored answer when a new question is close enough to an old one in embedding space. |
| **Semantic routing** | Pick a route by comparing the query's embedding with labelled example queries. |
| **Sparse vector** | A vector stored as its few non-zero dimensions, such as one weight for each word in a text. Qdrant stores BM25 this way. |
| **SSE** | Server-Sent Events: a simple one-way HTTP stream from server to browser, used here for streaming answers. |
| **Stratified split** | A split that keeps each category's share (here, question type) the same on both sides. |
| **Text-to-SQL** | Turning a natural-language question into a SQL query. |
| **Transition report (10-KT)** | An annual report covering a short period, filed when a company changes its fiscal year end. |
| **XBRL** | The tagged data format companies use to file financial statements. Each number carries a concept tag, a period and a unit. |
