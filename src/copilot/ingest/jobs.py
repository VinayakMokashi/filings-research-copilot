"""Ingestion jobs: one per document, run by a local runner now and an SQS-driven worker in Phase 8.

A job names one document. A handler does the work (chunk, embed, upsert) and returns a
`JobResult`. The local runner works through jobs in order, records a failure and moves on,
and appends every result to a JSON Lines log, so a long run can be watched and, after an
interruption, simply started again: the index skips chunks it already holds.
"""

from __future__ import annotations

import json
import time
import traceback
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

from copilot.logs import get_logger

log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class Job:
    doc_name: str


@dataclass(frozen=True, slots=True)
class JobResult:
    doc_name: str
    chunks: int = 0
    added: int = 0
    seconds: float = 0.0
    error: str | None = None


Handler = Callable[[Job], JobResult]


class Runner(Protocol):
    def run(self, jobs: Sequence[Job], handle: Handler) -> list[JobResult]: ...


@dataclass(frozen=True, slots=True)
class LocalRunner:
    """Runs jobs one after another in this process, logging each result."""

    log_path: Path | None = None

    def run(self, jobs: Sequence[Job], handle: Handler) -> list[JobResult]:
        results = []
        for number, job in enumerate(jobs, start=1):
            started = time.perf_counter()
            try:
                result = handle(job)
            except Exception as exc:  # one bad document mustn't stop the run
                result = JobResult(job.doc_name, error=f"{type(exc).__name__}: {exc}")
                log.error(
                    "ingest.job_failed", doc=job.doc_name, trace=traceback.format_exc(limit=3)
                )
            result = JobResult(
                result.doc_name,
                result.chunks,
                result.added,
                round(time.perf_counter() - started, 2),
                result.error,
            )
            results.append(result)
            log.info("ingest.job_done", n=f"{number}/{len(jobs)}", **asdict(result))
            if self.log_path is not None:
                self.log_path.parent.mkdir(parents=True, exist_ok=True)
                with self.log_path.open("a", encoding="utf-8", newline="\n") as out:
                    out.write(json.dumps(asdict(result)) + "\n")
        return results
