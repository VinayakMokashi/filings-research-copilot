"""Check every link in the documentation (step 10.5).

Reads the README, every Markdown file the repository tracks and the project page, and checks:

- **Relative links:** the file or folder exists, and a `#fragment` names a heading in the
  target (GitHub's anchors: lowercase, punctuation dropped, spaces as hyphens, repeats
  numbered) or an HTML `id`/`name` in it.
- **Links to this repository on GitHub** (`.../blob/main/<path>`, `.../tree/main/<path>`): the
  same checks on the local file, so they hold on `main` once a change merges.
- **Other web links,** with `--external` only: each address is fetched once. A 401, 403 or
  429 is reported as refused, to check by hand, since many sites turn scripts away.

Links inside code blocks and inline code are skipped. Prints `file:line target (reason)` for
each problem and exits 1 if any relative link or anchor is broken.

Usage: uv run poe check-links
       uv run poe check-links --external      (also fetches every web address once)
"""

from __future__ import annotations

import argparse
import asyncio
import re
import subprocess
import sys
from collections import defaultdict
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

import httpx

ROOT = Path(__file__).resolve().parents[1]
REPO_URL = re.compile(
    r"^https://github\.com/VinayakMokashi/filings-research-copilot/(?:blob|tree)/main/([^#?]*)"
)
MD_LINK = re.compile(r"!?\[(?:[^\]\[]|\[[^\]]*\])*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
HTML_LINK = re.compile(r"""(?:href|src)\s*=\s*["']([^"']+)["']""")
HTML_ID = re.compile(r"""\b(?:id|name)\s*=\s*["']([^"']+)["']""")
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
FENCE = re.compile(r"^\s*(```|~~~)")
INLINE_CODE = re.compile(r"`+[^`]*`+")
# A <link rel="preconnect"> names a host to warm up, not a page.
PRECONNECT = re.compile(r"""<link\b[^>]*\brel=["'](?:preconnect|dns-prefetch)["'][^>]*>""")
# Addresses that aren't pages to fetch with GET, and the status that shows they are there.
NOT_PAGES = {
    # The MCP server answers MCP's POST requests (streamable HTTP); a plain GET gets 400.
    "https://mcp-499690143794.asia-south1.run.app/mcp": 400,
}


@dataclass(frozen=True, slots=True)
class Link:
    file: Path
    line: int
    target: str


def slug(text: str) -> str:
    """GitHub's anchor for a heading's text, before repeats are numbered."""
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)  # a link's text stays
    text = re.sub(r"<[^>]+>", "", text).replace("`", "").replace("*", "")
    kept = "".join(ch for ch in text.lower() if ch.isalnum() or ch in " -_")
    return kept.replace(" ", "-")


def anchors(path: Path) -> set[str]:
    """Every anchor a Markdown or HTML file offers: its headings and its ids."""
    text = path.read_text(encoding="utf-8", errors="replace")
    found = set(HTML_ID.findall(text))
    if path.suffix.lower() == ".md":
        seen: dict[str, int] = defaultdict(int)
        fenced = False
        for line in text.splitlines():
            if FENCE.match(line):
                fenced = not fenced
                continue
            match = None if fenced else HEADING.match(line)
            if match:
                base = slug(match.group(2))
                found.add(base if not seen[base] else f"{base}-{seen[base]}")
                seen[base] += 1
    return found


def links(path: Path) -> Iterator[Link]:
    """The links in one file, outside code blocks and inline code."""
    fenced = False
    for number, line in enumerate(
        path.read_text(encoding="utf-8", errors="replace").splitlines(), 1
    ):
        if path.suffix.lower() == ".md" and FENCE.match(line):
            fenced = not fenced
            continue
        if fenced:
            continue
        line = INLINE_CODE.sub("", line) if path.suffix.lower() == ".md" else line
        line = PRECONNECT.sub("", line)
        for pattern in (MD_LINK, HTML_LINK):
            for target in pattern.findall(line):
                yield Link(path, number, target)


def tracked_files(root: Path) -> list[Path]:
    """The README, every tracked Markdown file and the project page."""
    found = subprocess.run(
        ["git", "ls-files", "*.md", "docs/site/*.html"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    return [root / name for name in found]


def check_local(link: Link, root: Path, cache: dict[Path, set[str]]) -> str | None:
    """Why a relative or same-repository link is broken, or None."""
    target = link.target
    repo = REPO_URL.match(target)
    if repo:
        path_part, _, fragment = target[len(repo.group(0)) - len(repo.group(1)) :].partition("#")
        destination = root / unquote(path_part)
    else:
        path_part, _, fragment = target.partition("#")
        path_part = path_part.split("?", 1)[0]
        destination = (link.file.parent / unquote(path_part)) if path_part else link.file
    destination = destination.resolve()
    if not destination.exists():
        return "missing file"
    if root.resolve() not in (destination, *destination.parents):
        return "outside the repository"
    if fragment and destination.is_file() and destination.suffix.lower() in (".md", ".html"):
        if destination not in cache:
            cache[destination] = anchors(destination)
        if unquote(fragment) not in cache[destination]:
            return f"no anchor #{fragment}"
    return None


async def fetch_all(urls: Sequence[str], workers: int = 8) -> dict[str, str | None]:
    """Each web address's problem (None when it answered 2xx or 3xx)."""
    limit = asyncio.Semaphore(workers)
    headers = {"User-Agent": "Mozilla/5.0 (link check; +https://github.com/VinayakMokashi)"}
    results: dict[str, str | None] = {}

    async def one(client: httpx.AsyncClient, url: str) -> None:
        async with limit:
            try:
                response = await client.get(url, headers=headers)
                status = response.status_code
                if status < 400 or NOT_PAGES.get(url) == status:
                    results[url] = None
                elif status in (401, 403, 429):
                    results[url] = f"refused ({status}): check by hand"
                else:
                    results[url] = f"HTTP {status}"
            except httpx.HTTPError as exc:
                results[url] = f"unreachable ({type(exc).__name__})"

    async with httpx.AsyncClient(follow_redirects=True, timeout=25) as client:
        await asyncio.gather(*(one(client, url) for url in urls))
    return results


def main(argv: Sequence[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--external", action="store_true", help="also fetch every web address")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    root: Path = args.root

    files = tracked_files(root)
    cache: dict[Path, set[str]] = {}
    broken: list[tuple[Link, str]] = []
    web: dict[str, list[Link]] = defaultdict(list)
    count = 0
    for path in files:
        for link in links(path):
            count += 1
            target = link.target
            if target.startswith(("mailto:", "data:", "javascript:")):
                continue
            if target.startswith(("http://", "https://")) and not REPO_URL.match(target):
                web[target].append(link)
                continue
            problem = check_local(link, root, cache)
            if problem:
                broken.append((link, problem))

    for link, problem in broken:
        print(f"{link.file.relative_to(root)}:{link.line} {link.target} ({problem})")
    print(f"{count} links in {len(files)} files; {len(broken)} broken relative links or anchors")

    refused = 0
    if args.external:
        results = asyncio.run(fetch_all(sorted(web)))
        for url, problem in sorted(results.items()):
            if problem:
                refused += problem.startswith("refused")
                first = web[url][0]
                where = f"{first.file.relative_to(root)}:{first.line}"
                print(f"{where} {url} ({problem}; {len(web[url])} uses)")
        bad = sum(1 for p in results.values() if p and not p.startswith("refused"))
        print(f"{len(web)} web addresses: {bad} broken, {refused} refused")
        return 1 if broken or bad else 0
    print(f"{len(web)} web addresses not fetched (add --external)")
    return 1 if broken else 0


if __name__ == "__main__":
    raise SystemExit(main())
