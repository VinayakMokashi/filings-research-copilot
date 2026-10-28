"""The data bundle the API image carries on Cloud Run: what it holds, and that the same
data always gives the same archive."""

from __future__ import annotations

import json
import tarfile
from pathlib import Path

import pytest

from copilot.config import Settings
from copilot.deploy.bundle import build

DOCUMENT: dict[str, object] = {
    "company": "Alpha",
    "gics_sector": "Industrials",
    "doc_type": "10k",
    "doc_link": "x",
}


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    data = tmp_path / "data"
    processed = data / "processed"
    (processed / "pages").mkdir(parents=True)
    (processed / "indexes").mkdir()
    (processed / "facts.db").write_bytes(b"facts")
    (processed / "indexes" / "fb_page_bge-small.json").write_text("{}", encoding="utf-8")
    rows = [DOCUMENT | {"doc_name": f"ALPHA_{y}_10K", "doc_period": y} for y in (2019, 2018)]
    (processed / "corpus.jsonl").write_text("\n".join(map(json.dumps, rows)), encoding="utf-8")
    for row in rows:
        (processed / "pages" / f"{row['doc_name']}.jsonl").write_text("{}", encoding="utf-8")
    (processed / "pages" / "NOT_IN_THE_CORPUS.jsonl").write_text("{}", encoding="utf-8")
    for model in ("models--Qdrant--bge-small-en-v1.5-onnx-Q", "models--Qdrant--bm25"):
        snapshot = data / "models" / model / "snapshots" / "abc"
        snapshot.mkdir(parents=True)
        (snapshot / "config.json").write_text("{}", encoding="utf-8")
        (data / "models" / model / "refs").mkdir()
        (data / "models" / model / "refs" / "main").write_text("abc", encoding="utf-8")
        (data / "models" / model / "download.lock").write_text("", encoding="utf-8")
    (data / "models" / "router-v2").mkdir()
    (data / "models" / "router-v2" / "router.onnx").write_bytes(b"not wanted")
    return data


def test_the_bundle_holds_what_the_services_read_at_start(data_dir: Path, tmp_path: Path) -> None:
    out = tmp_path / "bundle.tar.gz"
    digest, size, count = build(out, Settings(data_dir=data_dir))

    with tarfile.open(out) as tar:
        names = tar.getnames()
        members = tar.getmembers()
    assert names == sorted(names)
    assert set(names) == {
        "processed/facts.db",
        "processed/corpus.jsonl",
        "processed/indexes/fb_page_bge-small.json",
        "processed/pages/ALPHA_2018_10K.jsonl",
        "processed/pages/ALPHA_2019_10K.jsonl",
        "models/models--Qdrant--bge-small-en-v1.5-onnx-Q/refs/main",
        "models/models--Qdrant--bge-small-en-v1.5-onnx-Q/snapshots/abc/config.json",
        "models/models--Qdrant--bm25/refs/main",
        "models/models--Qdrant--bm25/snapshots/abc/config.json",
    }
    assert count == len(names)
    assert {(m.mtime, m.uid, m.gid) for m in members} == {(0, 0, 0)}
    assert size == out.stat().st_size
    assert len(digest) == 64


def test_the_same_data_gives_the_same_archive(data_dir: Path, tmp_path: Path) -> None:
    settings = Settings(data_dir=data_dir)
    first = build(tmp_path / "one" / "bundle.tar.gz", settings)
    second = build(tmp_path / "two" / "bundle.tar.gz", settings)

    assert first == second


def test_a_missing_file_stops_the_build(data_dir: Path, tmp_path: Path) -> None:
    (data_dir / "processed" / "facts.db").unlink()

    with pytest.raises(FileNotFoundError, match=r"facts\.db"):
        build(tmp_path / "bundle.tar.gz", Settings(data_dir=data_dir))
