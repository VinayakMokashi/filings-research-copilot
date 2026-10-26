# syntax=docker/dockerfile:1
# The copilot's images, from the locked environment:
#   api  the API, with the router's examples; the same image runs the MCP server
#   ui   the Streamlit UI, with the evaluation results its results page reads
# Both run as a non-root user and listen on $PORT when it is set, as Cloud Run sets it.
# The data (facts database, parsed pages, models, caches) is mounted at /app/data, not built in.

# Python 3.12.15 on Debian trixie, and uv 0.12.19, pinned by digest; Dependabot moves them.
FROM ghcr.io/astral-sh/uv:0.13.5@sha256:32a7bb39b496babbd997b0a39a4d66c126bdaf5661b302bf6f06abda8deca6ff AS uv

FROM python:3.12-slim-trixie@sha256:a0f57064cbdcd6285fa45f51237ab0b35ea8ebaed06a1f5973e89e19dfb86704 AS build
COPY --from=uv /uv /bin/uv
# git fetches text2sql-analyst, a pinned git dependency.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock ./

# Dependencies first, so a code change rebuilds only the last layer.
FROM build AS build-api
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-group ui --no-install-project
COPY README.md LICENSE ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-group ui

FROM build AS build-ui
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project
COPY README.md LICENSE ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

FROM python:3.12-slim-trixie@sha256:a0f57064cbdcd6285fa45f51237ab0b35ea8ebaed06a1f5973e89e19dfb86704 AS runtime
ARG UID=1000
RUN useradd --uid "${UID}" --create-home --shell /usr/sbin/nologin copilot
ENV PATH="/app/.venv/bin:${PATH}" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

FROM runtime AS api
COPY --from=build-api /app /app
# The semantic router's examples, which back up the model router (ADR-0017).
COPY eval/routing ./eval/routing
USER copilot
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn copilot.api.app:create_app --factory --host 0.0.0.0 --port ${PORT:-8000}"]

FROM runtime AS ui
COPY --from=build-ui /app /app
COPY eval/results ./eval/results
USER copilot
EXPOSE 8501
CMD ["sh", "-c", "exec streamlit run src/copilot/ui/app.py --server.address 0.0.0.0 --server.port ${PORT:-8501} --server.headless true --server.fileWatcherType none --browser.gatherUsageStats false --client.toolbarMode minimal"]
