"""Reference labels for checking the judge: which answers to label, and reading them back.

A labeller, a person or a stronger model, labels a sample of the agent's answers as
correct, incorrect or unsure, seeing what the judge sees. Each label line records who
labelled it. The sample is stratified by question type, so each type is represented in
proportion, and drawn with a fixed seed, so it can be drawn again.
"""

from __future__ import annotations

import json
import random
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Literal, get_args

Label = Literal["correct", "incorrect", "unsure"]
LABELS: tuple[str, ...] = get_args(Label)


def allocate(counts: Mapping[str, int], size: int) -> dict[str, int]:
    """Split `size` across groups in proportion to `counts`, largest remainders first."""
    total = sum(counts.values())
    if not 0 <= size <= total:
        raise ValueError(f"Asked for {size} items but only {total} are available.")
    exact = {group: size * count / total for group, count in counts.items()}
    shares = {group: int(value) for group, value in exact.items()}
    by_remainder = sorted(counts, key=lambda group: (shares[group] - exact[group], group))
    for group in by_remainder[: size - sum(shares.values())]:
        shares[group] += 1
    return shares


def stratified_sample(groups: Mapping[str, Sequence[str]], size: int, seed: int) -> set[str]:
    """`size` ids drawn from the groups in proportion to their sizes."""
    rng = random.Random(seed)
    shares = allocate({group: len(ids) for group, ids in groups.items()}, size)
    return {item for group in sorted(groups) for item in rng.sample(groups[group], shares[group])}


def labellers(path: Path, run: str) -> list[str]:
    """Who labelled one answers run: people or models, as the label lines record them."""
    names = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            item = json.loads(line)
            if item["answers_run"] == run:
                names.add(item.get("labeller", "unknown"))
    return sorted(names)


def read_labels(path: Path, run: str) -> dict[str, str]:
    """The decided labels (correct or incorrect) for one answers run, by question id."""
    labels: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if item["label"] not in LABELS:
            raise ValueError(f"Unknown label {item['label']!r} for {item['id']}.")
        if item["answers_run"] == run and item["label"] != "unsure":
            labels[item["id"]] = item["label"]
    return labels
