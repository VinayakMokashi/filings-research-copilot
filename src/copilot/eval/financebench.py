"""FinanceBench, the benchmark the copilot is judged on.

FinanceBench (Islam et al., 2023) asks questions about real 10-K, 10-Q, 8-K and earnings
documents, and gives the answer and the evidence pages for each one. The open-source
sample has 150 questions over 84 documents from 32 companies.

The files come from the authors' GitHub repository, pinned to one commit. The dataset is
licensed CC BY-NC 4.0 (per its Hugging Face card), so it is downloaded into
`data/raw/financebench/` and never committed. Every file is checked against the git blob
id in the committed manifest, so every machine evaluates on identical bytes.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
from urllib.parse import quote

import httpx
from pydantic import BaseModel, ConfigDict, Field

from copilot.logs import get_logger

REPO = "patronus-ai/financebench"
COMMIT = "cc39aeb4afdf33909ee1412188bf89035950c2eb"
QUESTIONS_PATH = "data/financebench_open_source.jsonl"
DOCUMENTS_PATH = "data/financebench_document_information.jsonl"
MANIFEST_FILE = Path("data/reference/financebench_manifest.json")

_RAW_URL = "https://raw.githubusercontent.com/{repo}/{commit}/{path}"
_TREE_URL = "https://api.github.com/repos/{repo}/git/trees/{commit}?recursive=1"

QuestionType = Literal["metrics-generated", "domain-relevant", "novel-generated"]
QUESTION_TYPES: tuple[QuestionType, ...] = (
    "metrics-generated",
    "domain-relevant",
    "novel-generated",
)
PdfSelection = Literal["referenced", "all", "none"]

log = get_logger(__name__)


class Evidence(BaseModel):
    """One evidence passage for a question.

    `page` is a 0-based PDF page index, as FinanceBench stores it: the text of page index
    `page` matches the evidence, and page `page - 1` doesn't. Add 1 before showing it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    doc_name: str
    page: int = Field(validation_alias="evidence_page_num", ge=0)
    text: str = Field(validation_alias="evidence_text")
    page_text: str = Field(validation_alias="evidence_text_full_page")


class Question(BaseModel):
    """One FinanceBench question. Every source field is declared, so a changed file fails."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(validation_alias="financebench_id")
    company: str
    doc_name: str
    question_type: QuestionType
    question_reasoning: str | None
    domain_question_num: str | None
    question: str
    answer: str
    justification: str | None
    dataset_subset_label: str
    evidence: tuple[Evidence, ...] = Field(min_length=1)


class Document(BaseModel):
    """Metadata for one source document."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    doc_name: str
    company: str
    gics_sector: str
    doc_type: str
    doc_period: int
    doc_link: str


class ManifestFile(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str
    size: int = Field(ge=0)
    git_sha1: str = Field(pattern=r"^[0-9a-f]{40}$")


class Manifest(BaseModel):
    """The question files and PDFs at the pinned commit, with their sizes and git blob ids."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    repo: str
    commit: str
    files: tuple[ManifestFile, ...]

    def file(self, path: str) -> ManifestFile:
        for entry in self.files:
            if entry.path == path:
                return entry
        raise KeyError(f"{path} is not in the FinanceBench manifest.")

    @property
    def pdfs(self) -> tuple[ManifestFile, ...]:
        return tuple(entry for entry in self.files if entry.path.startswith("pdfs/"))


class ChecksumError(RuntimeError):
    """Data on disk or from the network doesn't match what was recorded."""


@dataclass(frozen=True, slots=True)
class FetchReport:
    downloaded: int
    already_present: int


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Parse a JSON Lines file, skipping blank lines."""
    with path.open(encoding="utf-8") as lines:
        return [json.loads(line) for line in lines if line.strip()]


def load_questions(root: Path) -> list[Question]:
    """The questions in file order, from a fetched copy under `root`."""
    return [Question.model_validate(record) for record in read_jsonl(root / QUESTIONS_PATH)]


def load_documents(root: Path) -> dict[str, Document]:
    """Document metadata keyed by `doc_name`, from a fetched copy under `root`."""
    documents = (Document.model_validate(r) for r in read_jsonl(root / DOCUMENTS_PATH))
    return {document.doc_name: document for document in documents}


def pdf_path(root: Path, doc_name: str) -> Path:
    return root / "pdfs" / f"{doc_name}.pdf"


def load_manifest(path: Path = MANIFEST_FILE) -> Manifest:
    return Manifest.model_validate_json(path.read_text(encoding="utf-8"))


def save_manifest(manifest: Manifest, path: Path = MANIFEST_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n")


def git_blob_sha1(data: bytes) -> str:
    """The id git gives a file with these contents, as `git hash-object` prints it."""
    return hashlib.sha1(b"blob %d\0" % len(data) + data, usedforsecurity=False).hexdigest()


def _matches(data: bytes, expected: ManifestFile) -> bool:
    return len(data) == expected.size and git_blob_sha1(data) == expected.git_sha1


def download_verified(client: httpx.Client, url: str, dest: Path, expected: ManifestFile) -> bool:
    """Download `url` to `dest` unless a verified copy is already there.

    The bytes are checked before anything is written, and the file appears through a
    single rename, so an interrupted or corrupted download never looks complete.
    Returns True if a download happened.
    """
    if dest.is_file() and _matches(dest.read_bytes(), expected):
        return False
    response = client.get(url)
    response.raise_for_status()
    data = response.content
    if not _matches(data, expected):
        raise ChecksumError(
            f"{expected.path}: the download doesn't match the manifest ({len(data)} bytes, "
            f"expected {expected.size} with git blob {expected.git_sha1})."
        )
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_name(dest.name + ".part")
    partial.write_bytes(data)
    partial.replace(dest)
    return True


def build_manifest(client: httpx.Client) -> Manifest:
    """List the question files and PDFs at the pinned commit, using GitHub's tree API."""
    response = client.get(_TREE_URL.format(repo=REPO, commit=COMMIT))
    response.raise_for_status()
    tree = response.json()
    if tree.get("truncated"):
        raise RuntimeError("GitHub truncated the file listing, so the manifest would be partial.")
    wanted = {QUESTIONS_PATH, DOCUMENTS_PATH}
    files = [
        ManifestFile(path=item["path"], size=item["size"], git_sha1=item["sha"])
        for item in tree["tree"]
        if item["type"] == "blob"
        and (
            item["path"] in wanted
            or (item["path"].startswith("pdfs/") and item["path"].endswith(".pdf"))
        )
    ]
    missing = wanted - {entry.path for entry in files}
    if missing:
        raise RuntimeError(f"The pinned commit has no {', '.join(sorted(missing))}.")
    return Manifest(
        repo=REPO, commit=COMMIT, files=tuple(sorted(files, key=lambda entry: entry.path))
    )


def fetch(
    client: httpx.Client,
    root: Path,
    manifest: Manifest,
    pdfs: PdfSelection = "referenced",
) -> FetchReport:
    """Download the question files and the selected PDFs into `root`, verifying each one.

    `referenced` fetches only the PDFs that questions point to; `all` fetches every PDF in
    the repository. Files already present and verified are skipped, so a rerun resumes.
    """
    if (manifest.repo, manifest.commit) != (REPO, COMMIT):
        raise ValueError(
            f"The manifest is for {manifest.repo}@{manifest.commit[:12]}, "
            f"but the code is pinned to {REPO}@{COMMIT[:12]}."
        )
    targets = [manifest.file(QUESTIONS_PATH), manifest.file(DOCUMENTS_PATH)]
    counts = [_fetch_one(client, root, manifest, entry) for entry in targets]
    if pdfs == "all":
        targets = list(manifest.pdfs)
    elif pdfs == "referenced":
        names = sorted({question.doc_name for question in load_questions(root)})
        targets = [manifest.file(f"pdfs/{name}.pdf") for name in names]
    else:
        targets = []
    counts += [_fetch_one(client, root, manifest, entry) for entry in targets]
    return FetchReport(downloaded=sum(counts), already_present=len(counts) - sum(counts))


def _fetch_one(client: httpx.Client, root: Path, manifest: Manifest, entry: ManifestFile) -> bool:
    url = _RAW_URL.format(repo=manifest.repo, commit=manifest.commit, path=quote(entry.path))
    downloaded = download_verified(client, url, root / entry.path, entry)
    if downloaded:
        log.info("financebench.downloaded", path=entry.path, size=entry.size)
    return downloaded
