"""FinanceBench records, the manifest, and verified downloads (no network: mocked transport)."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import ValidationError

from copilot.eval import financebench as fb

ROOT = Path(__file__).resolve().parents[1]
RecordFactory = Callable[..., dict[str, Any]]


def _jsonl(records: list[dict[str, Any]]) -> bytes:
    return "".join(json.dumps(record) + "\n" for record in records).encode("utf-8")


def _document(doc_name: str, company: str = "Acme") -> dict[str, Any]:
    return {
        "doc_name": doc_name,
        "company": company,
        "gics_sector": "Industrials",
        "doc_type": "10k",
        "doc_period": 2022,
        "doc_link": f"https://example.com/{doc_name}.pdf",
    }


def _url(path: str) -> str:
    return f"https://raw.githubusercontent.com/{fb.REPO}/{fb.COMMIT}/{path}"


def _entry(path: str, data: bytes) -> fb.ManifestFile:
    return fb.ManifestFile(path=path, size=len(data), git_sha1=fb.git_blob_sha1(data))


class _Repo:
    """A fake raw.githubusercontent.com serving fixed files at the pinned commit."""

    def __init__(self, files: dict[str, bytes]) -> None:
        self.files = files
        self.requests: list[str] = []
        self.manifest = fb.Manifest(
            repo=fb.REPO,
            commit=fb.COMMIT,
            files=tuple(_entry(path, data) for path, data in sorted(files.items())),
        )

    def client(self) -> httpx.Client:
        prefix = f"/{fb.REPO}/{fb.COMMIT}/"

        def handler(request: httpx.Request) -> httpx.Response:
            path = request.url.path.removeprefix(prefix)
            self.requests.append(path)
            if path not in self.files:
                return httpx.Response(404)
            return httpx.Response(200, content=self.files[path])

        return httpx.Client(transport=httpx.MockTransport(handler))


@pytest.fixture
def repo(question_record: RecordFactory) -> _Repo:
    questions = [
        question_record(1, doc_name="ACME_2022_10K"),
        question_record(2, doc_name="ACME_2022_10K", question_type="domain-relevant"),
        question_record(3, doc_name="ACME_2023_10K", question_type="novel-generated"),
    ]
    documents = [_document(name) for name in ("ACME_2022_10K", "ACME_2023_10K", "ACME_2024_10K")]
    return _Repo(
        {
            fb.QUESTIONS_PATH: _jsonl(questions),
            fb.DOCUMENTS_PATH: _jsonl(documents),
            "pdfs/ACME_2022_10K.pdf": b"%PDF-1.7 2022",
            "pdfs/ACME_2023_10K.pdf": b"%PDF-1.7 2023",
            "pdfs/ACME_2024_10K.pdf": b"%PDF-1.7 2024",
        }
    )


def test_question_keeps_the_zero_based_page_index(question_record: RecordFactory) -> None:
    question = fb.Question.model_validate(question_record(7, page=59))

    assert question.id == "financebench_id_00007"
    assert question.evidence[0].page == 59
    assert question.evidence[0].doc_name == "ACME_2022_10K"


def test_unknown_fields_are_rejected(question_record: RecordFactory) -> None:
    record = question_record(1) | {"new_field": "surprise"}

    with pytest.raises(ValidationError, match="new_field"):
        fb.Question.model_validate(record)


def test_a_question_needs_evidence(question_record: RecordFactory) -> None:
    record = question_record(1) | {"evidence": []}

    with pytest.raises(ValidationError, match="evidence"):
        fb.Question.model_validate(record)


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (b"", "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"),
        (b"hello\n", "ce013625030ba8dba906f756967f9e9ca394464a"),
    ],
)
def test_git_blob_sha1_matches_git(data: bytes, expected: str) -> None:
    assert fb.git_blob_sha1(data) == expected


def test_download_writes_only_verified_bytes(tmp_path: Path) -> None:
    repo = _Repo({"pdfs/A.pdf": b"%PDF-1.7 a"})
    dest = tmp_path / "pdfs" / "A.pdf"
    url = _url("pdfs/A.pdf")

    with repo.client() as client:
        first = fb.download_verified(client, url, dest, repo.manifest.file("pdfs/A.pdf"))
        second = fb.download_verified(client, url, dest, repo.manifest.file("pdfs/A.pdf"))

    assert (first, second) == (True, False)
    assert dest.read_bytes() == b"%PDF-1.7 a"
    assert repo.requests == ["pdfs/A.pdf"]


def test_download_rejects_bytes_that_differ_from_the_manifest(tmp_path: Path) -> None:
    repo = _Repo({"pdfs/A.pdf": b"%PDF-1.7 tampered"})
    expected = _entry("pdfs/A.pdf", b"%PDF-1.7 original")
    dest = tmp_path / "pdfs" / "A.pdf"

    with repo.client() as client, pytest.raises(fb.ChecksumError, match=r"pdfs/A\.pdf"):
        fb.download_verified(client, _url("pdfs/A.pdf"), dest, expected)

    assert not dest.exists()
    assert not dest.with_name("A.pdf.part").exists()


def test_fetch_downloads_only_the_pdfs_questions_refer_to(tmp_path: Path, repo: _Repo) -> None:
    with repo.client() as client:
        first = fb.fetch(client, tmp_path, repo.manifest, "referenced")
        again = fb.fetch(client, tmp_path, repo.manifest, "referenced")

    assert first == fb.FetchReport(downloaded=4, already_present=0)
    assert again == fb.FetchReport(downloaded=0, already_present=4)
    assert fb.pdf_path(tmp_path, "ACME_2023_10K").is_file()
    assert not fb.pdf_path(tmp_path, "ACME_2024_10K").exists()
    assert [q.id for q in fb.load_questions(tmp_path)] == [
        "financebench_id_00001",
        "financebench_id_00002",
        "financebench_id_00003",
    ]
    assert set(fb.load_documents(tmp_path)) == {"ACME_2022_10K", "ACME_2023_10K", "ACME_2024_10K"}


@pytest.mark.parametrize(("selection", "pdf_count"), [("all", 3), ("none", 0)])
def test_fetch_pdf_selection(
    tmp_path: Path, repo: _Repo, selection: fb.PdfSelection, pdf_count: int
) -> None:
    with repo.client() as client:
        report = fb.fetch(client, tmp_path, repo.manifest, selection)

    assert report.downloaded == 2 + pdf_count
    assert len(list((tmp_path / "pdfs").glob("*.pdf"))) == pdf_count


def test_fetch_refuses_a_manifest_for_another_commit(tmp_path: Path, repo: _Repo) -> None:
    other = repo.manifest.model_copy(update={"commit": "0" * 40})

    with repo.client() as client, pytest.raises(ValueError, match="pinned"):
        fb.fetch(client, tmp_path, other, "none")


def test_build_manifest_keeps_question_files_and_pdfs() -> None:
    tree = {
        "sha": fb.COMMIT,
        "truncated": False,
        "tree": [
            {"path": "README.md", "type": "blob", "size": 10, "sha": "a" * 40},
            {"path": "data", "type": "tree", "sha": "b" * 40},
            {"path": fb.QUESTIONS_PATH, "type": "blob", "size": 5, "sha": "c" * 40},
            {"path": fb.DOCUMENTS_PATH, "type": "blob", "size": 6, "sha": "d" * 40},
            {"path": "pdfs/B.pdf", "type": "blob", "size": 7, "sha": "e" * 40},
            {"path": "pdfs/A.pdf", "type": "blob", "size": 8, "sha": "f" * 40},
            {"path": "results/scores.csv", "type": "blob", "size": 9, "sha": "0" * 40},
        ],
    }
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=tree))

    with httpx.Client(transport=transport) as client:
        manifest = fb.build_manifest(client)

    assert [entry.path for entry in manifest.files] == [
        fb.DOCUMENTS_PATH,
        fb.QUESTIONS_PATH,
        "pdfs/A.pdf",
        "pdfs/B.pdf",
    ]
    assert [entry.path for entry in manifest.pdfs] == ["pdfs/A.pdf", "pdfs/B.pdf"]


def test_build_manifest_refuses_a_truncated_listing() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"truncated": True, "tree": []})
    )

    with (
        httpx.Client(transport=transport) as client,
        pytest.raises(RuntimeError, match="truncated"),
    ):
        fb.build_manifest(client)


def test_committed_manifest_matches_the_pin() -> None:
    manifest = fb.load_manifest(ROOT / fb.MANIFEST_FILE)

    assert (manifest.repo, manifest.commit) == (fb.REPO, fb.COMMIT)
    assert fb.QUESTIONS_PATH in {entry.path for entry in manifest.files}
    assert fb.DOCUMENTS_PATH in {entry.path for entry in manifest.files}
    assert len(manifest.pdfs) == 368
