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

Models also build on their own results: a free cash flow conversion becomes `c1 = 7838 -
442`, then `c2 = c1 / 4756`. `run_all` evaluates a list of calculations in order, and an
expression may name an earlier calculation by its id; the name is replaced by that
calculation's value before evaluation.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, replace

from copilot.facts.formula import FormulaError, evaluate

_THOUSANDS = re.compile(r"(?<=\d),(?=\d{3}(?!\d))")
_CURRENCY = re.compile(r"[$\N{EURO SIGN}\N{POUND SIGN}]")
_PERCENT = re.compile(r"(?<![\d.])(\d+(?:\.\d+)?)\s*%")
_REFERENCE = re.compile(r"\b[cC](\d+)\b")


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


def run_all(requests: Sequence[tuple[str, str, int]]) -> list[Calculation]:
    """Each (id, expression, decimals) in order; an expression may use an earlier id."""
    values: dict[str, float] = {}
    results = []
    for calculation_id, expression, decimals in requests:
        names = [f"c{number}" for number in _REFERENCE.findall(expression)]
        unknown = [name for name in names if name not in values]
        if unknown:
            result = Calculation(
                calculation_id,
                expression,
                decimals,
                error=f"Uses {unknown[0]}, which has no value before this calculation.",
            )
        else:
            resolved = _REFERENCE.sub(lambda m: f"({values['c' + m.group(1)]!r})", expression)
            result = replace(run(calculation_id, resolved, decimals), expression=expression)
        if result.value is not None:
            values[calculation_id.lower()] = result.value
        results.append(result)
    return results
