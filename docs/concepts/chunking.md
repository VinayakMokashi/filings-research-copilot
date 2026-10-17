# Chunking

> A chunk is the unit search can return. Its size and its boundaries decide what an embedding can represent and what an answer model gets to read.

**Lands in:** Phase 2 · **Code:** `src/copilot/ingest/chunking.py`

## What it is

Search doesn't return whole filings; it returns pieces of them. **Chunking** decides where those pieces begin and end. Every chunk here is a character span of its document, and it remembers the pages it touches, the 10-K item it starts in, and the filing's company, fiscal period and form, so a result can be filtered, cited and expanded.

## Why we need it here

A 10-K runs from 60 to 550 pages and 30,000 to 250,000 tokens. The embedding model (bge-small) reads at most 512 tokens, so anything longer is cut off. Within that limit there is a trade-off:

- **Small chunks** give sharp embeddings (one topic per vector) but lose context: a table row without its header, a sentence that says "this decline" without saying what declined.
- **Large chunks** keep context but blur several topics into one vector, and they cost more of the answer model's context window per result.

Filings add their own problems: running headers on every page (removed by the parser), tables flattened to lines of numbers, and sections that start mid-page.

## How it works

The document is its pages joined by blank lines (`assemble`), so chunks can cross pages and still record which pages they cover. Every size is counted in bge-small's own tokens. Four strategies are compared:

| Strategy | Rule | Chunks (84 documents) | Median tokens |
|---|---|---|---|
| `page` | One chunk per page; a page over 480 tokens is split into windows within the page | 23,585 | 448 |
| `tokens-480` | Windows of up to 480 tokens that cross pages, 64 tokens of overlap | 21,899 | 462 |
| `tokens-256` | The same with 256 tokens and 32 of overlap | 39,573 | 242 |
| `semantic` | Breaks where the meaning shifts between sentences | Indexed for the 58 dev filings | |

**Where a window ends** (`window_spans`). A window never ends mid-word. Within its second half, it ends at the strongest break available: a blank line, then a line end, then the end of a sentence, and the latest such break. Only a paragraph with no break at all is cut hard. The overlap also starts at a break, so a repeated sentence is repeated whole.

**Semantic chunking** (`SemanticChunker`) cuts the text into units: sentences and paragraphs, with a table or other unit over 128 tokens split at line ends, and a unit under 24 tokens joined to the next. It embeds every unit, measures the cosine distance between neighbours, and starts a new chunk wherever the distance is above the document's 90th percentile. Chunks under 64 tokens join the next, and chunks over 480 are split like `tokens-480`.

**Late chunking** keeps the `tokens-480` boundaries but embeds them in context; see [late chunking](late-chunking.md).

## Where it lives in the code

| Piece | What it does |
|---|---|
| `assemble`, `AssembledDocument` | Pages joined into one text; page and section lookup for any span |
| `window_spans` | Token windows that end at the strongest break in reach |
| `TokenChunker`, `PageChunker`, `SemanticChunker` | The strategies |
| `Chunk.point_id` | A UUID from the chunk's SHA-256 id, used as its Qdrant point id |
| `scripts/chunk_corpus.py`, `scripts/index_corpus.py` | `poe chunk-corpus` (page and token strategies), `poe index-corpus` (all, including semantic) |

## How we measured it

The four strategies are compared with dense search inside each question's own filing, scored on FinanceBench dev evidence pages; see the [retrieval baseline report](../eval/retrieval-baseline.md).

## Pitfalls we hit

- **Pages are longer than the model's window.** The median page is 699 tokens, and 72% of pages exceed 512, so "one chunk per page" would hide the bottom of most pages from dense search. The page strategy splits long pages within the page.
- **PDF lines aren't sentences.** Extracted text breaks lines where the printed line ended, mid-sentence. The first semantic chunker embedded each line, so most units were fragments and every table row stood alone. Units are now sentences and paragraphs, with small ones joined.
- **Token counts depend on the tokenizer.** A chunk of 480 bge tokens can be over 512 tokens for jina's tokenizer, which late chunking had to allow for.

## Review questions

1. Why are chunk sizes counted in the embedding model's tokens rather than in characters or words?
2. What does 64 tokens of overlap buy, and what does it cost in index size?
3. Why does a window end at a blank line in its second half rather than exactly at 480 tokens?
4. A table spans the bottom of page 41 and the top of page 42. How does each strategy handle it?
5. Why might semantic chunking help narrative sections and hurt financial statements?

## References

- LangChain, [text splitters](https://python.langchain.com/docs/concepts/text_splitters/) (recursive character splitting).
- Kamradt, [The 5 levels of text splitting](https://github.com/FullStackRetrieval-com/RetrievalTutorials), 2024 (semantic chunking by embedding distance).
- Günther et al., [Late Chunking](https://arxiv.org/abs/2409.04701), 2024.
