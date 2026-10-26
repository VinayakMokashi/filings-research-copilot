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
| **Answer cache** | Stored answers served again when the same question, case, spacing and quote marks aside, comes from a new anonymous conversation; it matches questions exactly, unlike a semantic cache. |
| **Bi-encoder** | A model that embeds the query and each passage separately, so passage vectors can be computed ahead of time and searched quickly. The embedding models here are bi-encoders. |
| **BM25** | A keyword-ranking formula that scores documents by term frequency, term rarity and document length. Strong for exact terms such as tickers and line items. |
| **Bootstrap confidence interval** | Resample the eval questions with replacement many times, recompute the metric each time, and take percentiles to see how uncertain the number is. |
| **Cascade (routing)** | A cheap router decides when it is confident, and a more expensive one is asked otherwise. |
| **Centroid** | The average of a group's vectors. A route's centroid is the mean embedding of its example questions. |
| **Checkpointer** | Saves a graph's state after every step under a thread id, so a conversation can continue later, or after a crash, where it stopped. |
| **Chunk** | A piece of a document that gets its own embedding and can be retrieved on its own. |
| **CIK** | Central Index Key, the SEC's unique ID for each filer. |
| **Citation precision** | The share of cited sources that actually support the claim they're attached to. |
| **Cloud Run** | Google Cloud's service for running containers without managing servers; a service scales to zero when no requests arrive. |
| **Cohen's kappa** | Agreement between two raters corrected for the agreement chance alone would give: 1 is perfect, 0 is no better than chance. |
| **Company facts** | SEC's per-company JSON of every XBRL fact the company has filed, without dimensions, from `data.sec.gov/api/xbrl/companyfacts`. |
| **Conditional edge** | An edge whose destination a function chooses from the state; the router's branch to the six specialists is one. |
| **Context budget** | The most retrieved text, in tokens, that the answer prompt may hold: 3,000 here. |
| **Context hit** | Whether at least one evidence page is among the sources the answer model sees. An answer can't be better than its context. |
| **Corrective RAG** | Grade the retrieved documents before generating; if they're weak, rewrite the query or fall back. Here the answer model's own refusal is the grade, and the fallback is one search across all of the company's filings. |
| **Cross-encoder** | A model that reads the query and a passage together to score relevance. Slower than embedding search, but more precise. |
| **Data card** | A short document describing a dataset: source, licence, size, checksums, fields, splits and known issues. |
| **Demo window** | A period when the part of the cloud deployment that costs money while idle, here the database, is started for a demo and stopped afterwards. |
| **DNS rebinding** | An attack in which a web page gets the browser to send requests to a server on the reader's own machine under the page's own name; a server defends itself by accepting only the host names it expects. |
| **DSPy** | A framework that treats prompts as programs and optimises them against a metric. |
| **Duration and instant facts** | A duration fact covers a period with a start and end date (revenue for a year); an instant fact is measured on one date (total assets at the year end). |
| **Embedding** | A vector that represents meaning; similar texts get nearby vectors. |
| **Entity masking** | Replacing names (here company names and years) with placeholders before embedding, so similarity reflects what is asked rather than whom it is about. |
| **Execution accuracy (EX)** | Generated SQL counts as correct when it returns the same result as the gold query. |
| **Faithfulness** | Whether each sentence of an answer is supported by the sources it cites. An answer can be faithful and wrong (the cited page is the wrong one) or correct and unfaithful (the figure came from memory). |
| **Fallback chain** | Models tried in order when a role's own model keeps failing after retries. |
| **FinanceBench** | A benchmark of questions over real company filings, with answers and evidence pages. |
| **Follow-up rewriting** | Turning a question that depends on the conversation ("And in 2021?") into one that stands alone, before anything else runs. |
| **Git blob id** | The SHA-1 hash git computes over a file's contents. Used here to check every downloaded file against a manifest. |
| **Generation (tracing)** | A span for one model call, carrying the model's name, the tokens in and out, and their cost. |
| **Grounded answer** | An answer whose every claim cites a retrieved source that states it, so a reader can check it. |
| **Grouped split** | A split that keeps every item of a group (here, a company) on the same side, so nothing about the group leaks across. |
| **Held-out test set** | Questions set aside while building and opened only at milestones, so the reported result isn't tuned to them. |
| **Hit@k** | Whether at least one relevant item appears in the top k results: 1 or 0 for each question. |
| **HNSW** | A graph-based index for fast approximate nearest-neighbour search. |
| **Holm–Bonferroni correction** | Adjusts p-values when several comparisons are made at once, so the chance of any false win stays at the chosen level. |
| **Hybrid answer** | One answer built from two kinds of source: figures from a database query and explanations from document pages, each sentence citing the one it came from. |
| **Hybrid search** | Combining keyword (BM25) and semantic (dense) search. |
| **HyDE** | Hypothetical Document Embeddings: write a hypothetical answer, embed it, and search with that instead of the raw question. |
| **IDF** | Inverse document frequency: how rare a term is across the collection. BM25 multiplies each term's weight by it, so a rare word like a ticker counts for more than "the". |
| **Index card** | A JSON file kept beside each Qdrant collection, recording its models, query prefix, vector and HNSW settings, payload indexes, counts and timing. |
| **Indirect prompt injection** | Instructions hidden in content an application feeds its model, such as a retrieved page, rather than typed by the user. |
| **JSON mode** | A provider option that makes the model reply with one valid JSON object, so code can read the answer's fields. |
| **Langfuse** | An open-source store and viewer for traces of LLM applications, built on OpenTelemetry, with tokens, costs and sessions. |
| **LangGraph** | A library for building LLM workflows as state graphs with branches, loops and checkpoints. |
| **Late chunking** | Run long stretches of a document through a long-context embedding model, then average each chunk's token vectors, so the chunk's vector keeps the surrounding context. |
| **Leave-one-group-out evaluation** | Score each item with its whole group (here a seed and its paraphrases) removed from the examples, so a near-copy can't give the answer away. |
| **LiteLLM** | A library and proxy that gives one interface to many LLM providers, with retries and fallbacks. |
| **LLM router** | A router that asks a model which route a question needs, from the route definitions and a few examples. |
| **LLM-as-judge** | Using a model to grade answers against a reference by a written rubric. The judge itself has to be checked against human labels. |
| **Long-term memory** | What an assistant keeps about a user from one conversation to the next; here, short notes in a store, kept up to date by extracting facts and reconciling them with the notes already held. |
| **LoRA** | Low-Rank Adaptation: fine-tuning by training small low-rank adapter matrices instead of all the weights. |
| **McNemar's test** | A paired test for two systems' right-or-wrong outcomes that looks only at the questions where they disagree. |
| **MCP** | Model Context Protocol: a standard for connecting AI apps (hosts) to tools and data (servers). |
| **Model-call cache** | A file of model responses keyed by model, messages and parameters, so repeated experiment runs replay answers instead of spending quota. |
| **Mean pooling** | Turning a model's per-token vectors into one vector for the text by averaging them. |
| **Mem0** | A memory layer for agents (Chhikara et al., 2025) that extracts facts from each exchange and decides, against the stored memories, to add, update, delete or skip each one. |
| **MNRL** | MultipleNegativesRankingLoss: a contrastive loss that treats the other examples in a batch as negatives. |
| **Model role** | A named job (`strong`, `fast` or `small`) that code asks for instead of a specific model; settings decide which model fills it. |
| **Multi-query retrieval** | Asking a model for several rewordings of a question, searching each, and fusing the rankings. |
| **Multi-stage build** | A Dockerfile with several stages, where a later stage copies only what it needs from an earlier one, so build tools stay out of the final image. |
| **MRR** | Mean Reciprocal Rank: the average of 1/rank of the first relevant result. |
| **OIDC (for deploys)** | Lets GitHub Actions prove who it is to a cloud with short-lived tokens, so no keys are stored; Google Cloud does it through Workload Identity Federation. |
| **ONNX Runtime** | An engine that runs neural networks exported in the ONNX format quickly on a CPU. FastEmbed runs its models with it. |
| **OpenTelemetry** | The open standard for recording and sending traces, metrics and logs. |
| **Oracle-document setting** | A retrieval evaluation in which each question searches only the filing its evidence is in, isolating finding the page from finding the filing. |
| **Paired test** | Comparing two systems on the same questions, so that question-to-question noise cancels out. |
| **Payload index** | An index on a field stored with each Qdrant point, such as `company`, that makes searches filtered on that field fast. |
| **pdfium** | Google's PDF engine (used in Chrome); pypdfium2 is its Python binding and this project's parser. |
| **Permutation test** | A significance test that randomly swaps which system produced which score (here, flips the sign of each paired difference) to see how often chance alone gives a gap as large as the real one. |
| **Planner (hybrid answers)** | A model call that splits a question into the part a database answers (the figures) and the part the filings answer (the explanation), so each agent gets only its own part. |
| **Program-aided arithmetic** | The model writes a calculation as an expression and a safe evaluator computes it, instead of the model doing the arithmetic in its head (after PAL, Gao et al. 2022). |
| **Prompt injection** | Text that a model follows as an instruction although it arrived as data or as a user's request to break the rules; first in the OWASP Top 10 for LLM applications. |
| **Qdrant** | A vector database with dense and sparse vectors, filtering and hybrid queries. |
| **Query decomposition** | Splitting a question into the separate facts it needs (both parts of a ratio, both years of a change) and searching for each. |
| **Query understanding** | Reading the company, period and form out of a question and searching only the filings that match. |
| **Question quota** | How many questions the API answers in a day, per visitor and from everyone together, before it refuses with a 429. |
| **Readiness probe** | An endpoint that says whether a service can do its work now (its database reachable, its files present), as opposed to merely running; orchestrators send traffic only to ready instances. |
| **Recall@k** | The share of relevant items that appear in the top k results. |
| **Reference labels** | Labels a judge is checked against, made by someone or something other than the judge: ideally a person, here a stronger model. |
| **Request ID** | A unique id given to each HTTP request and returned in a header, so its logs, its events and any feedback on it can be tied together. |
| **Restatement** | A company revising a figure it reported earlier. The facts database keeps the first-reported value and the latest one. |
| **Router** | The first decision for every question: which part of the copilot answers it (doc, data, hybrid, brief, small talk or decline). |
| **RRF** | Reciprocal Rank Fusion: merge ranked lists by summing 1/(k + rank) for each item. |
| **Running header** | Text repeated at the top or bottom of most pages, such as a "Table of Contents" link or a page number. The parser removes it. |
| **Self-consistency** | Sample several reasoning paths and keep the majority answer. |
| **Self-Discover** | The model selects, adapts and structures reasoning modules into a plan, then follows the plan. |
| **Self-preference bias** | A model judge's tendency to rate text like its own more highly; one reason the judge here is a different model family from the answer model. |
| **Self-Refine** | A model improves its own output in rounds: generate, critique, revise (Madaan et al., 2023). The validator loop is a version with a specific critique: the sentences the sources don't support. |
| **Semantic cache** | Reuse a stored answer when a new question is close enough to an old one in embedding space. |
| **Semantic routing** | Pick a route by comparing the query's embedding with labelled example queries: the nearest examples vote, or the nearest route centroid wins. |
| **Span** | One piece of work in a trace, with a start, an end and a parent; here, one node of the graph. |
| **Sparse vector** | A vector stored as its few non-zero dimensions, such as one weight for each word in a text. Qdrant stores BM25 this way. |
| **SQL guardrails** | The checks that let a model's query run only if it is one read-only SELECT: a parser check, a read-only connection, an authorizer inside SQLite, and caps on rows, value size and time. |
| **SSE** | Server-Sent Events: a simple one-way HTTP stream from server to browser, used here for streaming answers. |
| **State graph** | A workflow as nodes (steps) and edges (what runs next) around one typed state that every node reads and updates. |
| **Stdio transport** | MCP over a child process's standard input and output: the host starts the server and they exchange newline-delimited JSON, so the server must keep its logs to standard error. |
| **Store (LangGraph)** | LangGraph's key-value storage for data that outlives one thread, organised by namespace; the notes about each user live under `("notes", user_id)`. |
| **Stratified split** | A split that keeps each category's share (here, question type) the same on both sides. |
| **Streamable HTTP** | MCP's HTTP transport: the server listens at one URL, and a response is plain JSON or a stream of server-sent events. |
| **Streamlit** | A Python library for data apps: the script runs from top to bottom on every interaction, and widgets keep their values between runs. |
| **Text-to-SQL** | Turning a natural-language question into a SQL query. |
| **Thread** | One conversation's id in a checkpointer: its turns and state live under it. |
| **Tool annotations** | Hints an MCP server gives about a tool, such as whether it only reads data; a host may use them to decide what to confirm, but should trust them only from a server it trusts. |
| **Trace** | The record of one run: here every node's start and end with its time, the nodes' own events and the response, as JSON lines. |
| **Transition report (10-KT)** | An annual report covering a short period, filed when a company changes its fiscal year end. |
| **Validator loop** | Checking an answer before it is shown and sending what fails back to the writer, a fixed number of times; here every cited sentence against its sources, at most twice, then the verified sentences or a refusal. |
| **Value linking** | Telling a Text-to-SQL model which database values a question refers to (a company's stored name, a metric's real key, the years covered), because the schema alone doesn't. |
| **Workload Identity Federation** | Google Cloud's way of letting an outside identity, such as a GitHub Actions run, act as a service account without a stored key. |
| **XBRL** | The tagged data format companies use to file financial statements. Each number carries a concept tag, a period and a unit. |
