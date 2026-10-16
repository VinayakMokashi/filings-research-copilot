"""The company-grouped FinanceBench split and the held-out guard."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

from copilot.eval import financebench as fb
from copilot.eval import splits

ROOT = Path(__file__).resolve().parents[1]
RecordFactory = Callable[..., dict[str, Any]]
TYPES = ("metrics-generated", "domain-relevant", "novel-generated")


def _items() -> list[splits.Item]:
    """12 companies in 4 sectors, each with one question of each type: a perfect split exists."""
    return [
        splits.Item(
            id=f"q{company}-{kind}",
            company=f"Company {company:02d}",
            question_type=kind,
            doc_type="10k",
            sector=f"Sector {company % 4}",
        )
        for company in range(12)
        for kind in TYPES
    ]


def test_split_keeps_each_company_on_one_side() -> None:
    items = _items()
    split = splits.split_by_company(items, test_size=12, seeds=range(300))

    company = {item.id: item.company for item in items}
    dev_companies = {company[i] for i in split.dev}
    test_companies = {company[i] for i in split.test}
    assert not dev_companies & test_companies
    assert test_companies == split.test_companies
    assert sorted(split.dev + split.test) == sorted(company)


def test_split_finds_the_perfectly_balanced_option() -> None:
    items = _items()
    split = splits.split_by_company(items, test_size=12, seeds=range(300))

    test = [item for item in items if item.id in set(split.test)]
    assert split.score == 0
    assert Counter(item.question_type for item in test) == dict.fromkeys(TYPES, 4)
    assert Counter(item.sector for item in test) == {f"Sector {s}": 3 for s in range(4)}


def test_split_is_deterministic_and_independent_of_input_order() -> None:
    items = _items()
    first = splits.split_by_company(items, test_size=12, seeds=range(300))
    again = splits.split_by_company(list(reversed(items)), test_size=12, seeds=range(300))

    assert (first.seed, first.score, first.test_companies) == (
        again.seed,
        again.score,
        again.test_companies,
    )


def test_a_sector_entirely_on_one_side_costs_more() -> None:
    items = _items()
    whole_sector = frozenset({"Company 00", "Company 04", "Company 08", "Company 01"})
    one_per_sector = frozenset({"Company 00", "Company 01", "Company 02", "Company 03"})

    assert splits.imbalance(items, one_per_sector, 12) == 0
    assert splits.imbalance(items, whole_sector, 12) > 0


def test_records_sha256_ignores_record_and_key_order() -> None:
    a = {"financebench_id": "1", "answer": "x"}
    b = {"financebench_id": "2", "answer": "y"}

    assert splits.records_sha256([a, b]) == splits.records_sha256([dict(reversed(b.items())), a])
    assert splits.records_sha256([a, b]) != splits.records_sha256([a, b | {"answer": "z"}])


@pytest.fixture
def fetched(tmp_path: Path, question_record: RecordFactory) -> tuple[Path, Path]:
    """A fetched copy with four questions and a split file putting two on each side."""
    records = [
        question_record(1, company="Acme", doc_name="ACME_2022_10K"),
        question_record(
            2, company="Acme", doc_name="ACME_2022_10K", question_type="domain-relevant"
        ),
        question_record(3, company="Bolt", doc_name="BOLT_2022_10K"),
        question_record(
            4, company="Bolt", doc_name="BOLT_2022_10K", question_type="novel-generated"
        ),
    ]
    data = "".join(json.dumps(r) + "\n" for r in records).encode("utf-8")
    questions_file = tmp_path / "raw" / fb.QUESTIONS_PATH
    questions_file.parent.mkdir(parents=True)
    questions_file.write_bytes(data)

    documents = {
        name: fb.Document(
            doc_name=name,
            company=name.split("_")[0].title(),
            gics_sector="Industrials",
            doc_type="10k",
            doc_period=2022,
            doc_link="https://example.com",
        )
        for name in ("ACME_2022_10K", "BOLT_2022_10K")
    }
    manifest = fb.Manifest(
        repo=fb.REPO,
        commit=fb.COMMIT,
        files=(
            fb.ManifestFile(
                path=fb.QUESTIONS_PATH, size=len(data), git_sha1=fb.git_blob_sha1(data)
            ),
        ),
    )
    split = splits.Split(
        seed=0,
        score=Fraction(0),
        dev=("financebench_id_00001", "financebench_id_00002"),
        test=("financebench_id_00003", "financebench_id_00004"),
        test_companies=frozenset({"Bolt"}),
    )
    questions = [fb.Question.model_validate(r) for r in records]
    spec = splits.build_split_file(split, questions, documents, records, manifest, seeds_searched=1)
    split_file = tmp_path / "splits.json"
    splits.save_split_file(spec, split_file)
    return tmp_path / "raw", split_file


def test_the_test_side_is_held_out(fetched: tuple[Path, Path]) -> None:
    root, split_file = fetched

    with pytest.raises(splits.HeldOutError, match="milestone"):
        splits.load_split("test", root, split_file=split_file)

    dev = splits.load_split("dev", root, split_file=split_file)
    test = splits.load_split("test", root, allow_test=True, split_file=split_file)
    assert [q.id for q in dev] == ["financebench_id_00001", "financebench_id_00002"]
    assert {q.company for q in test} == {"Bolt"}


def test_a_changed_question_fails_the_checksum(fetched: tuple[Path, Path]) -> None:
    root, split_file = fetched
    questions_file = root / fb.QUESTIONS_PATH
    questions_file.write_text(
        questions_file.read_text(encoding="utf-8").replace("$1577.00", "$1578.00", 1),
        encoding="utf-8",
    )

    with pytest.raises(fb.ChecksumError, match="dev"):
        splits.load_split("dev", root, split_file=split_file)


def test_the_split_file_is_never_silently_replaced(fetched: tuple[Path, Path]) -> None:
    _, split_file = fetched
    spec = splits.read_split_file(split_file)

    with pytest.raises(FileExistsError, match="fixed before any tuning"):
        splits.save_split_file(spec, split_file)


def test_committed_split_is_consistent() -> None:
    spec = splits.read_split_file(ROOT / splits.SPLIT_FILE)

    assert (len(spec.dev), len(spec.test)) == (100, 50)
    assert len(set(spec.dev) | set(spec.test)) == 150
    assert not set(spec.dev_companies) & set(spec.test_companies)
    assert (spec.source.repo, spec.source.commit) == (fb.REPO, fb.COMMIT)
    assert (
        spec.source.git_sha1
        == fb.load_manifest(ROOT / fb.MANIFEST_FILE).file(fb.QUESTIONS_PATH).git_sha1
    )
    sides: tuple[tuple[splits.SplitName, tuple[str, ...]], ...] = (
        ("dev", spec.dev),
        ("test", spec.test),
    )
    for name, ids in sides:
        counts = spec.counts[name]
        assert counts.questions == len(ids)
        assert sum(counts.question_types.values()) == len(ids)
        assert sum(counts.doc_types.values()) == len(ids)
        assert sum(counts.sectors.values()) == len(ids)
    assert 0 <= spec.method.seed < spec.method.seeds_searched
