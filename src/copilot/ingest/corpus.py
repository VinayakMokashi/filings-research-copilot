"""Parse the whole FinanceBench corpus into page files, resumably.

Each PDF becomes `data/processed/pages/<doc_name>.jsonl`. A manifest records the parser
version and the git blob id of each PDF, so a rerun parses only documents that are new, have
changed, or were parsed by an older parser. PDFs are parsed in separate worker processes,
because pdfium isn't thread-safe.
"""

from __future__ import annotations

from collections.abc import Mapping
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from copilot.eval.financebench import Document, git_blob_sha1
from copilot.ingest.pdf import PARSER_VERSION, parse_document, read_pages, write_pages

MANIFEST_NAME = "_manifest.json"
EMPTY_PAGE_CHARS = 30


class ParsedDoc(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    git_sha1: str
    doc_type: str
    pages: int
    empty_pages: int
    sectioned_pages: int


class ParseManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parser_version: str
    docs: dict[str, ParsedDoc]


@dataclass(frozen=True, slots=True)
class ParseReport:
    parsed: int
    skipped: int
    manifest: ParseManifest


def pages_path(out_dir: Path, doc_name: str) -> Path:
    return out_dir / f"{doc_name}.jsonl"


def load_manifest(out_dir: Path) -> ParseManifest:
    path = out_dir / MANIFEST_NAME
    if not path.is_file():
        return ParseManifest(parser_version=PARSER_VERSION, docs={})
    return ParseManifest.model_validate_json(path.read_text(encoding="utf-8"))


def _parse_one(job: tuple[Path, Path, str, str, str]) -> tuple[str, ParsedDoc]:
    pdf, out_dir, doc_name, doc_type, sha1 = job
    pages = parse_document(pdf, doc_name, doc_type)
    write_pages(pages, pages_path(out_dir, doc_name))
    return doc_name, ParsedDoc(
        git_sha1=sha1,
        doc_type=doc_type,
        pages=len(pages),
        empty_pages=sum(len(p.text.strip()) < EMPTY_PAGE_CHARS for p in pages),
        sectioned_pages=sum(p.section is not None or bool(p.headings) for p in pages),
    )


def parse_corpus(
    pdf_dir: Path,
    out_dir: Path,
    documents: Mapping[str, Document],
    *,
    workers: int = 8,
) -> ParseReport:
    """Parse every PDF in `pdf_dir` that the manifest doesn't already cover.

    `workers=1` parses in this process, which tests rely on.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest(out_dir)
    if manifest.parser_version != PARSER_VERSION:
        manifest = ParseManifest(parser_version=PARSER_VERSION, docs={})
    jobs = []
    for pdf in sorted(pdf_dir.glob("*.pdf")):
        doc_name = pdf.stem
        sha1 = git_blob_sha1(pdf.read_bytes())
        known = manifest.docs.get(doc_name)
        if known is not None and known.git_sha1 == sha1 and pages_path(out_dir, doc_name).is_file():
            continue
        doc_type = documents[doc_name].doc_type if doc_name in documents else "unknown"
        jobs.append((pdf, out_dir, doc_name, doc_type, sha1))
    if jobs and workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            for doc_name, parsed in pool.map(_parse_one, jobs):
                manifest.docs[doc_name] = parsed
                _save(manifest, out_dir)  # after each document, so an interruption loses little
    else:
        for job in jobs:
            doc_name, parsed = _parse_one(job)
            manifest.docs[doc_name] = parsed
            _save(manifest, out_dir)
    total = len(list(pdf_dir.glob("*.pdf")))
    return ParseReport(parsed=len(jobs), skipped=total - len(jobs), manifest=manifest)


def _save(manifest: ParseManifest, out_dir: Path) -> None:
    ordered = ParseManifest(
        parser_version=manifest.parser_version, docs=dict(sorted(manifest.docs.items()))
    )
    (out_dir / MANIFEST_NAME).write_text(
        ordered.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n"
    )


def page_text(out_dir: Path, doc_name: str) -> list[str]:
    """The clean text of every page of one parsed document."""
    return [page.text for page in read_pages(pages_path(out_dir, doc_name))]


def manifest_summary(manifest: ParseManifest) -> dict[str, int]:
    docs = manifest.docs.values()
    return {
        "documents": len(manifest.docs),
        "pages": sum(d.pages for d in docs),
        "empty_pages": sum(d.empty_pages for d in docs),
        "ten_k_pages": sum(d.pages for d in docs if d.doc_type == "10k"),
        "ten_k_sectioned_pages": sum(d.sectioned_pages for d in docs if d.doc_type == "10k"),
    }
