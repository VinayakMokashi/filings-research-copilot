"""Ask the live API the day's canary questions (step 9.3, ADR-0036).

Run by `.github/workflows/canary.yml` once a day, with an ID token for the private API in
`CANARY_ID_TOKEN`. Writes <out>/canary.json (the day's rows and summary) and
<out>/history.json (the summary, a line for `canary/history.jsonl`). Exits with 2 when a
request failed, so the run fails and an issue opens.

Usage:
  CANARY_ID_TOKEN=... uv run poe canary --api-url https://api-....run.app --out dist/canary
  uv run poe canary --api-url http://127.0.0.1:8010 --per-day 2 --out dist/canary  # a local API

With --history (the `canary` folder of a copy of the eval-history branch), the day also
carries the drift checks of `copilot.eval.drift`: latency and retrieval similarity on the
live API, over the earlier days and itself.
"""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Sequence
from datetime import UTC, date, datetime
from pathlib import Path

import httpx

from copilot.eval.canary import PER_DAY, ask, doc_questions, failed, summary, todays
from copilot.eval.drift import canary_drift
from copilot.eval.routing import load_queries


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--api-url", required=True)
    parser.add_argument("--date", type=date.fromisoformat, help="the day, UTC (default today)")
    parser.add_argument("--per-day", type=int, default=PER_DAY)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--history", type=Path, help="the eval-history branch's canary folder")
    args = parser.parse_args(argv)

    started = datetime.now(UTC)
    day = args.date or started.date()
    questions = todays(doc_questions(load_queries("dev")), day, args.per_day)
    token = os.environ.get("CANARY_ID_TOKEN", "")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    rows = []
    with httpx.Client(base_url=args.api_url, headers=headers, timeout=30.0) as http:
        for question in questions:
            row = ask(http, question)
            rows.append(row)
            print(
                f"{row['id']}: ok={row['ok']} route={row.get('route')} arm={row.get('arm')} "
                f"group={row.get('assignment')} judged={row.get('judged')} "
                f"faithful={row.get('faithful')} {row['seconds']} s"
                + (f" error={row['error']}" if row["error"] else "")
            )
    day_summary = {
        "date": day.isoformat(),
        "started": started.isoformat(timespec="seconds"),
        "finished": datetime.now(UTC).isoformat(timespec="seconds"),
        "commit": os.environ.get("GITHUB_SHA", ""),
        "summary": summary(rows),
    }
    if args.history is not None:
        try:
            earlier = [
                json.loads(path.read_text(encoding="utf-8"))
                for path in sorted((args.history / "runs").glob("*.json"))
                if path.stem != day.isoformat()
            ]
            day_summary["drift"] = canary_drift([*earlier, day_summary | {"rows": rows}])
        except Exception as exc:  # the drift checks must never cost a day its metrics
            day_summary["drift"] = {"error": type(exc).__name__}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "canary.json").write_text(
        json.dumps(day_summary | {"rows": rows}, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    (args.out / "history.json").write_text(
        json.dumps(day_summary) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(day_summary["summary"]))
    return 2 if failed(rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
