"""gcloud, always with the copilot's own configuration (`frc`), never the active one.

The machine that runs these scripts has other gcloud configurations for other work;
setting CLOUDSDK_ACTIVE_CONFIG_NAME for each command leaves them untouched. A secret
goes to gcloud on its standard input, so it appears in no command line or log.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Sequence

CONFIGURATION = "frc"
PROJECT = "filings-research-copilot"


def command(*args: str) -> list[str]:
    """A gcloud command line for the copilot's project."""
    # On Windows gcloud is a .cmd script, which subprocess finds only by its full path.
    return [shutil.which("gcloud") or "gcloud", *args, f"--project={PROJECT}"]


def shown(args: Sequence[str]) -> list[str]:
    """A command line as an error may show it: a password's value hidden."""
    return [
        arg.split("=", 1)[0] + "=<hidden>" if arg.startswith("--password=") else arg for arg in args
    ]


def run(args: Sequence[str], *, stdin: str | None = None, capture: bool = False) -> str:
    """Run a gcloud command line; returns its output when `capture` is set.

    gcloud takes a database user's password only as an argument, so a failure is raised
    again with the password hidden, and without the original, which holds it.
    """
    env = {**os.environ, "CLOUDSDK_ACTIVE_CONFIG_NAME": CONFIGURATION}
    try:
        result = subprocess.run(
            list(args), input=stdin, text=True, capture_output=capture, check=True, env=env
        )
    except subprocess.CalledProcessError as exc:
        raise subprocess.CalledProcessError(
            exc.returncode, shown(args), exc.output, exc.stderr
        ) from None
    return result.stdout.strip() if capture else ""
