"""Publish the classifier router on Hugging Face as a public model (step 7.2).

Stages a model folder that `poe kaggle-router` downloaded (data/models/<name>) in the Hub's
layout with the model card (`copilot.training.hub.stage`): README.md, the merged model
(config, safetensors, tokenizer), onnx/model.onnx, the LoRA adapter and the training
metrics. Then it creates the public model repository if needed and uploads the folder.

The token is the settings' HF_TOKEN (a fine-grained token with write access to the
namespace); it is never printed. `--dry-run` stages and lists the files without uploading.

Usage:
  uv run poe publish-router --model-dir data/models/router-v2 \
      --repo vinayakmokashi45/filings-research-copilot-router
"""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

from copilot.config import get_settings
from copilot.training.hub import stage

CARD = Path("docs/models/router-card.md")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--repo", required=True, help="namespace/name on the Hub")
    parser.add_argument("--card", type=Path, default=CARD)
    parser.add_argument("--message", default="Upload the classifier router")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    with tempfile.TemporaryDirectory() as temporary:
        folder = Path(temporary)
        for path in stage(args.model_dir, args.card, folder):
            print(f"  {path} ({(folder / path).stat().st_size:,} bytes)")
        if args.dry_run:
            print("Dry run: nothing uploaded.")
            return 0
        token = get_settings().hf_token
        if token is None:
            print("HF_TOKEN isn't set.")
            return 1
        from huggingface_hub import HfApi

        api = HfApi(token=token.get_secret_value())
        url = api.create_repo(args.repo, repo_type="model", private=False, exist_ok=True)
        commit = api.upload_folder(
            repo_id=args.repo, repo_type="model", folder_path=folder, commit_message=args.message
        )
    print(f"Published {url} ({commit.oid[:7]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
