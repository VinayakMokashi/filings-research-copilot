"""The data bundle the API image carries on Cloud Run (ADR-0031).

The bundle holds what the API, the MCP server and the worker read at start, and from
FinanceBench only the corpus's document names and labels:

- data/processed/facts.db, the facts database;
- data/processed/pages/<doc>.jsonl for the corpus's 84 filings, for the cited pages;
- data/processed/indexes/<collection>.json, the index card naming the query embedder;
- data/processed/corpus.jsonl, the corpus's metadata (`copilot.answer.agent.CORPUS_FILE`);
- data/models/models--Qdrant--bge-small-en-v1.5-onnx-Q and models--Qdrant--bm25,
  FastEmbed's model files, so the image starts with nothing to download.

The archive is deterministic (sorted entries, fixed times and owners, no links), so the
same data gives the same SHA-256, and an unchanged bundle needs no new upload.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import tarfile
from collections.abc import Iterator
from pathlib import Path

from copilot.answer.agent import CORPUS_FILE, corpus_documents
from copilot.config import Settings

MODELS = ("models--Qdrant--bge-small-en-v1.5-onnx-Q", "models--Qdrant--bm25")


def members(data_dir: Path, collection: str) -> Iterator[tuple[str, Path]]:
    """(name in the bundle, file on disk) for the database, the index card and the models."""
    processed = data_dir / "processed"
    yield "processed/facts.db", processed / "facts.db"
    yield f"processed/indexes/{collection}.json", processed / "indexes" / f"{collection}.json"
    for model in MODELS:
        root = data_dir / "models" / model
        # The bundle stores real files: a link in FastEmbed's cache is read through.
        for path in sorted(p for p in root.rglob("*") if p.is_file() and ".lock" not in p.name):
            yield f"models/{path.relative_to(data_dir / 'models').as_posix()}", path


def _info(name: str, size: int) -> tarfile.TarInfo:
    """An entry with fixed times and owners, so the archive depends on the data alone."""
    info = tarfile.TarInfo(name)
    info.size, info.mtime, info.mode, info.uid, info.gid = size, 0, 0o644, 0, 0
    return info


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build(out: Path, settings: Settings) -> tuple[str, int, int]:
    """Write the archive to `out`, streaming each file from `settings.data_dir`.

    Returns its SHA-256, its size and how many files it holds. Raises FileNotFoundError
    naming what is missing.
    """
    documents = corpus_documents(settings)
    corpus = "".join(document.model_dump_json() + "\n" for document in documents).encode()
    pages = settings.data_dir / "processed" / "pages"
    files = [
        *members(settings.data_dir, settings.collection),
        *((f"processed/pages/{d.doc_name}.jsonl", pages / f"{d.doc_name}.jsonl")
          for d in documents),
    ]  # fmt: skip
    missing = [str(path) for _, path in files if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"missing from the data folder: {missing[:5]}")

    out.parent.mkdir(parents=True, exist_ok=True)
    entries: list[tuple[str, Path | None]] = sorted(
        [*files, (CORPUS_FILE.as_posix(), None)], key=lambda entry: entry[0]
    )
    with (
        gzip.GzipFile(out, mode="wb", mtime=0) as gz,
        tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT) as tar,
    ):
        for name, path in entries:
            if path is None:
                tar.addfile(_info(name, len(corpus)), io.BytesIO(corpus))
                continue
            with path.open("rb") as f:
                tar.addfile(_info(name, path.stat().st_size), f)
    return sha256(out), out.stat().st_size, len(entries)
