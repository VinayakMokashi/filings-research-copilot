from __future__ import annotations

import pytest

from copilot.llm.reasoning import split_reasoning


@pytest.mark.parametrize(
    ("raw", "answer", "reasoning"),
    [
        pytest.param("Paris", "Paris", None, id="plain-answer"),
        pytest.param(
            "<think>step 1</think>\n\nSELECT 1", "SELECT 1", "step 1", id="complete-block"
        ),
        pytest.param("<Think>Mixed case</Think>ok", "ok", "Mixed case", id="case-insensitive"),
        pytest.param(
            "draft SELECT 2</think>SELECT 1", "SELECT 1", "draft SELECT 2", id="opens-mid-block"
        ),
        pytest.param("SELECT 1<think>still reasoning", "SELECT 1", "still reasoning", id="cut-off"),
        pytest.param("<think>only thinking</think>", "", "only thinking", id="no-answer"),
        pytest.param("<think></think>answer", "answer", None, id="empty-block"),
        pytest.param("<think>a</think>x<think>b</think>", "x", "a\n\nb", id="two-blocks"),
    ],
)
def test_split_reasoning(raw: str, answer: str, reasoning: str | None) -> None:
    assert split_reasoning(raw) == (answer, reasoning)
