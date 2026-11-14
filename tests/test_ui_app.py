"""The UI's Streamlit script, run headless: it renders without the API, and shows an answer."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from streamlit.testing.v1 import AppTest

from copilot.api.client import CopilotClient, Event

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


def fake_ask(
    self: CopilotClient,
    question: str,
    thread_id: str | None = None,
    *,
    brief: bool = False,
    retry_of: str | None = None,
) -> Iterator[Event]:
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


def test_a_handed_on_answer_and_an_assessment_are_noted() -> None:
    from copilot.ui.app import assessed, handed_on

    doc = {"text": "Margins fell [1]. Assessment: they are under pressure [1].", "handoff": None}
    handed = {"text": "Sales in Asia rose [1].", "handoff": {"from": "data"}}

    assert handed_on(doc) == ""
    assert "the filings' text answered it" in handed_on(handed)
    assert "reading of the cited facts" in assessed(doc)
    assert assessed(handed) == ""


def test_a_brief_says_how_it_was_made_and_what_it_left_out() -> None:
    from copilot.ui.app import briefed

    brief = {
        "sections": [
            {"heading": "Results", "answered": True, "cut": 1},
            {"heading": "Risks", "answered": True, "cut": 0},
            {"heading": "Outlook", "answered": False, "cut": 0},
        ],
        "summary_cut": 1,
        "missing": ["Outlook"],
    }

    note = briefed(brief)

    assert note.startswith("A brief in 2 sections")
    assert "2 unsupported sentences cut" in note
    assert note.endswith("Not covered: Outlook.")
    assert briefed({}) == ""


def test_an_idle_page_leaves_for_the_paused_page(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(CopilotClient, "ready", lambda self: {"ready": True, "checks": {}})

    app = AppTest.from_file(str(APP), default_timeout=60).run()

    script = app.html[0].value
    assert "< 900000) return;" in script  # 15 minutes, the default
    assert 'location.replace("/app/static/paused.html?after=15")' in script
    for kind in ("pointermove", "keydown", "scroll", "touchstart"):
        assert f'"{kind}"' in script


def test_the_idle_limit_can_be_turned_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRC_UI_IDLE_MINUTES", "0")
    monkeypatch.setattr(CopilotClient, "ready", lambda self: {"ready": True, "checks": {}})

    app = AppTest.from_file(str(APP), default_timeout=60).run()

    assert not app.exception
    assert len(app.html) == 0


def test_the_paused_page_is_served_and_continues_to_the_app() -> None:
    from copilot.ui.app import PAUSED_PAGE

    page = (APP.parent / "static" / Path(PAUSED_PAGE).name).read_text(encoding="utf-8")

    assert '<a class="continue" href="/">Continue</a>' in page
    assert "A conversation in progress isn't kept." in page
    # Streamlit serves static/ only when told to, in the image and in `poe ui`
    for config in ("Dockerfile", "pyproject.toml"):
        assert "--server.enableStaticServing true" in Path(config).read_text(encoding="utf-8")


DOC_ANSWER = RESPONSE | {
    "route": "doc",
    "text": "Netflix names intense competition as a risk [1].",
    "citations": [{"number": 1, "label": "Netflix, PDF page 9", "doc_name": "N", "page": 8}],
    "table": None,
    "chart": None,
    "sql": None,
}
SECOND = DOC_ANSWER | {"text": "Competition for viewers' time is a risk Netflix names [1]."}


def test_a_thumbs_down_offers_another_answer_and_keeps_the_pick(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asked: list[str | None] = []
    picks: list[tuple[str, str, str]] = []

    def ask(
        self: CopilotClient,
        question: str,
        thread_id: str | None = None,
        *,
        brief: bool = False,
        retry_of: str | None = None,
    ) -> Iterator[Event]:
        asked.append(retry_of)
        request_id = "r2" if retry_of else "r1"
        yield Event("meta", {"request_id": request_id, "thread_id": "t9" if retry_of else "t1"})
        yield Event("response", SECOND if retry_of else DOC_ANSWER)
        yield Event("done", {})

    def preference(self: CopilotClient, first: str, second: str, chosen: str) -> bool:
        picks.append((first, second, chosen))
        return True

    monkeypatch.setattr(CopilotClient, "ask", ask)
    monkeypatch.setattr(CopilotClient, "preference", preference)
    monkeypatch.setattr(CopilotClient, "feedback", lambda self, *args: True)
    monkeypatch.setattr(CopilotClient, "ready", lambda self: {"ready": True, "checks": {}})

    app = AppTest.from_file(str(APP), default_timeout=60).run()
    app.chat_input[0].set_value("What risks does Netflix name?").run()
    assert not [b for b in app.button if b.label == "Try another answer"]  # not before a rating
    assert any("Nothing that identifies you" in caption.value for caption in app.caption)
    app.feedback[0].set_value(0).run()  # thumbs down
    app.button(key="retry-1").click().run()

    assert not app.exception
    assert asked == [None, "r1"]
    texts: list[Any] = [element.value for element in app.markdown]
    assert str(SECOND["text"]) in texts
    app.radio(key="pick-1").set_value("The second").run()

    assert picks == [("r1", "r2", "second")]
    assert any("your pick is kept" in toast.value for toast in app.toast)
    app.run()
    assert any(caption.value == "Your pick is kept." for caption in app.caption)
    assert not app.radio  # picked once


def test_a_data_answer_offers_no_second_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(CopilotClient, "ask", fake_ask)
    monkeypatch.setattr(CopilotClient, "feedback", lambda self, *args: True)
    monkeypatch.setattr(CopilotClient, "ready", lambda self: {"ready": True, "checks": {}})

    app = AppTest.from_file(str(APP), default_timeout=60).run()
    app.chat_input[0].set_value("What was 3M's capital expenditure in 2018?").run()
    app.feedback[0].set_value(0).run()

    assert not app.exception
    assert not [b for b in app.button if b.label == "Try another answer"]


FOUND = {
    "search_id": "s1",
    "filings": ["3M_2018_10K"],
    "results": [
        {
            "position": n,
            "label": f"3M, Form 10-K for fiscal 2018, PDF page {n + 2}",
            "doc_name": "3M_2018_10K",
            "page": n + 1,
            "section": "Item 7",
            "text": f"Passage {n}.",
        }
        for n in range(2)
    ],
}


def search_script() -> None:
    from copilot.ui.app import search_page

    search_page()


def test_the_search_page_lists_passages_and_counts_a_page_opened(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clicks: list[tuple[str, int]] = []

    def click(self: CopilotClient, search_id: str, position: int) -> bool:
        clicks.append((search_id, position))
        return True

    def source(self: CopilotClient, doc_name: str, page: int) -> dict[str, Any]:
        return {"text": "The whole page."}

    monkeypatch.setattr(CopilotClient, "search", lambda self, query: FOUND)
    monkeypatch.setattr(CopilotClient, "click", click)
    monkeypatch.setattr(CopilotClient, "source", source)

    app = AppTest.from_function(search_script, default_timeout=60).run()
    app.text_input(key="search_query").set_value("3M capex").run()

    assert not app.exception
    assert any("never your words" in caption.value for caption in app.caption)
    assert [text.value for text in app.text][:2] == ["Passage 0.", "Passage 1."]
    app.toggle(key="read-s1-1").set_value(True).run()
    app.toggle(key="read-s1-1").set_value(False).run()
    app.toggle(key="read-s1-1").set_value(True).run()

    assert clicks == [("s1", 1)]  # opened twice, counted once
    assert "The whole page." in [text.value for text in app.text]
