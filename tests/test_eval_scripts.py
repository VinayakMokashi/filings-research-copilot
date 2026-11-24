"""The answer and scoring scripts open FinanceBench's test split only when asked (ADR-0006)."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

from copilot.config import Settings

SCRIPTS = ("run_copilot", "answer_questions", "judge_answers", "check_faithfulness")


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
