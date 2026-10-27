"""Train the classifier router on a Kaggle GPU and download the model (step 7.2).

Builds the kernel in a temporary folder: kaggle/router/train_router.py with REF pinned to a
commit of this repository (the kernel reads the training set from GitHub at that commit),
and a kernel-metadata.json for the given Kaggle user. Pushes it with a T4 GPU, waits for
it to finish, and downloads its output to data/models/<name>/, with router.onnx,
metrics.json and the merged model's config.json and tokenizer.json (the files
`ClassifierRouter.load` reads) at the top of the folder. The Kaggle CLI runs through uvx
(`copilot.training.kaggle`).

Usage: uv run poe kaggle-router --user KAGGLE_USERNAME --ref COMMIT --name router-v1
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

from copilot.training import kaggle

KERNEL_SOURCE = Path("kaggle/router/train_router.py")
SLUG = "frc-router"
KEEP = ("router.onnx", "metrics.json", "model/config.json", "model/tokenizer.json")


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
        code = kaggle.pin(KERNEL_SOURCE.read_text(encoding="utf-8"), args.ref)
        metadata = kaggle.kernel_metadata(args.user, SLUG, KERNEL_SOURCE.name)
        kaggle.write_kernel(folder, KERNEL_SOURCE.name, code, metadata)
        print(kaggle.push(folder))

    status = kaggle.wait(kaggle.kernel_status(kernel))
    if "complete" not in status.lower():
        print(f"The kernel didn't complete: {status}", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory() as temporary:
        download = Path(temporary)
        print(kaggle.download(kernel, download))
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
