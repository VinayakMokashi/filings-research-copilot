"""The answer and scoring scripts open FinanceBench's test split only when asked (ADR-0006),
and the copilot's run answers as the API does only when asked."""

from __future__ import annotations

import importlib.util
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

from copilot.config import Settings
from copilot.eval.financebench import Question

SCRIPTS = ("run_copilot", "answer_questions", "judge_answers", "check_faithfulness")
RecordFactory = Callable[..., dict[str, Any]]
DOC_RESULT = {
    "kind": "doc",
    "answer": {
        "answerable": True,
        "text": "Capital expenditure was $1,577 million [1].",
        "missing": "",
        "error": None,
        "sources": [],
        "cited": [],
        "calculations": [],
    },
}


def script(name: str) -> ModuleType:
    path = Path(__file__).resolve().parents[1] / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("name", SCRIPTS)
def test_the_test_split_stays_closed_without_allow_test(
    name: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = script(name)
    settings = Settings(_env_file=None, data_dir=tmp_path)
    monkeypatch.setattr(module, "get_settings", lambda: settings)

    args = ["--run", "trial", "--split", "test", "--results-dir", str(tmp_path / "results")]

    assert module.main(args) == 2
    assert "held out" in capsys.readouterr().out
    assert not any(path.is_file() for path in tmp_path.rglob("*"))


@dataclass
class Parts:
    """Stands in for the graph's components; only `strict` matters here."""

    strict: bool = True


def run_copilot_with(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    question_record: RecordFactory,
    events: list[dict[str, Any]],
    values: dict[str, Any],
    *flags: str,
) -> tuple[int, list[bool], Path]:
    """Run scripts/run_copilot.py on one question with a stand-in graph that streams `events`
    and ends in `values`. Returns the exit code, the `strict` each copilot was built with,
    and the answers file."""
    module = script("run_copilot")
    settings = Settings(_env_file=None, data_dir=tmp_path)
    question = Question.model_validate(question_record(7))
    monkeypatch.setattr(module, "get_settings", lambda: settings)
    monkeypatch.setattr(module, "load_split", lambda *args, **kwargs: [question])
    monkeypatch.setattr(module, "build_components", lambda settings, batch: Parts())
    built: list[bool] = []

    class StandIn:
        def __init__(self, parts: Parts, trace: Any) -> None:
            built.append(parts.strict)
            self.graph = SimpleNamespace(
                get_state=lambda config: SimpleNamespace(values=values),
                get_state_history=lambda config: [],
            )

        def stream(self, question: str, thread_id: str) -> list[dict[str, Any]]:
            return events

    monkeypatch.setattr(module, "Copilot", StandIn)
    code = module.main(["--run", "trial", "--results-dir", str(tmp_path / "results"), *flags])
    return code, built, tmp_path / "processed" / "answers" / "trial" / "dev" / "answers.jsonl"


@pytest.mark.parametrize(("flags", "strict"), [((), True), (("--lenient",), False)])
def test_a_lenient_run_lets_an_unreadable_check_pass_as_the_api_does(
    flags: tuple[str, ...],
    strict: bool,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    question_record: RecordFactory,
) -> None:
    unreadable = {"checked": False, "error": "the checker's reply was unreadable"}
    events = [
        {"type": "start", "node": "validate"},
        {"type": "event", "node": "validate", "event": "unreadable"},
    ]
    values = {"route": "doc", "result": DOC_RESULT, "validation": unreadable}

    code, built, answers = run_copilot_with(
        tmp_path, monkeypatch, question_record, events, values, *flags
    )

    assert (code, built) == (0, [strict])
    assert json.loads(answers.read_text(encoding="utf-8"))["validation"] == unreadable


@pytest.mark.parametrize(
    ("events", "result"),
    [
        ([{"type": "event", "node": "revise", "event": "quota"}], DOC_RESULT),
        ([], {"kind": "data", "data": {"status": "ok", "rate_limited": True}}),
    ],
)
def test_a_lenient_run_stops_where_a_spent_quota_shaped_the_reply(
    events: list[dict[str, Any]],
    result: dict[str, Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    question_record: RecordFactory,
) -> None:
    values = {"route": result["kind"], "result": result}

    code, _, answers = run_copilot_with(
        tmp_path, monkeypatch, question_record, events, values, "--lenient"
    )

    assert code == 75
    assert answers.read_text(encoding="utf-8") == ""
