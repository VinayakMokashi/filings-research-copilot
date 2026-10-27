"""Kaggle kernels and datasets through the Kaggle CLI, for training on a free GPU (Phase 7).

The laptop this project is built on has no GPU and little free memory, so training runs as
a private Kaggle kernel: `scripts/kaggle_router.py` and `scripts/kaggle_embedder.py` build
the kernel's folder (its code, with the commit it reads pinned, and its metadata), push it
with a T4 GPU, wait for it and download what it wrote. A kernel reads committed data from
GitHub at that commit, or data that may not be committed from a private Kaggle dataset.

The CLI runs through uvx, so it is no dependency of the project; it reads the API token
from ~/.kaggle/access_token (or KAGGLE_API_TOKEN).
"""

from __future__ import annotations

import json
import subprocess
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

ACCELERATOR = "NvidiaTeslaT4"
POLL_S = 30.0
FINISHED = ("complete", "error", "cancel")
REF_MARKER = 'REF = "main"'


def cli(*args: str) -> str:
    """Run the Kaggle CLI through uvx and return what it prints."""
    done = subprocess.run(
        ["uvx", "kaggle", *args], capture_output=True, text=True, check=False, encoding="utf-8"
    )
    if done.returncode != 0:
        raise RuntimeError(f"kaggle {' '.join(args)} failed: {done.stderr.strip() or done.stdout}")
    return done.stdout


def pin(source: str, ref: str, marker: str = REF_MARKER) -> str:
    """The kernel's code with its REF line set to a commit."""
    if marker not in source:
        raise ValueError(f"The kernel has no {marker!r} line to pin.")
    return source.replace(marker, f'REF = "{ref}"')


def kernel_metadata(
    user: str, slug: str, code_file: str, datasets: Sequence[str] = ()
) -> dict[str, Any]:
    """A private GPU script kernel with internet access, reading the given datasets."""
    return {
        "id": f"{user}/{slug}",
        "title": slug,
        "code_file": code_file,
        "language": "python",
        "kernel_type": "script",
        "is_private": True,
        "enable_gpu": True,
        "enable_internet": True,
        "dataset_sources": list(datasets),
        "competition_sources": [],
        "kernel_sources": [],
    }


def write_kernel(folder: Path, code_file: str, code: str, metadata: dict[str, Any]) -> None:
    """The kernel's code and kernel-metadata.json, ready for `kaggle kernels push`."""
    (folder / code_file).write_text(code, encoding="utf-8", newline="\n")
    (folder / "kernel-metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def push(folder: Path, accelerator: str = ACCELERATOR) -> str:
    return cli("kernels", "push", "-p", str(folder), "--accelerator", accelerator)


def wait(
    status: Callable[[], str],
    poll_s: float = POLL_S,
    sleep: Callable[[float], None] = time.sleep,
    log: Callable[[str], None] = print,
) -> str:
    """Poll `status` until it reports a finished kernel; the last status."""
    current = ""
    while not any(word in current.lower() for word in FINISHED):
        sleep(poll_s)
        current = status().strip()
        log(f"  {time.strftime('%H:%M:%S')} {current}")
    return current


def kernel_status(kernel: str) -> Callable[[], str]:
    return lambda: cli("kernels", "status", kernel)


def download(kernel: str, folder: Path) -> str:
    return cli("kernels", "output", kernel, "-p", str(folder))


def dataset_metadata(user: str, slug: str, title: str, licence: str = "other") -> dict[str, Any]:
    return {"title": title, "id": f"{user}/{slug}", "licenses": [{"name": licence}]}


def publish_dataset(folder: Path, dataset: str, message: str) -> str:
    """Create the dataset, private, or add a version if it exists; what the CLI printed.

    `--keep-tabular` keeps every file as it is; the default would convert tabular files.
    """
    try:
        cli("datasets", "status", dataset)
    except RuntimeError:
        return cli("datasets", "create", "-p", str(folder), "--keep-tabular", "--quiet")
    return cli("datasets", "version", "-p", str(folder), "-m", message, "--keep-tabular", "--quiet")


def wait_for_dataset(
    dataset: str,
    poll_s: float = 15.0,
    sleep: Callable[[float], None] = time.sleep,
    status: Callable[[], str] | None = None,
) -> str:
    """Poll a dataset's status until Kaggle has processed it ("ready")."""
    check = status or (lambda: cli("datasets", "status", dataset))
    current = check().strip()
    while "ready" not in current.lower():
        if "error" in current.lower() or "fail" in current.lower():
            raise RuntimeError(f"The dataset {dataset} failed: {current}")
        sleep(poll_s)
        current = check().strip()
    return current
