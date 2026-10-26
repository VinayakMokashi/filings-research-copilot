# ADR-0022: Build two images from one Dockerfile, and mount the data rather than build it in

- **Status:** Accepted
- **Date:** 2026-10-26
- **Phase:** 6

## Context

Step 6.6 asks for the whole local demo from one Compose command: Qdrant, Postgres, the API, the web UI and the MCP server. Phase 8 then runs the same images on Cloud Run ([ADR-0016](0016-deploy-on-google-cloud.md)).

The services need different things:

- **The API and the MCP server** need the code, the locked dependencies and the data: the facts database, the parsed pages, the embedding models and the model-call caches, about 3 GB under `data/`, much of it FinanceBench's PDFs and reranker models that only the evaluations use.
- **The web UI** needs only the code, the API's address and the evaluation results its results page reads.

The laptop has no GPU and the hosting is free-tier, so images should stay small and rebuild quickly when only the code changes. Secrets must never end up in an image.

## Options considered

| Option | For | Against |
|---|---|---|
| Data built into the images | Each image is complete on its own | Images of several gigabytes, rebuilt whenever the data changes; FinanceBench's documents would travel with every published image |
| **Data mounted at run time** | Small images; the containers use the same data as local runs | The data must be built before the stack starts; Cloud Run needs another way to get it |
| A Dockerfile per service | Each file is short | The base image and the dependency steps are written three times |
| **One multi-stage Dockerfile with a target per image** | One place for the base, the locked install and the user | A build names its target |

## Decision

1. **One Dockerfile, two images.** `api` runs the API and, with another command, the MCP server; `ui` runs Streamlit. A build stage with uv and git installs the locked dependencies (`uv sync --locked --no-dev`, without the `ui` group for `api`) in a layer that changes only with `uv.lock`, then the project; the runtime stage copies the environment and the code and runs as a non-root user. Bytecode is compiled at build time, for faster starts.
2. **Base images pinned by digest:** Python 3.12.15 on Debian trixie, and uv 0.12.19. Dependabot proposes new digests weekly.
3. **Data mounted at `/app/data`.** The `api` image carries only what the code reads at startup besides the data, the semantic router's examples (`eval/routing`); the `ui` image carries `eval/results`.
4. **Compose behind a profile.** The app services sit in the `app` profile, so `poe services-up` still starts only Qdrant and Postgres for development, and `poe stack-up` builds and starts everything and waits until it is healthy. Every port is bound to 127.0.0.1 and can be moved (`API_PORT`, `UI_PORT`, `MCP_PORT`). The API keeps conversations, notes, feedback, quotas and the answer cache in Postgres. The API and MCP containers read `.env` at run time; the UI container gets no secrets; and the build context is an allowlist, so `.env` and `data/` are never sent to the builder.
5. **`$PORT` when set,** as Cloud Run sets it; the defaults are 8000, 8501 and 8001.
6. **Health checks** for Compose: the API's `/readyz`, so the UI and MCP server start only once the API can answer; Streamlit's own health endpoint; a TCP check for the MCP server.
7. **DNS-rebinding protection on the MCP server's HTTP transport.** The SDK switches it on only when the server binds to localhost, and in a container it binds to every interface, so the server sets it itself: a request must name this machine, or a host given with `--allowed-host`.
8. **CI builds both images on every pull request** and checks that they run as a non-root user, that the code imports and that the Compose file parses.

## Evidence

- **Sizes and builds:** `api` 1.14 GB, of which the Python environment is 701 MB (LiteLLM alone 168 MB); `ui` 1.5 GB. Cold builds took 3.5 and 4.4 minutes on the laptop; a code change rebuilds only the last layers.
- **The whole stack, live,** with the local data: all five services healthy 48 seconds after `up`. `/readyz` passed its five checks, Postgres included; a question streamed 28 events in 2.9 seconds, its model calls served from the caches; over HTTP, the MCP server listed its tools, returned Coca-Cola's revenue for fiscal 2021 and 2022, found passages in the fiscal 2022 10-K, served a cached answer from Postgres in 0.04 seconds and read a filing page; a request naming another host was refused with 421; and the UI answered an example question in a browser.
- **The first start failed:** the router's examples weren't in the image, and the API's startup reads them. The image now carries them.

## Consequences

- **The data comes first.** The stack serves what `data/` and the Qdrant volume hold, so the facts database, the parsed pages and the index must be built as the runbooks describe.
- **File ownership on Linux.** The containers run as uid 1000 and write to `data/cache` and `data/traces`; where the host user differs, build with `--build-arg UID=$(id -u)`.
- **Cloud Run needs the data another way.** Phase 8 decides between building the facts database and pages into the image, mounting a bucket, and moving the vectors to a managed Qdrant.
- **LiteLLM's size stays.** Trimming it isn't worth the effort while the images run locally.

## References

- Docker, [Multi-stage builds](https://docs.docker.com/build/building/multi-stage/).
- uv, [Using uv in Docker](https://docs.astral.sh/uv/guides/integration/docker/).
- Docker, [Using profiles with Compose](https://docs.docker.com/compose/how-tos/profiles/).
- The [MCP server guide](../concepts/mcp-server.md), for the HTTP transport.
