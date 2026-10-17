"""Check that parsed pages line up with FinanceBench's evidence pages (dev questions only).

For every evidence passage, compare FinanceBench's full-page text with our page of the same
index and with its neighbours. A page lines up when it is the most similar of the three and
shares at least half its words. Writes eval/results/parsing/page-alignment-dev.md and .json.

Usage: uv run poe check-pages   (after `poe parse-pdfs`)
"""

from __future__ import annotations

import json
import re
import statistics
from dataclasses import asdict, dataclass
from pathlib import Path

from copilot.config import get_settings
from copilot.eval.splits import load_split
from copilot.ingest.corpus import pages_path
from copilot.ingest.pdf import normalise_text, read_pages

OUT_DIR = Path("eval/results/parsing")
MIN_SIMILARITY = 0.5


@dataclass(frozen=True, slots=True)
class Alignment:
    id: str
    doc_name: str
    page: int
    similarity: float
    best_offset: int
    aligned: bool


def words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", normalise_text(text).lower()))


def similarity(a: set[str], b: set[str]) -> float:
    """Jaccard similarity of two word sets."""
    return len(a & b) / len(a | b) if a or b else 1.0


def main() -> int:
    settings = get_settings()
    dev = load_split("dev", settings.data_dir / "raw" / "financebench")
    pages_dir = settings.data_dir / "processed" / "pages"
    cache: dict[str, list[set[str]]] = {}
    rows: list[Alignment] = []
    for question in dev:
        for evidence in question.evidence:
            if evidence.doc_name not in cache:
                cache[evidence.doc_name] = [
                    words(p.text) for p in read_pages(pages_path(pages_dir, evidence.doc_name))
                ]
            ours = cache[evidence.doc_name]
            gold = words(evidence.page_text)
            scores = {
                offset: similarity(gold, ours[evidence.page + offset])
                for offset in (-1, 0, 1)
                if 0 <= evidence.page + offset < len(ours)
            }
            best = max(scores, key=lambda offset: scores[offset])
            rows.append(
                Alignment(
                    id=question.id,
                    doc_name=evidence.doc_name,
                    page=evidence.page,
                    similarity=round(scores[0], 3),
                    best_offset=best,
                    aligned=best == 0 and scores[0] >= MIN_SIMILARITY,
                )
            )

    aligned = sum(row.aligned for row in rows)
    median = statistics.median(row.similarity for row in rows)
    misaligned = [row for row in rows if not row.aligned]
    lines = [
        "# Page alignment with FinanceBench evidence (dev)",
        "",
        f"{aligned} of {len(rows)} evidence passages line up with the parsed page of the same "
        "index (the most similar of it and its neighbours, sharing at least "
        f"{MIN_SIMILARITY:.0%} of words). Median word overlap: {median:.2f}.",
    ]
    if misaligned:
        lines += [
            "",
            "| Question | Document | Page | Overlap | Best neighbour |",
            "|---|---|---|---|---|",
        ]
        lines += [
            f"| {r.id} | {r.doc_name} | {r.page} | {r.similarity:.2f} | {r.best_offset:+d} |"
            for r in misaligned
        ]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "page-alignment-dev.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
    )
    (OUT_DIR / "page-alignment-dev.json").write_text(
        json.dumps([asdict(row) for row in rows], indent=1) + "\n", encoding="utf-8", newline="\n"
    )
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
