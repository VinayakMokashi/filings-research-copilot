"""Ask the strong model for paraphrases of each routing seed, for review.

Writes eval/routing/candidates.jsonl with every rewrite and an empty verdict. Seeds that
already have candidates are skipped, so an interrupted run resumes. Then review each
candidate (a verdict of "accept" or "reject", with a reason) and run
`poe build-routing-set`.

Usage: uv run poe paraphrase-routing-seeds   (needs GROQ_API_KEY in .env)
"""

from __future__ import annotations

import json
import sys
import time

from copilot.config import get_settings
from copilot.eval import routing
from copilot.llm import LLMError, LLMGateway, LLMResponse
from copilot.logs import configure_logging

ATTEMPTS = 3
RATE_LIMIT_PAUSE_S = 20.0
PAUSE_BETWEEN_SEEDS_S = 1.0


def main() -> int:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)
    if settings.groq_api_key is None:
        print("GROQ_API_KEY is not set. Add it to .env and try again.", file=sys.stderr)
        return 1

    gateway = LLMGateway(settings)
    path = routing.CANDIDATES_FILE
    done = {c.seed for c in routing.load_candidates(path)} if path.exists() else set()
    with path.open("a", encoding="utf-8", newline="\n") as out:
        for seed in routing.load_seeds():
            if seed.seed in done:
                continue
            response = _paraphrase(gateway, seed)
            rewrites = routing.parse_paraphrases(response.text)
            for text in rewrites:
                candidate = routing.Candidate(seed=seed.seed, query=text, model=response.model)
                out.write(json.dumps(candidate.model_dump(mode="json"), ensure_ascii=False) + "\n")
            out.flush()
            print(f"{seed.seed} {seed.route:9} {len(rewrites)} rewrites")
            time.sleep(PAUSE_BETWEEN_SEEDS_S)
    return 0


def _paraphrase(gateway: LLMGateway, seed: routing.Seed) -> LLMResponse:
    for attempt in range(1, ATTEMPTS + 1):
        try:
            return gateway.complete(
                routing.paraphrase_messages(seed), role="strong", temperature=0.9, max_tokens=2048
            )
        except LLMError as exc:
            if not exc.rate_limited or attempt == ATTEMPTS:
                raise
            time.sleep(RATE_LIMIT_PAUSE_S)
    raise AssertionError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
