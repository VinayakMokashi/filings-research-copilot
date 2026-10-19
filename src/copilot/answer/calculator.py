"""The calculator the answer model uses instead of doing arithmetic itself (step 3.5).

Language models are unreliable at arithmetic: a ratio of two seven-digit figures or a
three-year average is easy to get slightly wrong, and a slightly wrong number in a
financial answer is a wrong answer. So the model writes the expression ("1577 / 32765 *
100") and this module computes it. Expressions are parsed with `ast` by the same evaluator
the facts database uses (`copilot.facts.formula`): only numbers, `+ - * /`, parentheses and
signs are allowed, nothing is executed, and division by zero is an error rather than an
infinity.

Models write numbers the way filings print them, so thousands separators, currency signs
and a trailing percent sign on a number are cleaned up first.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from copilot.facts.formula import FormulaError, evaluate

_THOUSANDS = re.compile(r"(?<=\d),(?=\d{3}(?!\d))")
_CURRENCY = re.compile(r"[$\N{EURO SIGN}\N{POUND SIGN}]")
_PERCENT = re.compile(r"(?<![\d.])(\d+(?:\.\d+)?)\s*%")


class CalculationError(ValueError):
    """The expression isn't plain arithmetic, or it divides by zero."""


def clean(expression: str) -> str:
    """The expression with separators, currency signs and percent signs made arithmetic."""
    text = _THOUSANDS.sub("", expression)
    text = _CURRENCY.sub("", text)
    return _PERCENT.sub(r"(\1 / 100)", text)


def _no_lookups(metric: str, year: int) -> float:
    raise FormulaError(f"Only numbers are allowed, not {metric}[{year}].")


def calculate(expression: str) -> float:
    try:
        return evaluate(clean(expression), _no_lookups)
    except FormulaError as exc:
        raise CalculationError(str(exc)) from exc


@dataclass(frozen=True, slots=True)
class Calculation:
    """One expression the model asked for, and its result or the reason it failed."""

    id: str
    expression: str
    decimals: int = 2
    value: float | None = None
    error: str | None = None

    @property
    def text(self) -> str:
        """The result as it appears in the answer."""
        if self.value is None:
            return "[calculation failed]"
        return f"{self.value:,.{max(0, min(self.decimals, 6))}f}"


def run(calculation_id: str, expression: str, decimals: int = 2) -> Calculation:
    try:
        value = calculate(expression)
    except CalculationError as exc:
        return Calculation(calculation_id, expression, decimals, error=str(exc))
    return Calculation(calculation_id, expression, decimals, value=value)
