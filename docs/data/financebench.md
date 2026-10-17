# Data card: FinanceBench (open-source sample)

| | |
|---|---|
| **Source** | [patronus-ai/financebench](https://github.com/patronus-ai/financebench), pinned to commit `cc39aeb4afdf33909ee1412188bf89035950c2eb` (2024-12-03) |
| **Paper** | Islam et al., *FinanceBench: A New Benchmark for Financial Question Answering* (2023), [arXiv:2311.11944](https://arxiv.org/abs/2311.11944) |
| **Licence** | CC BY-NC 4.0, as stated on the [Hugging Face dataset card](https://huggingface.co/datasets/PatronusAI/financebench). The GitHub repository has no licence file. |
| **Use here** | Evaluation only, non-commercial. The files are downloaded and never committed: the repository holds only the manifest, question ids and checksums. |
| **Downloaded** | 2026-10-17 |
| **Fetch** | `uv run poe fetch-financebench` gets the question files and the 84 PDFs the questions use (159 MB). `--pdfs all` gets all 368 PDFs (706 MB). |

## What's in it

- **150 questions**, 50 of each type:
  - `metrics-generated`: a figure or ratio from the financial statements, such as capital expenditure or the quick ratio.
  - `domain-relevant`: 25 generic analyst questions, each asked of about two companies.
  - `novel-generated`: questions written for one specific filing.
- **84 documents from 32 companies**: 64 10-Ks, 8 10-Qs, 6 8-Ks and 6 earnings releases. Fiscal periods run from 2015 to 2024, and most questions are about 2022 and 2023.
- Each question has an answer, sometimes a justification, and one to three evidence passages (115 questions have one, 31 have two, 4 have three). Each passage names its document and page.
- The wider corpus: the document file describes 361 filings from 40 companies, and the repository holds 368 PDFs. Eight companies have filings but no questions: Apple, eBay, FedEx, Intel, McDonald's, Oracle, PG&E and Salesforce.

## Fields used

| Field | Used for |
|---|---|
| `financebench_id` | The question id (`Question.id`) |
| `company`, `doc_name` | Grouping the split; finding the PDF |
| `question_type` | Stratifying the split; reporting results by type |
| `question`, `answer`, `justification` | The question and its gold answer, for the Phase 3 judge |
| `evidence[].doc_name`, `evidence[].evidence_page_num` | Gold pages for retrieval recall and MRR (Phase 2) |
| `evidence[].evidence_text`, `evidence[].evidence_text_full_page` | Checking page alignment; error analysis |
| Document file: `doc_type`, `gics_sector`, `doc_period`, `doc_link` | Balancing the split; describing the corpus |

`question_reasoning`, `domain_question_num` and `dataset_subset_label` are loaded but not used yet. The loader declares every source field and rejects unknown ones, so a changed file fails loudly.

## Checksums

| File | Size | Git blob id | SHA-256 |
|---|---|---|---|
| `data/financebench_open_source.jsonl` | 929,848 bytes | `4aef1d43a443474ba193f158f2baf70550ff528d` | `a5a2aa673e573e55675fc3c0f9aa38c1cf59d2abc91edb077534f71f10a71877` |
| `data/financebench_document_information.jsonl` | 88,781 bytes | `decdfa948630f289d05cc0048417b3b9107cfb9f` | `1c69127783879de8cdadb159d2181f39bc3123b8e0ebf74031c3969d69189575` |

The size and git blob id of every PDF are in [`data/reference/financebench_manifest.json`](../../data/reference/financebench_manifest.json). `fetch` checks each download against it before writing anything, and skips files already present and verified, so a rerun resumes.

## Splits

The split was made once, before any tuning, with `uv run poe split-financebench` ([ADR-0006](../decisions/0006-evaluation-splits.md)), and is recorded in [`eval/financebench/splits.json`](../../eval/financebench/splits.json).

| | Dev | Test (held out) |
|---|---|---|
| Questions | 100 | 50 |
| Companies | 20 | 12 |
| Documents | 58 | 26 |
| Metrics-generated / domain-relevant / novel-generated | 33 / 34 / 33 | 17 / 16 / 17 |
| 10-K / 10-Q / 8-K / earnings | 74 / 12 / 6 / 8 | 38 / 3 / 3 / 6 |

- **Test companies:** AES Corporation, AMD, Amazon, Corning, Kraft Heinz, Lockheed Martin, Microsoft, Netflix, PayPal, PepsiCo, Pfizer and Ulta Beauty.
- **Test-set checksum** (SHA-256 of the canonical records): `244383209a16e05763c27ed1d1f122e232d1ea9c6d9bc1fb827a4cf7370a64c0`.
- Every sector with more than one company appears on both sides. Materials has a single company (Amcor), which is in dev.

## Parsed pages

`uv run poe parse-pdfs` turns the PDFs into clean page text ([ADR-0009](../decisions/0009-pdf-parsing.md)). The 84 question documents have 12,013 pages, 82 of them images with no text. Every dev evidence passage but one lines up with the parsed page of the same index, with a median word overlap of 0.99 ([report](../../eval/results/parsing/page-alignment-dev.md)); the exception is still the closest page.

## Known issues

- **Page numbers start at 0.** `evidence_page_num` is a PDF page index counted from 0. On 12 evidence passages in three documents, the text of page index *n* matched the evidence (similarity at least 0.98) and page *n* − 1 didn't. Citations shown to people add 1.
- **Many answers are free text.** Answers like "No, the company is managing its CAPEX…" need an LLM judge checked against human labels (Phase 3), not exact matching.
- **Templates repeat.** Each of the 25 domain-relevant templates is asked of about two companies, so 12 of the 16 test domain-relevant questions share a template with a dev question. Results are reported by question type; novel-generated questions give the cleanest read.
- **Models may have seen it.** The dataset has been public since November 2023, so language models may have trained on it. Results are read with that in mind (Plan §9).
- **The test set is small.** At 50 questions, a 95% confidence interval on an accuracy near 50% spans about ±14 points. Decisions rest on paired comparisons on dev (Plan §2).
- **Some fields are empty.** `question_reasoning` is empty for every novel-generated question, and `justification` is empty for 25 domain-relevant and 25 novel-generated questions.
- Seven PDFs in the repository have no entry in the document file.
- **39 of the 84 question PDFs are encrypted** (owner-password protected, readable without a password). pdfium opens them; some other parsers need extra packages.

## Citation

```bibtex
@misc{islam2023financebench,
  title={FinanceBench: A New Benchmark for Financial Question Answering},
  author={Pranab Islam and Anand Kannappan and Douwe Kiela and Rebecca Qian and Nino Scherrer and Bertie Vidgen},
  year={2023},
  eprint={2311.11944},
  archivePrefix={arXiv},
  primaryClass={cs.CL}
}
```
