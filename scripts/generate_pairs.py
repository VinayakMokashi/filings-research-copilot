"""Generate synthetic question-to-chunk pairs from training filings (step 2.6).

Samples chunks from the training filings (no test company, no dev-question filing), asks
the LLM for one question per chunk, and keeps the questions that pass the checks in
`copilot.training.pairs`. Every reply is written as it arrives: kept pairs to
data/processed/synthetic/pairs.jsonl and rejected replies, with the reason, to
rejected.jsonl. A rerun skips chunks already tried, so an interrupted or rate-limited run
just continues. Calls alternate between the fast and strong models, which have separate
quotas and phrase questions differently; a pause between calls keeps each model under its
per-minute limit. When a model's daily quota runs out (gpt-oss-120b allows 200,000 tokens a
day on Groq's free tier), the run stops cleanly; `--roles fast` continues with one model.

Usage: uv run poe generate-pairs --per-doc 6        (needs GROQ_API_KEY in .env)
       uv run poe generate-pairs --limit 5          (a quick check)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

from copilot.config import get_settings
from copilot.eval import financebench as fb
from copilot.eval.splits import load_split, read_split_file
from copilot.ingest.chunking import (
    Chunk,
    TokenChunker,
    assemble,
    bge_token_offsets,
    read_chunks,
    write_chunks,
)
from copilot.ingest.corpus import pages_path
from copilot.ingest.pdf import read_pages
from copilot.llm import LLMError, LLMGateway, LLMResponse, ModelRole
from copilot.logs import configure_logging
from copilot.training import pairs

MANIFEST = Path("data/reference/synthetic_pairs_manifest.json")
ATTEMPTS = 4
RATE_LIMIT_PAUSE_S = 30.0
PAUSE_S = 8.0
ROLES: tuple[ModelRole, ...] = ("fast", "strong")
QUOTA_EXHAUSTED = 3


def load_chunks(name: str, documents: dict[str, fb.Document], data_dir: Path) -> list[Chunk]:
    """The filing's tokens-480 chunks, chunking and caching it first if needed."""
    path = data_dir / "processed" / "chunks" / "tokens-480" / f"{name}.jsonl"
    if path.exists():
        return read_chunks(path)
    pages = read_pages(pages_path(data_dir / "processed" / "pages", name))
    chunks = TokenChunker(bge_token_offsets(), 480, 64).chunk(assemble(pages, documents[name]))
    write_chunks(chunks, path)
    return chunks


def ask(gateway: LLMGateway, chunk: Chunk, role: ModelRole) -> LLMResponse:
    for attempt in range(1, ATTEMPTS + 1):
        try:
            return gateway.complete(
                pairs.question_messages(chunk), role=role, temperature=0.7, max_tokens=2048
            )
        except LLMError as exc:
            if not exc.rate_limited or attempt == ATTEMPTS:
                raise
            time.sleep(RATE_LIMIT_PAUSE_S * attempt)
    raise AssertionError("unreachable")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--per-doc", type=int, default=6, help="chunks sampled per filing")
    parser.add_argument("--limit", type=int, help="stop after this many model calls")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--roles", default="fast,strong", help="model roles to alternate between, comma-separated"
    )
    parser.add_argument(
        "--manifest-only", action="store_true", help="only rewrite the manifest from the files"
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)
    out_dir = settings.data_dir / "processed" / "synthetic"
    kept_path, rejected_path = out_dir / "pairs.jsonl", out_dir / "rejected.jsonl"
    if args.manifest_only:
        write_manifest(kept_path, rejected_path)
        return 0
    roles = tuple(role for role in ROLES if role in args.roles.split(","))
    if not roles:
        parser.error(f"--roles must name at least one of {', '.join(ROLES)}")
    if settings.groq_api_key is None:
        print("GROQ_API_KEY is not set. Add it to .env and try again.", file=sys.stderr)
        return 1
    root = settings.data_dir / "raw" / "financebench"
    documents = fb.load_documents(root)
    dev_documents = {question.doc_name for question in load_split("dev", root)}
    test_companies = set(read_split_file().test_companies)
    parsed = {path.stem for path in (settings.data_dir / "processed" / "pages").glob("*.jsonl")}
    names = pairs.training_documents(documents, test_companies, dev_documents, parsed)

    chunks = [chunk for name in names for chunk in load_chunks(name, documents, settings.data_dir)]
    sample = pairs.sample_chunks(chunks, args.per_doc, args.seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    tried = {
        json.loads(line)["chunk_id"]
        for path in (kept_path, rejected_path)
        if path.exists()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    todo = [chunk for chunk in sample if chunk.chunk_id not in tried][: args.limit]
    print(f"{len(names)} training filings, {len(sample)} chunks sampled, {len(todo)} to ask")

    gateway = LLMGateway(settings)
    outcome: Counter[str] = Counter()
    with (
        kept_path.open("a", encoding="utf-8", newline="\n") as kept,
        rejected_path.open("a", encoding="utf-8", newline="\n") as rejected,
    ):
        for number, chunk in enumerate(todo, start=1):
            role = roles[number % len(roles)]
            try:
                response = ask(gateway, chunk, role)
            except LLMError as exc:
                if not exc.rate_limited:
                    raise
                print(f"The {role} model's quota is used up; run again later to continue.")
                write_manifest(kept_path, rejected_path)
                return QUOTA_EXHAUSTED
            question = pairs.parse_question(response.text)
            reason = None
            if question is None:
                reason = "format"
            elif pairs.copies_chunk(question, chunk.text):
                reason = "copied"
            if reason is None and question is not None:
                pair = pairs.Pair(
                    chunk_id=chunk.chunk_id,
                    doc_name=chunk.doc_name,
                    company=chunk.company,
                    doc_period=chunk.doc_period,
                    doc_type=chunk.doc_type,
                    question=question,
                    model=response.model,
                )
                kept.write(pair.model_dump_json() + "\n")
                kept.flush()
                outcome["kept"] += 1
            else:
                record = {"chunk_id": chunk.chunk_id, "reason": reason, "reply": response.text}
                rejected.write(json.dumps(record, ensure_ascii=False) + "\n")
                rejected.flush()
                outcome[str(reason)] += 1
            if number % 25 == 0:
                print(f"  {number}/{len(todo)}: {dict(outcome)}")
            time.sleep(PAUSE_S)
    print(f"Done: {dict(outcome)}; pairs in {kept_path}")
    write_manifest(kept_path, rejected_path)
    return 0


def write_manifest(kept_path: Path, rejected_path: Path) -> None:
    """Counts and the pairs file's checksum, committed so the set used in Phase 7 is on record."""
    summary = pairs.summarise(kept_path, rejected_path)
    MANIFEST.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"Wrote {MANIFEST}: {summary['pairs']} pairs from {summary['filings']} filings")


if __name__ == "__main__":
    raise SystemExit(main())
