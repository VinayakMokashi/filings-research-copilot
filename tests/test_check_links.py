"""The documentation's link check (step 10.5)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest


def script(name: str) -> ModuleType:
    path = Path(__file__).resolve().parents[1] / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # dataclasses look their module up while the class is made
    spec.loader.exec_module(module)
    return module


check_links = script("check_links")


@pytest.mark.parametrize(
    ("heading", "anchor"),
    [
        (
            "2026-11-23 · Phase 9 · The close: a baseline",
            "2026-11-23--phase-9--the-close-a-baseline",
        ),
        (
            "Amendment (15 November): a week instead of two",
            "amendment-15-november-a-week-instead-of-two",
        ),
        ("What `poe check` runs", "what-poe-check-runs"),
        ("See [the report](eval/x.md)", "see-the-report"),
    ],
)
def test_anchors_follow_githubs_rules(heading: str, anchor: str) -> None:
    assert check_links.slug(heading) == anchor


def test_repeated_headings_are_numbered_and_code_blocks_skipped(tmp_path: Path) -> None:
    page = tmp_path / "page.md"
    page.write_text(
        "# Notes\n\n## Results\n\n```text\n## Not a heading\n```\n\n## Results\n"
        '<a id="kept"></a>\n',
        encoding="utf-8",
    )

    assert check_links.anchors(page) == {"notes", "results", "results-1", "kept"}


def test_broken_files_and_anchors_are_found(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "guide.md").write_text("# Guide\n\n## How it works\n", encoding="utf-8")
    readme = tmp_path / "README.md"
    readme.write_text(
        "[ok](docs/guide.md#how-it-works) [gone](docs/missing.md) "
        "[no anchor](docs/guide.md#why) `[code](docs/missing.md)`\n"
        "```\n[fenced](docs/missing.md)\n```\n"
        "[here](#readme) [repo](https://github.com/VinayakMokashi/filings-research-copilot/"
        "blob/main/docs/guide.md#guide)\n",
        encoding="utf-8",
    )
    cache: dict[Path, set[str]] = {}

    found = list(check_links.links(readme))
    problems = [check_links.check_local(link, tmp_path, cache) for link in found]

    assert [link.target for link in found] == [
        "docs/guide.md#how-it-works",
        "docs/missing.md",
        "docs/guide.md#why",
        "#readme",
        "https://github.com/VinayakMokashi/filings-research-copilot/blob/main/docs/guide.md#guide",
    ]
    assert problems == [None, "missing file", "no anchor #why", "no anchor #readme", None]


def test_a_preconnect_hint_is_not_a_link(tmp_path: Path) -> None:
    page = tmp_path / "index.html"
    page.write_text(
        '<link rel="preconnect" href="https://fonts.example.com">\n'
        '<link rel="stylesheet" href="https://fonts.example.com/css2?family=X">\n',
        encoding="utf-8",
    )

    assert [link.target for link in check_links.links(page)] == [
        "https://fonts.example.com/css2?family=X"
    ]
