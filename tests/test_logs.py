from __future__ import annotations

import json

import pytest

from copilot.logs import configure_logging, get_logger


def test_json_logs_are_machine_readable(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO", "json")

    get_logger("test").info("llm.call", role="fast", cost_usd=0.001)

    record = json.loads(capsys.readouterr().err.strip().splitlines()[-1])
    assert record["event"] == "llm.call"
    assert record["role"] == "fast"
    assert record["level"] == "info"
    assert "timestamp" in record


def test_messages_below_the_level_are_dropped(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("WARNING", "json")
    logger = get_logger("test")

    logger.info("hidden")
    logger.warning("shown")

    output = capsys.readouterr().err
    assert "hidden" not in output
    assert "shown" in output
