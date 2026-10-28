# ADR-0032: Deploy from GitHub Actions without keys, prove the new revision serves, and roll back on a failed smoke test

- **Status:** Accepted
- **Date:** 2026-10-28
- **Phase:** 8

## Context

[ADR-0031](0031-google-cloud-topology.md) puts the copilot on Cloud Run as four services built from one Dockerfile. The API's image carries a data bundle that isn't in the repository. The definition of done asks for deploys through GitHub Actions with no stored keys. Terraform owns the services' configuration and ignores their images, so something else has to build the images, roll them out, and tell a good release from a bad one.

The constraints:

- **No laptop builds.** The laptop has under a gigabyte of free memory, so images can't be built there.
- **A public repository.** Nothing in it may unlock the cloud.
- **A demo that must not break silently.** A release that starts but can't answer has to be caught and undone without a person watching.

## Options considered

| Option | For | Against |
|---|---|---|
| Cloud Build triggers | Google's own; no credentials leave the cloud | A second CI system beside GitHub Actions; the data bundle and the checks would live in two places |
| `gcloud run deploy --source` from the laptop | Simple | Builds on Cloud Build from the laptop's working tree, so not from a reviewed commit; no checks before it |
| Terraform sets the image | One tool for everything | Every release becomes an infrastructure change; a plan would fight each deploy |
| **GitHub Actions, keyless, after CI's checks on main** | The same checks gate every release; workload identity federation stores no key; the commit is built and tagged by its SHA | The deploy workflow has to manage rollbacks itself |
| Canary releases (traffic split by percent) | Limits a bad release's reach | With one instance and a handful of visitors a day, a split shows nothing; it doubles the release's steps |

## Decision

**When a release happens.** After CI's checks pass on `main`, a deploy runs if the push changed what the images hold:

- `src/`, the Dockerfile, `pyproject.toml`, `uv.lock`;
- the router's examples or the evaluation results the UI shows;
- `infra/data-bundle.json`.

The Deploy workflow can also run by hand. The job is skipped until the deployment exists, which the repository variable `GCP_PROJECT_ID` signals. Runs on `main` queue instead of cancelling each other, so a rollout is never cut off.

**The steps:**

1. **Keyless access.** GitHub's OIDC token becomes an hour of the `github-deployer` account's access through workload identity federation. The provider accepts only this repository and `main` ([guide](../concepts/workload-identity-federation.md)).
2. **The data bundle.** The workflow fetches the bundle that `infra/data-bundle.json` names and checks its SHA-256. A different file fails the release.
3. **The images.** `api` and `mcp` are built with the bundle as the `data` build context; `ui` is built without it. Each is tagged with the commit's SHA and carries it as `GIT_SHA`. Layers are cached in GitHub Actions' cache.
4. **The rollout:** `api` first, since the others call it, then `mcp`, then `ui`. Each service's previous revision is recorded first. Each update sends all traffic to the latest revision, which also undoes an earlier rollback's pin.
5. **The smoke tests:**
   - the private API's `/healthz` must report this commit, called with an ID token for its deterministic address;
   - its `/readyz` must pass, which reads the facts database, the pages, Qdrant with its key and Firestore;
   - the MCP server must answer an MCP `initialize`;
   - the UI's health endpoint must answer.
6. **The rollback.** If any step after the rollout fails, every service's traffic goes back to the revision it replaced.

## Consequences

- **A release is a commit.** The running revision reports the commit it was built from, and the registry tags images by SHA. Rolling back by hand is moving traffic to an earlier revision ([runbook](../runbooks/deploy.md)).
- **What may deploy.** Only `main`, after every check, through a GitHub environment named `production`, can deploy. Forks and branches are refused at the token exchange.
- **What isn't redeployed.** A push that changes only docs or Terraform doesn't redeploy. A failed release stays rolled back until the next change, or a manual run.
- **What CI needs.** Seven repository variables, none of them secret: `GCP_PROJECT_ID`, `GCP_PROJECT_NUMBER`, `GCP_REGION`, `GCP_WIF_PROVIDER`, `GCP_DEPLOYER_SA`, `GCP_REGISTRY` and `GCP_DATA_BUCKET`. The deployer account may also call the API and the worker, for the smoke tests.
- **The worker** is part of the rollout: its image is the API's, started as the worker, and its `/healthz` must report the commit too.

## References

- [google-github-actions/auth](https://github.com/google-github-actions/auth): OIDC access and ID tokens.
- Cloud Run: [rollbacks and traffic migration](https://cloud.google.com/run/docs/rollouts-rollbacks-traffic-migration).
- Docker: [named build contexts](https://docs.docker.com/build/building/context/#named-contexts).
- [ADR-0031](0031-google-cloud-topology.md); [deploy runbook](../runbooks/deploy.md).
