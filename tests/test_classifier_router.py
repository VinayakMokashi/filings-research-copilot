"""The classifier router: probabilities, the chosen route and the model's labels."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pytest
from numpy.typing import NDArray

from copilot.agents.classifier import ClassifierRouter, read_labels, softmax
from copilot.agents.router import ROUTES


def test_softmax_rows_are_probabilities() -> None:
    probabilities = softmax(np.array([[1.0, 2.0, 3.0], [0.0, 0.0, 0.0]], dtype=np.float32))

    assert probabilities.sum(axis=1) == pytest.approx([1.0, 1.0])
    assert probabilities[0].argmax() == 2
    assert probabilities[1] == pytest.approx([1 / 3] * 3)


def test_the_most_probable_route_wins_with_its_probability_as_confidence() -> None:
    asked: list[str] = []

    def scorer(questions: Sequence[str]) -> NDArray[np.float32]:
        asked.extend(questions)
        return np.array([[0.0, 4.0, 1.0, 0.0, 0.0, 0.0]], dtype=np.float32)

    decision = ClassifierRouter(scorer, list(ROUTES), model="router-v1").route("3M's capex?")

    assert asked == ["3M's capex?"]
    assert (decision.route, decision.router, decision.model) == ("data", "classifier", "router-v1")
    assert decision.confidence == pytest.approx(float(softmax(scorer(["x"]))[0][1]))
    assert sum(decision.scores.values()) == pytest.approx(1.0, abs=1e-3)
    assert (decision.cost_usd, decision.prompt_tokens, decision.error) == (0.0, 0, None)


def test_labels_come_from_the_model_config_in_output_order(tmp_path: Path) -> None:
    order = ["smalltalk", "doc", "data", "decline", "brief", "hybrid"]
    config = {"id2label": {str(i): label for i, label in enumerate(order)}}
    (tmp_path / "config.json").write_text(json.dumps(config), encoding="utf-8")

    assert read_labels(tmp_path) == order
    config["id2label"]["0"] = "weather"
    (tmp_path / "config.json").write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(ValueError, match="weather"):
        read_labels(tmp_path)
