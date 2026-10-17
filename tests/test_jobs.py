"""The local job runner: results in order, a failed job recorded without stopping the run."""

from __future__ import annotations

import json
from pathlib import Path

from copilot.ingest.jobs import Job, JobResult, LocalRunner


def test_the_runner_logs_every_result_and_survives_a_failure(tmp_path: Path) -> None:
    def handle(job: Job) -> JobResult:
        if job.doc_name == "bad":
            raise RuntimeError("boom")
        return JobResult(job.doc_name, chunks=3, added=2)

    log_path = tmp_path / "indexes" / "log.jsonl"
    results = LocalRunner(log_path).run([Job("a"), Job("bad"), Job("b")], handle)

    assert [r.error for r in results] == [None, "RuntimeError: boom", None]
    assert all(r.seconds >= 0 for r in results)
    lines = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    assert [line["doc_name"] for line in lines] == ["a", "bad", "b"]
    assert (lines[0]["chunks"], lines[0]["added"]) == (3, 2)


def test_a_rerun_appends_to_the_log(tmp_path: Path) -> None:
    log_path = tmp_path / "log.jsonl"
    runner = LocalRunner(log_path)

    runner.run([Job("a")], lambda job: JobResult(job.doc_name))
    runner.run([Job("a")], lambda job: JobResult(job.doc_name))

    assert len(log_path.read_text(encoding="utf-8").splitlines()) == 2
