"""Start or stop the demo database on Cloud SQL (ADR-0031).

`up` starts the instance and waits until it runs. The API's data agent turns to it
within a minute; until then, and whenever it is stopped, the data agent answers from the
facts file the image carries. `down` stops it; the storage stays. A Cloud Scheduler job
stops it every night at 23:30 IST anyway, and an alert fires after four hours up.

Usage: uv run poe demo-up
       uv run poe demo-down
"""

from __future__ import annotations

import argparse
import time
from collections.abc import Sequence

from copilot.deploy.cloudsql import describe_state, set_activation, wait_for
from copilot.deploy.gcloud import run


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("action", choices=("up", "down"))
    args = parser.parse_args(argv)

    up = args.action == "up"
    started = time.monotonic()
    run(set_activation("ALWAYS" if up else "NEVER"))
    state = wait_for(
        lambda: run(describe_state(), capture=True),
        (lambda s: s == "RUNNABLE") if up else (lambda s: s != "RUNNABLE"),
    )
    print(f"the demo database is {state}, {time.monotonic() - started:.0f} s after the request")
    if up:
        print("The data agent uses it from its next question, within a minute.")
        print("Stop it with `uv run poe demo-down`; it stops at 23:30 IST in any case.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
