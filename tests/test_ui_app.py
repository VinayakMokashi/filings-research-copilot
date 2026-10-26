"""The UI's Streamlit script, run headless: it renders without the API, and shows an answer."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from streamlit.testing.v1 import AppTest

from copilot.ui.client import CopilotClient, Event

APP = Path(__file__).resolve().parents[1] / "src" / "copilot" / "ui" / "app.py"
RESPONSE = {
    "type": "response",
    "question": "What was 3M's capital expenditure in 2018?",
    "standalone": "What was 3M's capital expenditure in 2018?",
    "route": "data",
    "text": "3M's capital expenditure was $1,577 million in 2018 [1].",
    "answered": True,
    "citations": [
        {"number": 1, "label": "Facts database", "doc_name": "facts-database", "page": None}
    ],
    "sql": "SELECT value FROM annual_values WHERE metric = 'capital_expenditure'",
    "table": {
        "columns": ["fiscal_year", "value"],
        "rows": [[2018, 1577000000]],
        "truncated": False,
    },
    "chart": {"kind": "metric", "y": "value", "x": None},
    "validation": {},
}


def fake_ask(self: CopilotClient, question: str, thread_id: str | None = None) -> Iterator[Event]:
    yield Event("meta", {"request_id": "r1", "thread_id": "t1"})
    yield Event("start", {"node": "route"})
    yield Event("event", {"event": "route", "route": "data", "router": "cascade", "model": "m"})
    yield Event("end", {"node": "route", "ms": 512.0})
    yield Event("response", RESPONSE)
    yield Event("done", {"thread_id": "t1"})


def test_the_app_renders_and_says_when_the_api_is_down(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRC_API_URL", "http://127.0.0.1:9")  # nothing listens there

    app = AppTest.from_file(str(APP), default_timeout=60).run()

    assert not app.exception
    assert app.title[0].value == "Filings Research Copilot"
    assert any("Not ready" in warning.value for warning in app.sidebar.warning)


def test_a_question_shows_its_answer_figure_and_query(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(CopilotClient, "ask", fake_ask)
    monkeypatch.setattr(CopilotClient, "ready", lambda self: {"ready": True, "checks": {}})

    app = AppTest.from_file(str(APP), default_timeout=60).run()
    app.chat_input[0].set_value("What was 3M's capital expenditure in 2018?").run()

    assert not app.exception
    texts: list[Any] = [element.value for element in app.markdown]
    assert str(RESPONSE["text"]).replace("$", "\\$") in texts  # dollar signs escaped
    assert app.metric[0].value == "1,577,000,000"
    sql = str(RESPONSE["sql"])
    assert any(sql in code.value for code in app.code)
