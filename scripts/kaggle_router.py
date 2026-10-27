"""Train the classifier router on a Kaggle GPU and download the model (step 7.2).

Builds the kernel in a temporary folder: kaggle/router/train_router.py with REF pinned to a
commit of this repository (the kernel reads the training set from GitHub at that commit),
and a kernel-metadata.json for the given Kaggle user. Pushes it with a T4 GPU, waits for
it to finish, and downloads its output to data/models/<name>/, with router.onnx,
metrics.json and the merged model's config.json and tokenizer.json (the files
`ClassifierRouter.load` reads) at the top of the folder. The Kaggle CLI runs through uvx,
so it is no dependency of the project; it reads the API token from ~/.kaggle/access_token
(or KAGGLE_API_TOKEN).

Usage: uv run poe kaggle-router --user KAGGLE_USERNAME --ref COMMIT --name router-v1
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

KERNEL_SOURCE = Path("kaggle/router/train_router.py")
SLUG = "frc-router"
POLL_S = 30.0
FINISHED = ("complete", "error", "cancel")
KEEP = ("router.onnx", "metrics.json", "model/config.json", "model/tokenizer.json")


def kaggle(*args: str) -> str:
    """Run the Kaggle CLI through uvx and return what it prints."""
    done = subprocess.run(
        ["uvx", "kaggle", *args], capture_output=True, text=True, check=False, encoding="utf-8"
    )
    if done.returncode != 0:
        raise RuntimeError(f"kaggle {' '.join(args)} failed: {done.stderr.strip() or done.stdout}")
    return done.stdout


def build(folder: Path, user: str, ref: str) -> None:
    """The kernel's code with REF pinned, and its metadata."""
    source = KERNEL_SOURCE.read_text(encoding="utf-8")
    marker = 'REF = "main"'
    if marker not in source:
        raise ValueError(f"{KERNEL_SOURCE} has no {marker!r} line to pin.")
    (folder / KERNEL_SOURCE.name).write_text(
        source.replace(marker, f'REF = "{ref}"'), encoding="utf-8", newline="\n"
    )
    metadata = {
        "id": f"{user}/{SLUG}",
        "title": SLUG,
        "code_file": KERNEL_SOURCE.name,
        "language": "python",
        "kernel_type": "script",
        "is_private": True,
        "enable_gpu": True,
        "enable_internet": True,
        "dataset_sources": [],
        "competition_sources": [],
        "kernel_sources": [],
    }
    (folder / "kernel-metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--user", required=True, help="your Kaggle username")
    parser.add_argument("--ref", required=True, help="the commit whose training set to use")
    parser.add_argument("--name", default="router-v1", help="folder under data/models")
    parser.add_argument("--out", type=Path, default=Path("data/models"))
    args = parser.parse_args(argv)
    kernel = f"{args.user}/{SLUG}"

    with tempfile.TemporaryDirectory() as temporary:
        folder = Path(temporary)
        build(folder, args.user, args.ref)
        print(kaggle("kernels", "push", "-p", str(folder), "--accelerator", "NvidiaTeslaT4"))

    status = ""
    while not any(word in status.lower() for word in FINISHED):
        time.sleep(POLL_S)
        status = kaggle("kernels", "status", kernel).strip()
        print(f"  {time.strftime('%H:%M:%S')} {status}", flush=True)
    if "complete" not in status.lower():
        print(f"The kernel didn't complete: {status}", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory() as temporary:
        download = Path(temporary)
        print(kaggle("kernels", "output", kernel, "-p", str(download)))
        missing = [name for name in KEEP if not (download / name).exists()]
        if missing:
            print(f"The kernel's output has no {', '.join(missing)}.", file=sys.stderr)
            return 1
        target = args.out / args.name
        # Everything the kernel wrote (the merged model, the adapter, the log), and the
        # files ClassifierRouter.load reads at the top of the folder.
        shutil.copytree(download, target, dirs_exist_ok=True)
        for name in KEEP:
            shutil.copy2(download / name, target / Path(name).name)
    metrics = json.loads((target / "metrics.json").read_text(encoding="utf-8"))
    print(
        f"Wrote {target}: best validation accuracy {metrics['best_val_accuracy']}, "
        f"ONNX difference {metrics['onnx_max_abs_diff']:.2e}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
