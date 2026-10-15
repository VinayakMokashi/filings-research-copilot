# ADR-0004: Tooling, repository layout and Git workflow

- **Status:** Accepted
- **Date:** 2026-10-15
- **Phase:** 0

## Context

The repository needs reproducible installs on Windows and Linux, fast feedback while coding, the same code checks locally as in CI, and no secrets in a public history.

## Options considered

| Option | Pros | Cons |
|---|---|---|
| **uv** for Python, dependencies and the lockfile | One fast tool; installs Python too; cross-platform lockfile | Newer than the alternatives |
| Poetry or pip-tools | Mature | Slower; separate tools for Python versions and locking |
| **poethepoet** tasks in `pyproject.toml` | Same commands on every OS | One more dev dependency |
| make | Familiar | Not installed on Windows by default |
| **Actions pinned to commit SHAs** | A moved tag can't change what runs | Updates need the new SHA (Dependabot handles it) |
| Actions pinned to tags | Easier to read | A tag can be moved to different code |
| gitleaks GitHub Action | One line | Scans only the pushed commit range, which fails when that range starts at the root commit (the first push) |
| **Pinned gitleaks CLI scanning the full history** | Covers every commit on every run; checksum-verified | A version and checksum to bump by hand |

## Decision

| Concern | Choice |
|---|---|
| Packaging | uv with a committed `uv.lock`; hatchling build; `src/copilot` layout; Python 3.12 |
| Lint and format | ruff (linter and formatter), line length 100 |
| Types | mypy in strict mode over `src`, `tests` and `scripts`, with the pydantic plugin |
| Tests | pytest; `integration` and `eval` markers are excluded by default; unit tests refuse DNS lookups of non-local hosts |
| Tasks | poethepoet: `uv run poe check` runs the same lint, format, type and test steps as CI; `uv run poe secrets` runs the same gitleaks scan through Docker |
| Hooks | pre-commit: ruff, YAML and TOML checks, whitespace, large files, private keys |
| CI | GitHub Actions: lint, format, types, tests; a gitleaks scan of the full history with `.gitleaks.toml` (default rules plus explicit Groq, Cerebras, OpenRouter and Langfuse key patterns); every action pinned to a commit SHA |
| Dependency updates | Dependabot (`.github/dependabot.yml`): weekly pull requests for GitHub Actions, `uv.lock` and pre-commit hooks, with a 7-day cooldown |
| Project page | `docs/site` deployed with GitHub Pages. Setting the Pages source to GitHub Actions is a one-time repository setting ([runbook](../runbooks/publishing-the-project-page.md)) |
| Commits | Conventional Commits, small and single-purpose |
| Branches | Phase 0 bootstraps `main` directly. From Phase 1, work lands through pull requests from `phase-N/<topic>` branches after CI passes |
| Local services | Docker Compose: Qdrant 1.19.2 and Postgres 18.6, bound to 127.0.0.1 (ports 6333 and 5433) |

## Consequences

- `uv run poe check` locally runs the same lint, format, type and test steps as CI. CI also installs with `uv sync --locked`, which fails on an out-of-date `uv.lock`; `uv run --locked poe check` catches that locally.
- GitHub raises no Dependabot alerts for actions pinned to a SHA, so action fixes arrive through the weekly update pull requests. The gitleaks CLI version in `ci.yml` is bumped by hand.
- Postgres is published on 5433 because a local PostgreSQL install held 5432 on the development machine. Both ports can be overridden in `.env`. Both services listen on 127.0.0.1 only.
- Unit tests never need network access or API keys; live checks are separate scripts.

## References

- uv: https://docs.astral.sh/uv/
- Ruff: https://docs.astral.sh/ruff/
- Conventional Commits: https://www.conventionalcommits.org/
- GitHub, *Security hardening for GitHub Actions* (pinning actions to a full-length commit SHA): https://docs.github.com/en/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions
- Dependabot options reference: https://docs.github.com/en/code-security/dependabot/working-with-dependabot/dependabot-options-reference
- gitleaks: https://github.com/gitleaks/gitleaks
