"""Train the domain embedder on a Kaggle GPU; download the model and the corpus's vectors (7.1).

1. Writes the kernel's data to data/processed/embedder/ (`copilot.training.embedder`): the
   synthetic pairs with their split, the training filings' 480-token chunks and the corpus's
   page chunks, gzipped, with the dataset's metadata; and the manifest (counts and checksums,
   no text) to data/reference/embedder_data_manifest.json.
2. Uploads the folder as a private Kaggle dataset, or a new version of it, when its checksums
   differ from the last upload's (data/processed/embedder/uploaded.json), and waits until
   Kaggle has processed it.
3. Pushes kaggle/embedder/train_embedder.py as a private kernel with a T4 GPU, REF pinned to
   the given commit (the record of which code ran; the kernel reads only the dataset), waits
   for it, and downloads its output to data/models/<name>/: model/, embedder/ and base/
   (each with model.onnx, tokenizer.json and config.json), vectors/ and metrics.json.

The filing text stays out of the repository: FinanceBench's filings are CC BY-NC 4.0.

Usage: uv run poe kaggle-embedder --user KAGGLE_USERNAME --ref COMMIT --name embedder-v1
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

from copilot.config import get_settings
from copilot.eval import financebench as fb
from copilot.ingest.chunking import read_chunks
from copilot.training import embedder, kaggle
from copilot.training.pairs import load_pairs

KERNEL_SOURCE = Path("kaggle/embedder/train_embedder.py")
SLUG = "frc-embedder"
DATASET_SLUG = "frc-embedder-data"
MANIFEST = Path("data/reference/embedder_data_manifest.json")
KEEP = (
    "metrics.json",
    "model/config.json",
    "embedder/model.onnx",
    "embedder/tokenizer.json",
    "base/model.onnx",
    "vectors/embedder.npy",
    "vectors/base.npy",
    "vectors/chunk_ids.json",
)


def prepare(data_dir: Path, folder: Path, user: str) -> dict[str, object]:
    """Write the dataset's files and metadata into `folder`; the manifest."""
    fb_root = data_dir / "raw" / "financebench"
    chunks_dir = data_dir / "processed" / "chunks"
    pairs_path = data_dir / "processed" / "synthetic" / "pairs.jsonl"
    pairs = load_pairs(pairs_path)
    train_filings = sorted({pair.doc_name for pair in pairs})
    chunks = embedder.by_place(
        chunk
        for name in train_filings
        for chunk in read_chunks(chunks_dir / "tokens-480" / f"{name}.jsonl")
    )
    val = embedder.split_filings(train_filings)
    records = embedder.pair_records(pairs, {chunk.chunk_id: chunk for chunk in chunks}, val)
    corpus = sorted({question.doc_name for question in fb.load_questions(fb_root)})
    pages = embedder.by_place(
        chunk for name in corpus for chunk in read_chunks(chunks_dir / "page" / f"{name}.jsonl")
    )
    files = {
        "pairs.jsonl.gz": embedder.write_jsonl_gz(records, folder / "pairs.jsonl.gz"),
        "chunks.jsonl.gz": embedder.write_jsonl_gz(
            map(embedder.chunk_record, chunks), folder / "chunks.jsonl.gz"
        ),
        "pages.jsonl.gz": embedder.write_jsonl_gz(
            map(embedder.page_record, pages), folder / "pages.jsonl.gz"
        ),
    }
    metadata = kaggle.dataset_metadata(user, DATASET_SLUG, "frc embedder training data")
    (folder / "dataset-metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    source = json.loads(Path("data/reference/synthetic_pairs_manifest.json").read_text("utf-8"))
    return embedder.manifest(
        records, files, len(train_filings), len(corpus), str(source["pairs_sha256"])
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--user", required=True, help="your Kaggle username")
    parser.add_argument("--ref", required=True, help="the commit whose kernel code runs")
    parser.add_argument("--name", default="embedder-v1", help="folder under data/models")
    parser.add_argument("--out", type=Path, default=Path("data/models"))
    parser.add_argument("--prepare-only", action="store_true", help="write the data, no Kaggle")
    args = parser.parse_args(argv)
    data_dir = get_settings().data_dir
    folder = data_dir / "processed" / "embedder"
    folder.mkdir(parents=True, exist_ok=True)

    manifest = prepare(data_dir, folder, args.user)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"Wrote {folder} and {MANIFEST}: {manifest['pairs']}")
    if args.prepare_only:
        return 0

    dataset = f"{args.user}/{DATASET_SLUG}"
    uploaded = folder / "uploaded.json"
    previous = json.loads(uploaded.read_text("utf-8")) if uploaded.exists() else None
    if previous != manifest["files"]:
        with tempfile.TemporaryDirectory() as temporary:
            staging = Path(temporary)
            for name in (*embedder.FILES, "dataset-metadata.json"):
                shutil.copy2(folder / name, staging / name)
            print(kaggle.publish_dataset(staging, dataset, f"Data at {args.ref[:7]}"))
        print(f"Dataset {dataset}: {kaggle.wait_for_dataset(dataset)}")
        uploaded.write_text(json.dumps(manifest["files"], indent=2), encoding="utf-8")
    else:
        print(f"Dataset {dataset} is up to date.")

    kernel = f"{args.user}/{SLUG}"
    with tempfile.TemporaryDirectory() as temporary:
        staging = Path(temporary)
        code = kaggle.pin(KERNEL_SOURCE.read_text(encoding="utf-8"), args.ref)
        metadata = kaggle.kernel_metadata(args.user, SLUG, KERNEL_SOURCE.name, [dataset])
        kaggle.write_kernel(staging, KERNEL_SOURCE.name, code, metadata)
        print(kaggle.push(staging))
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
        shutil.copytree(download, target, dirs_exist_ok=True)
    metrics = json.loads((target / "metrics.json").read_text(encoding="utf-8"))
    chosen = metrics["chosen"]
    print(
        f"Wrote {target}: base model on validation {metrics['base_val']}; chosen lr "
        f"{chosen['lr']:g} epoch {chosen['epoch']}: {chosen['val']}; "
        f"ONNX differences {metrics['onnx']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
