"""The answer model's calculator: plain arithmetic only, numbers as filings print them."""

from __future__ import annotations

import pytest

from copilot.answer import calculator


@pytest.mark.parametrize(
    ("expression", "value"),
    [
        ("1577 / 32765 * 100", 1577 / 32765 * 100),
        ("(1,577 + 1,373) / 2", 1475.0),
        ("$2,000 - $500", 1500.0),
        ("12% * 400", 48.0),
        ("-(3 - 5)", 2.0),
    ],
)
def test_arithmetic_with_filing_style_numbers(expression: str, value: float) -> None:
    assert calculator.calculate(expression) == pytest.approx(value)


@pytest.mark.parametrize(
    "expression", ["__import__('os')", "revenue[2019] / 2", "1 / 0", "2 ** 1000", "abs(-3)"]
)
def test_anything_but_arithmetic_is_refused(expression: str) -> None:
    with pytest.raises(calculator.CalculationError):
        calculator.calculate(expression)


def test_run_keeps_the_error_and_formats_the_result() -> None:
    good = calculator.run("c1", "1577 / 32765 * 100", decimals=1)
    bad = calculator.run("c2", "1 / 0")

    assert (good.value is not None, good.text) == (True, "4.8")
    assert calculator.run("c3", "1234567.891", decimals=0).text == "1,234,568"
    assert (bad.value, bad.text) == (None, "[calculation failed]")
    assert bad.error is not None
