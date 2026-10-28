"""Index one filing into the doc agent's collection, as an ingestion job (ADR-0031).

The steps are the corpus's own (Phase 2):

1. download the filing's PDF;
2. keep a copy in the filings bucket;
3. parse it into pages with pdfium;
4. chunk it one page at a time;
5. embed the chunks with bge-small and BM25;
6. upsert the chunks the collection lacks.

A chunk's id comes from its content, so indexing the same filing twice adds nothing, and
a retried message is harmless.

Everything runs offline once the PDF is in. The tokenizer for page windows is the one in
the bundled bge-small model, since the image may not download (`HF_HUB_OFFLINE=1`).

A filing indexed here is searchable at once. The doc agent's resolver, however, knows
the 84 corpus filings by name, so questions about a new company or year find it only
once the corpus list includes it (`data/processed/corpus.jsonl`).
"""

from __future__ import annotations

import tempfile
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, Field, HttpUrl, field_validator
from qdrant_client import QdrantClient

from copilot.config import Settings
from copilot.eval.financebench import Document
from copilot.ingest.chunking import Chunk, PageChunker, TokenOffsets, assemble, bge_token_offsets
from copilot.ingest.embed import FastEmbedBM25, FastEmbedDense, SparseEmbedder
from copilot.ingest.index import index_chunks
from copilot.ingest.jobs import JobResult
from copilot.ingest.pdf import Page, parse_document

MAX_PDF_BYTES = 60_000_000  # a 10-K is a few megabytes; anything near this is a mistake
METADATA_TOKEN = (
    "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token"
)


class IngestRequest(BaseModel):
    """What a message asks for: one filing's PDF and how to label it."""

    doc_name: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{2,119}$")
    url: HttpUrl
    company: str = Field(min_length=1, max_length=120)
    doc_type: str = Field(pattern=r"^(10k|10q|8k|earnings)$")
    doc_period: int = Field(ge=1990, le=2100)
    gics_sector: str = ""

    @field_validator("url")
    @classmethod
    def _https(cls, url: HttpUrl) -> HttpUrl:
        if url.scheme != "https":
            raise ValueError("the PDF must come over HTTPS")
        return url

    def document(self) -> Document:
        return Document(
            doc_name=self.doc_name,
            company=self.company,
            gics_sector=self.gics_sector,
            doc_type=self.doc_type,
            doc_period=self.doc_period,
            doc_link=str(self.url),
        )


def download(url: str, user_agent: str | None) -> bytes:
    """The PDF at `url`. SEC asks every client for a contact in its User-Agent."""
    host = urlsplit(url).hostname or ""
    headers = {"User-Agent": user_agent} if user_agent and host.endswith("sec.gov") else {}
    with httpx.stream("GET", url, headers=headers, timeout=120, follow_redirects=True) as response:
        response.raise_for_status()
        data = bytearray()
        for chunk in response.iter_bytes(1 << 20):
            data.extend(chunk)
            if len(data) > MAX_PDF_BYTES:
                raise ValueError(f"{url} is larger than {MAX_PDF_BYTES:,} bytes")
    if not bytes(data[:5]).startswith(b"%PDF"):
        raise ValueError(f"{url} did not return a PDF")
    return bytes(data)


def store_in_bucket(bucket: str, name: str, data: bytes) -> None:
    """Upload to Cloud Storage with the service account's token, from the metadata server."""
    token = httpx.get(METADATA_TOKEN, headers={"Metadata-Flavor": "Google"}, timeout=5).json()
    httpx.post(
        f"https://storage.googleapis.com/upload/storage/v1/b/{bucket}/o",
        params={"uploadType": "media", "name": name},
        headers={
            "Authorization": f"Bearer {token['access_token']}",
            "Content-Type": "application/pdf",
        },
        content=data,
        timeout=120,
    ).raise_for_status()


def bundled_token_offsets(models_dir: Path) -> TokenOffsets:
    """bge-small's tokenizer from the bundled model files, so nothing is downloaded; the
    Hub's copy when the bundle isn't there (a local run)."""
    pattern = "models--Qdrant--bge-small-en-v1.5-onnx-Q/snapshots/*/tokenizer.json"
    found = sorted(models_dir.glob(pattern))
    if not found:
        return bge_token_offsets()
    from tokenizers import Tokenizer

    tokenizer = Tokenizer.from_file(str(found[0]))

    def offsets(text: str) -> list[tuple[int, int]]:
        spans = tokenizer.encode(text, add_special_tokens=False).offsets
        return [span for span in spans if span[1] > span[0]]

    return offsets


Parse = Callable[[Path, str, str], list[Page]]


class Ingester:
    """Indexes filings into one collection; the models load once, on the first filing."""

    def __init__(
        self,
        settings: Settings,
        *,
        client: QdrantClient | None = None,
        fetch: Callable[[str, str | None], bytes] = download,
        store: Callable[[str, bytes], None] | None = None,
        parse: Parse = parse_document,
        embed: Callable[[Sequence[Chunk]], NDArray[np.float32]] | None = None,
        sparse: SparseEmbedder | None = None,
        offsets: TokenOffsets | None = None,
    ) -> None:
        self.settings = settings
        key = settings.qdrant_api_key
        self.client = client or QdrantClient(
            url=settings.qdrant_url,
            api_key=key.get_secret_value() if key else None,
            timeout=120,
        )
        self.fetch = fetch
        bucket = settings.filings_bucket
        self.store = store if store is not None else (
            (lambda name, data: store_in_bucket(bucket, name, data)) if bucket else None
        )  # fmt: skip
        self.parse = parse
        self._embed = embed
        self._sparse = sparse
        self._offsets = offsets

    def _models(
        self,
    ) -> tuple[Callable[[Sequence[Chunk]], NDArray[np.float32]], SparseEmbedder, TokenOffsets]:
        models_dir = self.settings.data_dir / "models"
        if self._embed is None:
            dense = FastEmbedDense(cache_dir=models_dir)
            self._embed = lambda batch: dense.embed_documents([c.text for c in batch])
        if self._sparse is None:
            self._sparse = FastEmbedBM25(cache_dir=models_dir)
        if self._offsets is None:
            self._offsets = bundled_token_offsets(models_dir)
        return self._embed, self._sparse, self._offsets

    def __call__(self, request: IngestRequest) -> JobResult:
        started = time.perf_counter()
        pdf = self.fetch(str(request.url), self.settings.sec_user_agent)
        if self.store is not None:
            self.store(f"{request.doc_name}.pdf", pdf)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / f"{request.doc_name}.pdf"
            path.write_bytes(pdf)
            pages = self.parse(path, request.doc_name, request.doc_type)
        embed, sparse, offsets = self._models()
        chunks = PageChunker(offsets, max_tokens=480).chunk(assemble(pages, request.document()))
        added = index_chunks(self.client, self.settings.collection, chunks, embed, sparse)
        return JobResult(
            request.doc_name, len(chunks), added, round(time.perf_counter() - started, 2)
        )
