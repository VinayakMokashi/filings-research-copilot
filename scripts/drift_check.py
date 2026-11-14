"""Print the drift checks over the whole history (step 9.5).

Reads the nightly evaluation's nights and the canary's days from the eval-history branch, as
git has it (fetched first), or from a folder holding a copy of it, and prints
`copilot.eval.drift`'s checks for both: retrieval similarity and refusals from the nights,
latency and retrieval similarity from the canary. The nightly run and the canary already
write these into each history line; this is for a look by hand, with another window.

Usage:
  uv run poe drift-check
  uv run poe drift-check --window 5
  uv run poe drift-check --history ../eval-history-copy
"""

from __future__ import annotations

import argparse
import json
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from copilot.eval.drift import WINDOW, canary_drift, nightly_drift

BRANCH = "eval-history"


def from_git(folder: str) -> list[dict[str, Any]]:
    ref = f"origin/{BRANCH}"
    listed = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", ref, f"{folder}/runs"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    return [
        json.loads(
            subprocess.run(
                ["git", "show", f"{ref}:{name}"], capture_output=True, text=True, check=True
            ).stdout
        )
        for name in listed
        if name.endswith(".json")
    ]


def from_folder(root: Path, folder: str) -> list[dict[str, Any]]:
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((root / folder / "runs").glob("*.json"))
    ]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--history", type=Path, help="a folder holding a copy of the branch")
    parser.add_argument("--window", type=int, default=WINDOW)
    args = parser.parse_args(argv)

    if args.history is None:
        subprocess.run(["git", "fetch", "-q", "origin", BRANCH], check=True)
        nights, days = from_git("nightly"), from_git("canary")
    else:
        nights, days = from_folder(args.history, "nightly"), from_folder(args.history, "canary")
    print(f"{len(nights)} nights, {len(days)} canary days; windows of {args.window}")
    for name, report in (
        ("nightly", nightly_drift(nights, args.window)),
        ("canary", canary_drift(days, args.window)),
    ):
        print(f"{name}: periods {json.dumps(report['periods'])}")
        for check, found in report["checks"].items():
            print(f"  {check}: {json.dumps(found)}")
        if not report["checks"]:
            print(f"  not enough {name} periods yet: {2 * args.window} needed for each signal")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
