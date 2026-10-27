"""Staging a trained router for the Hugging Face Hub."""

from __future__ import annotations

from pathlib import Path

import pytest

from copilot.training.hub import ROUTER_LAYOUT, stage


def model_folder(root: Path) -> Path:
    """A model folder as `poe kaggle-router` writes it, with placeholder files."""
    for source in ROUTER_LAYOUT.values():
        path = root / source
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
    return root


def test_stage_lays_the_files_out_as_the_hub_reads_them(tmp_path: Path) -> None:
    folder = model_folder(tmp_path / "router-v2")
    card = tmp_path / "card.md"
    card.write_text("---\nlicense: mit\n---\n# Router\n", encoding="utf-8")
    out = tmp_path / "out"
    out.mkdir()

    published = stage(folder, card, out)

    assert published[0] == "README.md"
    assert (out / "README.md").read_text(encoding="utf-8").startswith("---\nlicense: mit")
    assert (out / "onnx" / "model.onnx").read_text(encoding="utf-8") == "router.onnx"
    assert (out / "config.json").read_text(encoding="utf-8") == "model/config.json"
    assert sorted(published[1:]) == sorted(ROUTER_LAYOUT)


def test_stage_names_what_is_missing_before_copying(tmp_path: Path) -> None:
    folder = model_folder(tmp_path / "router-v2")
    (folder / "router.onnx").unlink()
    out = tmp_path / "out"
    out.mkdir()

    with pytest.raises(FileNotFoundError, match=r"router\.onnx.*card\.md"):
        stage(folder, tmp_path / "card.md", out)
    assert list(out.iterdir()) == []
