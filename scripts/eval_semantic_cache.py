"""Would a similarity cache serve the right answers? Measured on routing-set pairs (step 6.2).

A semantic cache serves a stored answer when a new question is close enough to an old one
in embedding space. Two questions that ask the same thing should hit; two that ask
different things must not. This script measures both on the routing set's doc, data and
hybrid questions, embedded with bge-small as the semantic router embeds them:

- **should hit:** each pair of questions from one seed group (a seed and its two reviewed
  paraphrases), which ask the same thing in different words;
- **must miss:** each question with its measure swapped for another (revenue for net
  income, say), which shares every other word, its company and its years;
- **must miss:** pairs from different seed groups that name the same companies and years.

A hit needs the same companies, years, quarters and dates, and a cosine similarity at or
above the threshold; a second gate also needs the same measures. Results for each
threshold go to eval/results/cache/similarity/<split>/. No model is called.

Usage: uv run poe eval-semantic-cache
       uv run poe eval-semantic-cache --split test --allow-test
"""

from __future__ import annotations

import argparse
import itertools
import json
import re
from collections import defaultdict
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from copilot.config import get_settings
from copilot.eval.report import RESULTS_DIR
from copilot.eval.routing import load_queries
from copilot.ingest.embed import FastEmbedDense, normalise
from copilot.ingest.universe import read_companies
from copilot.retrieval.query import CompanyMatcher, understand

THRESHOLDS = (0.85, 0.88, 0.90, 0.92, 0.93, 0.94, 0.95, 0.96, 0.97, 0.98)
SWAPS = ("revenue", "net income", "operating income", "capital expenditure", "total assets")
MEASURES = {
    "revenue": "revenue",
    "net sales": "revenue",
    "sales": "revenue",
    "net income": "net_income",
    "earnings": "net_income",
    "operating income": "operating_income",
    "gross margin": "gross_margin",
    "operating margin": "operating_margin",
    "net margin": "net_margin",
    "gross profit": "gross_profit",
    "capital expenditure": "capex",
    "capex": "capex",
    "free cash flow": "free_cash_flow",
    "cash flow from operations": "operating_cash_flow",
    "operating cash flow": "operating_cash_flow",
    "total assets": "total_assets",
    "long-term debt": "debt",
    "total debt": "debt",
    "debt": "debt",
    "dividends": "dividends",
    "dividend": "dividends",
    "research and development": "rnd",
    "r&d": "rnd",
    "inventory": "inventory",
    "earnings per share": "eps",
    "eps": "eps",
}
_TERMS = sorted(MEASURES, key=len, reverse=True)
_MEASURE = re.compile(r"(?<![\w&])(" + "|".join(map(re.escape, _TERMS)) + r")(?![\w&])", re.I)


def measures(text: str) -> tuple[str, ...]:
    return tuple(sorted({MEASURES[match.group(1).lower()] for match in _MEASURE.finditer(text)}))


def swapped(text: str) -> list[str]:
    """The question with its first measure replaced by two others from SWAPS."""
    match = _MEASURE.search(text)
    if match is None:
        return []
    others = [s for s in SWAPS if MEASURES[s] != MEASURES[match.group(1).lower()]][:2]
    return [text[: match.start()] + other + text[match.end() :] for other in others]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--split", choices=("dev", "test"), default="dev")
    parser.add_argument("--allow-test", action="store_true", help="read the test split")
    parser.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    args = parser.parse_args(argv)

    queries = [
        q
        for q in load_queries(args.split, allow_test=args.allow_test)
        if q.route in ("doc", "data", "hybrid")
    ]
    companies = read_companies()
    matcher = CompanyMatcher([c.name for c in companies], {c.name: c.ticker for c in companies})
    texts = [q.query for q in queries]
    swaps = [(i, variant) for i, text in enumerate(texts) for variant in swapped(text)]
    every = texts + [variant for _, variant in swaps]
    embedder = FastEmbedDense(cache_dir=get_settings().data_dir / "models")
    vectors = normalise(embedder.embed_documents(every))

    def cue(text: str) -> tuple[Any, ...]:
        found = understand(text, matcher)
        return (found.companies, found.years, found.quarters, found.dates)

    cues = [tuple(sorted(part) for part in cue(text)) for text in every]
    named = [measures(text) for text in every]
    groups: dict[str, list[int]] = defaultdict(list)
    for i, query in enumerate(queries):
        groups[query.seed].append(i)
    pairs = {
        "paraphrases": [p for g in groups.values() for p in itertools.combinations(g, 2)],
        "measure_swaps": [(i, len(texts) + k) for k, (i, _) in enumerate(swaps)],
        "same_cue_other_question": [
            (a, b)
            for a, b in itertools.combinations(range(len(texts)), 2)
            if queries[a].seed != queries[b].seed and cues[a] == cues[b] and cues[a][0]
        ],
    }

    def hits(kind: str, threshold: float, with_measures: bool) -> int:
        return sum(
            1
            for a, b in pairs[kind]
            if cues[a] == cues[b]
            and (not with_measures or named[a] == named[b])
            and float(np.dot(vectors[a], vectors[b])) >= threshold
        )

    rows = [
        {
            "threshold": t,
            **{f"{kind}_hit": hits(kind, t, False) for kind in pairs},
            **{f"{kind}_hit_with_measures": hits(kind, t, True) for kind in pairs},
        }
        for t in THRESHOLDS
    ]
    result = {
        "created": datetime.now(UTC).isoformat(timespec="seconds"),
        "split": args.split,
        "questions": len(queries),
        "pairs": {kind: len(found) for kind, found in pairs.items()},
        "embedder": "BAAI/bge-small-en-v1.5, no instruction",
        "rows": rows,
    }
    out = args.results_dir / "cache" / "similarity" / args.split
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    lines = [
        f"# Similarity cache on routing {args.split} pairs",
        "",
        f"{len(queries)} doc, data and hybrid questions: {len(pairs['paraphrases'])} paraphrase "
        f"pairs (should hit), {len(pairs['measure_swaps'])} measure swaps (must miss), "
        f"{len(pairs['same_cue_other_question'])} other questions with the same cues (must miss).",
        "",
        "| Threshold | Paraphrases hit | Measure swaps hit | Same-cue others hit | "
        "Swaps hit, measures also gated |",
        "|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['threshold']:.2f} | {row['paraphrases_hit']} | {row['measure_swaps_hit']} | "
            f"{row['same_cue_other_question_hit']} | {row['measure_swaps_hit_with_measures']} |"
        )
    (out / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
