"""Cross-checks of annual values against FinanceBench's gold answers (dev questions only).

Each check is a FinanceBench dev question rewritten as a formula over canonical metrics:
a question asking for 3M's fiscal 2018 capital expenditure in USD millions becomes
`capital_expenditure[2018] / 1e6`. A check agrees when the computed value, rounded to the
precision the question asks for ("Answer in USD millions" means whole millions), equals
the gold answer.
"""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from copilot.facts.formula import FormulaError, Lookup, evaluate

CHECKS_FILE = Path("data/reference/financebench_xbrl_checks.json")

_NUMBER = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


class Check(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    company: str
    formula: str
    decimals: int = Field(ge=0)
    note: str | None = None


@dataclass(frozen=True, slots=True)
class CheckResult:
    id: str
    company: str
    formula: str
    expected: float
    decimals: int
    computed: float | None
    agrees: bool
    detail: str


def load_checks(path: Path = CHECKS_FILE) -> list[Check]:
    return TypeAdapter(list[Check]).validate_json(path.read_bytes())


def parse_answer(answer: str) -> float:
    """The first number in a gold answer, such as 1577.0 from "$1577.00"."""
    match = _NUMBER.search(answer)
    if match is None:
        raise ValueError(f"No number in the answer {answer!r}.")
    return float(match.group().replace(",", ""))


def agrees(computed: float, expected: float, decimals: int) -> bool:
    """True when `computed`, rounded to `decimals` places, equals the gold answer."""
    return abs(round(computed, decimals) - expected) < 1e-9


def run_checks(
    conn: sqlite3.Connection,
    checks: Sequence[Check],
    answers: Mapping[str, str],
    cik_by_company: Mapping[str, int],
) -> list[CheckResult]:
    results = []
    for check in checks:
        if check.id not in answers:
            raise KeyError(f"{check.id} is not a dev question; checks may only use dev answers.")
        expected, decimals = parse_answer(answers[check.id]), check.decimals
        used: list[str] = []
        try:
            computed = evaluate(check.formula, _lookup(conn, cik_by_company[check.company], used))
        except (LookupError, FormulaError) as exc:
            results.append(
                CheckResult(
                    check.id,
                    check.company,
                    check.formula,
                    expected,
                    decimals,
                    None,
                    False,
                    str(exc),
                )
            )
            continue
        results.append(
            CheckResult(
                check.id,
                check.company,
                check.formula,
                expected,
                decimals,
                computed,
                agrees(computed, expected, decimals),
                ", ".join(dict.fromkeys(used)),
            )
        )
    return results


def _lookup(conn: sqlite3.Connection, cik: int, used: list[str]) -> Lookup:
    def lookup(metric: str, year: int) -> float:
        row = conn.execute(
            "SELECT value, tag FROM annual_values WHERE cik = ? AND metric = ? AND fiscal_year = ?",
            (cik, metric, year),
        ).fetchone()
        if row is None:
            raise LookupError(f"no {metric} for FY{year}")
        used.append(f"{metric}: {row[1]}")
        return float(row[0])

    return lookup


def render_report(results: Sequence[CheckResult]) -> str:
    agreed = sum(result.agrees for result in results)
    lines = [
        "# Facts database against FinanceBench dev answers",
        "",
        f"{agreed} of {len(results)} checks agree. A check agrees when the computed value, "
        "rounded to the precision the question asks for, equals the gold answer.",
        "",
        "| Question | Company | Formula | Gold | Computed | Agrees | Tags used or problem |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in results:
        computed = "none" if r.computed is None else f"{r.computed:.{r.decimals}f}"
        mark = "yes" if r.agrees else "**no**"
        lines.append(
            f"| {r.id.removeprefix('financebench_id_')} | {r.company} | `{r.formula}` | "
            f"{r.expected:.{r.decimals}f} | {computed} | {mark} | {r.detail} |"
        )
    return "\n".join(lines) + "\n"
