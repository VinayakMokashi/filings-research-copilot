"""A safe evaluator for small formulas over metric values.

Formulas look like `revenue[2019] / ((property_plant_equipment_net[2018] +
property_plant_equipment_net[2019]) / 2)`. Only numbers, `+ - * /`, parentheses, unary
signs and `metric[year]` lookups are allowed. The formula is parsed with `ast` and walked
node by node; it is never executed, so nothing else can run.
"""

from __future__ import annotations

import ast
from collections.abc import Callable

Lookup = Callable[[str, int], float]


class FormulaError(ValueError):
    """The formula uses something other than arithmetic and metric lookups, or divides by 0."""


def evaluate(formula: str, lookup: Lookup) -> float:
    try:
        tree = ast.parse(formula, mode="eval")
    except SyntaxError as exc:
        raise FormulaError(f"Not a valid formula: {formula!r}") from exc
    return _evaluate(tree.body, lookup)


def lookups(formula: str) -> list[tuple[str, int]]:
    """The `(metric, year)` pairs a formula reads, in order of appearance."""
    found: list[tuple[str, int]] = []

    def record(metric: str, year: int) -> float:
        found.append((metric, year))
        return 1.0

    evaluate(formula, record)
    return found


def _evaluate(node: ast.expr, lookup: Lookup) -> float:
    match node:
        case ast.Constant(value=bool()):
            raise FormulaError("Booleans are not numbers here.")
        case ast.Constant(value=int() | float() as number):
            return float(number)
        case ast.UnaryOp(op=ast.USub(), operand=operand):
            return -_evaluate(operand, lookup)
        case ast.UnaryOp(op=ast.UAdd(), operand=operand):
            return _evaluate(operand, lookup)
        case ast.BinOp(left=left, op=op, right=right):
            a, b = _evaluate(left, lookup), _evaluate(right, lookup)
            match op:
                case ast.Add():
                    return a + b
                case ast.Sub():
                    return a - b
                case ast.Mult():
                    return a * b
                case ast.Div():
                    if b == 0:
                        raise FormulaError("Division by zero.")
                    return a / b
            raise FormulaError(f"Operator not allowed: {type(op).__name__}.")
        case ast.Subscript(value=ast.Name(id=metric), slice=ast.Constant(value=int() as year)):
            return lookup(metric, year)
    raise FormulaError(f"Not allowed in a formula: {ast.unparse(node)!r}.")
