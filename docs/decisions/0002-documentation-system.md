# ADR-0002: Keep all project documentation in the repo

- **Status:** Accepted
- **Date:** 2026-10-15
- **Phase:** Planning

## Context

Decisions, reasoning, commands and results should be captured while the work happens, not reconstructed later. The documentation has to survive across working sessions, be reviewed alongside the code, and let anyone evaluating the project follow how and why it was built.

## Options considered

| Option | Pros | Cons |
|---|---|---|
| **Docs in the repo (`docs/`)** | Versioned with the code; reviewed in the same commits; visible on GitHub | Has to be kept current as part of each change |
| External wiki or notes tool | Comfortable editing | Drifts from the code; not versioned with commits |
| Code comments only | Close to the code | No narrative and no reasons |

## Decision

All documentation lives in `docs/`, with these rules:

1. **Every working session** adds a [build log](../BUILD_LOG.md) entry: goal, what changed, commands, results, problems and fixes, next steps.
2. **Every choice between real alternatives** gets an ADR in `decisions/`.
3. **Every component that lands** gets a concept guide in `concepts/`, using the [template](../concepts/_template.md): what it is, why it's needed, how it works here, where it lives in the code, how it was measured, pitfalls, references and review questions.
4. **Every dataset** gets a data card in `data/`. **Every experiment** gets a report in `eval/` with confidence intervals.
5. **Everything operable** gets a runbook in `runbooks/`.
6. **The project page** (`site/index.html`) is updated at phase milestones and deployed with GitHub Pages.

## Consequences

- A small, steady documentation cost per session, in exchange for a complete record of how the system was built.
- The README and project page are assembled from these documents instead of being written from memory at the end.

## References

- Michael Nygard, *Documenting Architecture Decisions* (2011).
