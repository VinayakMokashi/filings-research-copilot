"""Ask the data agent one question and print its answer, SQL, rows and statistics.

Usage: uv run poe ask-data "How did 3M's capital expenditure change from 2018 to 2022?"
       uv run poe ask-data "..." --json           (the whole answer as JSON)
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from copilot.config import get_settings
from copilot.logs import configure_logging
from copilot.sql.tool import DataAgent, DataAnswer

MAX_ROWS_SHOWN = 20


def render(answer: DataAnswer) -> str:
    lines = [f"[{answer.status}] {answer.answer}"]
    lines += [f"  - {insight}" for insight in answer.insights]
    lines += [f"  (caveat) {caveat}" for caveat in answer.caveats]
    if answer.sql:
        lines += ["", "SQL:", answer.sql]
    if answer.rows:
        lines += ["", " | ".join(answer.columns)]
        lines += [" | ".join(str(cell) for cell in row) for row in answer.rows[:MAX_ROWS_SHOWN]]
        if len(answer.rows) > MAX_ROWS_SHOWN or answer.truncated:
            lines.append(
                f"... ({len(answer.rows)} rows{', truncated' if answer.truncated else ''})"
            )
    for stat in answer.statistics:
        extremes = f", max at {stat.max_at}, min at {stat.min_at}" if stat.max_at else ""
        lines.append(
            f"{stat.column}: total {stat.total:,.2f}, mean {stat.mean:,.2f}, "
            f"min {stat.min:,.2f}, max {stat.max:,.2f}{extremes}"
        )
    if answer.chart:
        lines.append(f"Chart: {answer.chart.kind} of {answer.chart.y} by {answer.chart.x}")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("question")
    parser.add_argument("--json", action="store_true", help="print the whole answer as JSON")
    args = parser.parse_args(argv)

    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)
    answer = DataAgent.build(settings).ask(args.question)
    print(answer.model_dump_json(indent=2) if args.json else render(answer))
    return 0 if answer.status != "error" else 1


if __name__ == "__main__":
    raise SystemExit(main())
