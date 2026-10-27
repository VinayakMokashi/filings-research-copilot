"""Kaggle kernels and datasets: pinned code, private GPU kernels, and waiting on the CLI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from copilot.training import kaggle


def test_pin_sets_the_commit_and_refuses_code_without_the_line() -> None:
    code = 'REF = "main"\nprint(REF)\n'

    assert kaggle.pin(code, "abc1234") == 'REF = "abc1234"\nprint(REF)\n'
    with pytest.raises(ValueError, match="REF"):
        kaggle.pin("print('no ref')\n", "abc1234")


def test_kernel_metadata_is_a_private_gpu_kernel_with_its_datasets() -> None:
    metadata = kaggle.kernel_metadata("someone", "frc-embedder", "train.py", ["someone/data"])

    assert metadata["id"] == "someone/frc-embedder"
    assert metadata["is_private"] is True
    assert metadata["enable_gpu"] is True
    assert metadata["dataset_sources"] == ["someone/data"]


def test_write_kernel_writes_the_code_and_its_metadata(tmp_path: Path) -> None:
    metadata = kaggle.kernel_metadata("someone", "frc-router", "train.py")

    kaggle.write_kernel(tmp_path, "train.py", "print(1)\n", metadata)

    assert (tmp_path / "train.py").read_bytes() == b"print(1)\n"
    assert json.loads((tmp_path / "kernel-metadata.json").read_text("utf-8")) == metadata


def test_wait_polls_until_the_kernel_finishes() -> None:
    statuses = iter(["running", "running", 'has status "KernelWorkerStatus.COMPLETE"'])
    sleeps: list[float] = []

    last = kaggle.wait(lambda: next(statuses), poll_s=5, sleep=sleeps.append, log=lambda _: None)

    assert "COMPLETE" in last
    assert sleeps == [5, 5, 5]


def test_wait_for_dataset_returns_when_ready_and_raises_on_an_error() -> None:
    statuses = iter(["pending", "ready"])

    assert kaggle.wait_for_dataset("a/b", sleep=lambda _: None, status=lambda: next(statuses))
    with pytest.raises(RuntimeError, match="failed"):
        kaggle.wait_for_dataset("a/b", sleep=lambda _: None, status=lambda: "error")


def test_wait_for_dataset_waits_out_a_new_dataset_that_isnt_visible_yet() -> None:
    answers: list[str | Exception] = [RuntimeError("403 Client Error: Forbidden"), "ready"]

    def status() -> str:
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    assert kaggle.wait_for_dataset("a/b", sleep=lambda _: None, status=status) == "ready"
    with pytest.raises(TimeoutError, match="after 2 polls"):
        kaggle.wait_for_dataset("a/b", sleep=lambda _: None, status=lambda: "pending", attempts=2)


def test_publish_dataset_creates_a_new_one_and_versions_an_old_one(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[tuple[str, ...]] = []
    exists = {"value": False}

    def fake_cli(*args: str) -> str:
        calls.append(args)
        if args[:2] == ("datasets", "status") and not exists["value"]:
            raise RuntimeError("403 Forbidden")
        return "ok"

    monkeypatch.setattr(kaggle, "cli", fake_cli)
    kaggle.publish_dataset(tmp_path, "a/b", "first")
    exists["value"] = True
    kaggle.publish_dataset(tmp_path, "a/b", "second")

    assert [call[:2] for call in calls] == [
        ("datasets", "status"),
        ("datasets", "create"),
        ("datasets", "status"),
        ("datasets", "version"),
    ]
    assert "--public" not in calls[1]
    assert "second" in calls[3]
