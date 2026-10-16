"""Dev and held-out test splits for FinanceBench (ADR-0006).

Questions are split by company: every question about a company lands on the same side, so
no test company's filings are seen while tuning (Phases 2 to 5) or training (Phase 7).
Within that constraint the split balances question types as closely as it can, and
document types and sectors roughly. It tries a fixed range of seeds and keeps the most
balanced result. Scores use exact fractions, so the same data always gives the same split.

The test split is held out. Loading it needs `allow_test=True`, which is reserved for
milestone evaluations, and both splits are checked against their recorded checksums
every time they are loaded.
"""

from __future__ import annotations

import hashlib
import json
import random
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from copilot.eval.financebench import (
    QUESTIONS_PATH,
    ChecksumError,
    Document,
    Manifest,
    Question,
    read_jsonl,
)
from copilot.logs import get_logger

SPLIT_FILE = Path("eval/financebench/splits.json")
TEST_SIZE = 50
SEEDS = range(20_000)

# The test-set size and the question-type mix dominate; document type and sector break
# ties; a sector with more than one company should appear on both sides.
_SIZE_WEIGHT = Fraction(3)
_SECONDARY_WEIGHT = Fraction(1, 4)
_ONE_SIDED_SECTOR_PENALTY = Fraction(5)

SplitName = Literal["dev", "test"]

log = get_logger(__name__)


class HeldOutError(PermissionError):
    """The test split was requested without `allow_test=True`."""


@dataclass(frozen=True, slots=True)
class Item:
    """What the split needs to know about one question."""

    id: str
    company: str
    question_type: str
    doc_type: str
    sector: str


@dataclass(frozen=True, slots=True)
class Split:
    seed: int
    score: Fraction
    dev: tuple[str, ...]
    test: tuple[str, ...]
    test_companies: frozenset[str]


def items_from(questions: Sequence[Question], documents: Mapping[str, Document]) -> list[Item]:
    return [
        Item(
            id=question.id,
            company=question.company,
            question_type=question.question_type,
            doc_type=documents[question.doc_name].doc_type,
            sector=documents[question.doc_name].gics_sector,
        )
        for question in questions
    ]


def imbalance(items: Sequence[Item], test_companies: frozenset[str], test_size: int) -> Fraction:
    """How far a candidate split is from the ideal; lower is better."""
    test = [item for item in items if item.company in test_companies]
    score = _SIZE_WEIGHT * abs(len(test) - test_size)
    score += _deviation(items, test, lambda item: item.question_type)
    score += _SECONDARY_WEIGHT * _deviation(items, test, lambda item: item.doc_type)
    score += _SECONDARY_WEIGHT * _deviation(items, test, lambda item: item.sector)
    companies_by_sector: dict[str, set[str]] = {}
    for item in items:
        companies_by_sector.setdefault(item.sector, set()).add(item.company)
    for companies in companies_by_sector.values():
        one_sided = companies <= test_companies or not companies & test_companies
        if len(companies) > 1 and one_sided:
            score += _ONE_SIDED_SECTOR_PENALTY
    return score


def _deviation(items: Sequence[Item], test: Sequence[Item], key: Callable[[Item], str]) -> Fraction:
    """Sum over categories of |test count - the count a proportional split would give|."""
    share = Fraction(len(test), len(items))
    in_test = Counter(map(key, test))
    return sum(
        (
            abs(in_test[category] - count * share)
            for category, count in Counter(map(key, items)).items()
        ),
        Fraction(0),
    )


def split_by_company(
    items: Sequence[Item], test_size: int = TEST_SIZE, seeds: Iterable[int] = SEEDS
) -> Split:
    """Try each seed and keep the most balanced company-grouped split.

    For each seed, the companies are shuffled and added to the test side until it holds at
    least `test_size` questions. Ties go to the earlier seed.
    """
    companies = sorted({item.company for item in items})
    questions_per_company = Counter(item.company for item in items)
    best: tuple[Fraction, int, frozenset[str]] | None = None
    for seed in seeds:
        order = companies.copy()
        random.Random(seed).shuffle(order)
        chosen: list[str] = []
        total = 0
        for company in order:
            if total >= test_size:
                break
            chosen.append(company)
            total += questions_per_company[company]
        candidate = frozenset(chosen)
        score = imbalance(items, candidate, test_size)
        if best is None or score < best[0]:
            best = (score, seed, candidate)
    if best is None:
        raise ValueError("No seeds to search.")
    score, seed, test_companies = best
    return Split(
        seed=seed,
        score=score,
        dev=tuple(item.id for item in items if item.company not in test_companies),
        test=tuple(item.id for item in items if item.company in test_companies),
        test_companies=test_companies,
    )


def records_sha256(records: Iterable[Mapping[str, Any]]) -> str:
    """SHA-256 of source records in canonical form, independent of order.

    Each record becomes compact JSON with sorted keys; the lines are sorted and hashed
    with a newline after each.
    """
    lines = sorted(
        json.dumps(record, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        for record in records
    )
    digest = hashlib.sha256()
    for line in lines:
        digest.update(line.encode("utf-8") + b"\n")
    return digest.hexdigest()


class SplitSource(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    repo: str
    commit: str
    path: str
    git_sha1: str


class SplitMethod(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    group_by: str
    stratify_by: str
    also_balanced: tuple[str, ...]
    test_size: int
    seeds_searched: int
    seed: int
    score: float


class SideCounts(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    questions: int
    companies: int
    documents: int
    question_types: dict[str, int]
    doc_types: dict[str, int]
    sectors: dict[str, int]


class SplitFile(BaseModel):
    """The committed record of the split: the question ids on each side and their checksums."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    dataset: str
    source: SplitSource
    method: SplitMethod
    counts: dict[SplitName, SideCounts]
    dev_companies: tuple[str, ...]
    test_companies: tuple[str, ...]
    dev_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    test_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    dev: tuple[str, ...]
    test: tuple[str, ...]


def build_split_file(
    split: Split,
    questions: Sequence[Question],
    documents: Mapping[str, Document],
    records: Sequence[Mapping[str, Any]],
    manifest: Manifest,
    seeds_searched: int = len(SEEDS),
) -> SplitFile:
    by_id = {question.id: question for question in questions}
    record_by_id = {record["financebench_id"]: record for record in records}

    def counts(ids: Sequence[str]) -> SideCounts:
        side = [by_id[i] for i in ids]
        docs = [documents[question.doc_name] for question in side]
        return SideCounts(
            questions=len(side),
            companies=len({question.company for question in side}),
            documents=len({question.doc_name for question in side}),
            question_types=dict(sorted(Counter(q.question_type for q in side).items())),
            doc_types=dict(sorted(Counter(d.doc_type for d in docs).items())),
            sectors=dict(sorted(Counter(d.gics_sector for d in docs).items())),
        )

    return SplitFile(
        dataset="FinanceBench open-source sample",
        source=SplitSource(
            repo=manifest.repo,
            commit=manifest.commit,
            path=QUESTIONS_PATH,
            git_sha1=manifest.file(QUESTIONS_PATH).git_sha1,
        ),
        method=SplitMethod(
            group_by="company",
            stratify_by="question_type",
            also_balanced=("doc_type", "gics_sector"),
            test_size=TEST_SIZE,
            seeds_searched=seeds_searched,
            seed=split.seed,
            score=float(split.score),
        ),
        counts={"dev": counts(split.dev), "test": counts(split.test)},
        dev_companies=tuple(sorted({by_id[i].company for i in split.dev})),
        test_companies=tuple(sorted(split.test_companies)),
        dev_sha256=records_sha256(record_by_id[i] for i in split.dev),
        test_sha256=records_sha256(record_by_id[i] for i in split.test),
        dev=split.dev,
        test=split.test,
    )


def save_split_file(
    split_file: SplitFile, path: Path = SPLIT_FILE, *, overwrite: bool = False
) -> None:
    """Write the split once. Replacing it would invalidate the held-out test set."""
    if path.exists() and not overwrite:
        raise FileExistsError(
            f"{path} already exists. The split is fixed before any tuning; pass overwrite=True "
            "only if you really mean to replace it."
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(split_file.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n")


def read_split_file(path: Path = SPLIT_FILE) -> SplitFile:
    return SplitFile.model_validate_json(path.read_text(encoding="utf-8"))


def load_split(
    name: SplitName, root: Path, *, allow_test: bool = False, split_file: Path = SPLIT_FILE
) -> list[Question]:
    """The questions on one side of the split, checked against the recorded checksum.

    `root` is a fetched copy of FinanceBench. The test side needs `allow_test=True`.
    """
    if name == "test" and not allow_test:
        raise HeldOutError(
            "The test split is held out for milestone evaluations (ADR-0006). "
            "Pass allow_test=True only for one of those."
        )
    spec = read_split_file(split_file)
    ids, expected = (spec.dev, spec.dev_sha256) if name == "dev" else (spec.test, spec.test_sha256)
    records = {record["financebench_id"]: record for record in read_jsonl(root / QUESTIONS_PATH)}
    missing = [i for i in ids if i not in records]
    if missing:
        raise ChecksumError(f"{len(missing)} {name} questions are missing, e.g. {missing[0]}.")
    chosen = [records[i] for i in ids]
    if records_sha256(chosen) != expected:
        raise ChecksumError(f"The {name} questions differ from the ones the split recorded.")
    if name == "test":
        log.warning("eval.test_split_opened", questions=len(chosen))
    return [Question.model_validate(record) for record in chosen]
