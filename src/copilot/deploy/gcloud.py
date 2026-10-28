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


def run(args: Sequence[str], *, stdin: str | None = None, capture: bool = False) -> str:
    """Run a gcloud command line; returns its output when `capture` is set."""
    env = {**os.environ, "CLOUDSDK_ACTIVE_CONFIG_NAME": CONFIGURATION}
    result = subprocess.run(
        list(args), input=stdin, text=True, capture_output=capture, check=True, env=env
    )
    return result.stdout.strip() if capture else ""
