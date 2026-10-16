"""Make the FinanceBench dev/test split (ADR-0006) and write eval/financebench/splits.json.

Run once, after `poe fetch-financebench` and before any tuning. The split file is
committed, and this script refuses to replace it unless --force is given.

Usage: uv run poe split-financebench
"""

from __future__ import annotations

import argparse

from copilot.config import get_settings
from copilot.eval import financebench as fb
from copilot.eval import splits


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--force", action="store_true", help="replace an existing split file")
    args = parser.parse_args(argv)

    if splits.SPLIT_FILE.exists() and not args.force:
        print(
            f"{splits.SPLIT_FILE} already exists. The split is fixed before any tuning; "
            "use --force only if you really mean to replace it."
        )
        return 1

    root = get_settings().data_dir / "raw" / "financebench"
    manifest = fb.load_manifest()
    questions_file = root / fb.QUESTIONS_PATH
    if fb.git_blob_sha1(questions_file.read_bytes()) != manifest.file(fb.QUESTIONS_PATH).git_sha1:
        print(f"{questions_file} doesn't match the manifest; run `poe fetch-financebench`.")
        return 1

    questions = fb.load_questions(root)
    documents = fb.load_documents(root)
    split = splits.split_by_company(splits.items_from(questions, documents))
    spec = splits.build_split_file(
        split, questions, documents, fb.read_jsonl(questions_file), manifest
    )
    splits.save_split_file(spec, overwrite=args.force)

    print(f"Wrote {splits.SPLIT_FILE} (seed {split.seed}, imbalance {float(split.score):.2f})")
    for name, side in spec.counts.items():
        print(
            f"  {name:4}  {side.questions:3} questions, {side.companies:2} companies, "
            f"{side.documents:2} documents  {side.question_types}"
        )
    print(f"  test companies: {', '.join(spec.test_companies)}")
    print(f"  test sha256: {spec.test_sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
