"""CSV import + validation pipeline — realistic module for csort examples.

This file is intentionally out of order and contains *barriers* (module-level
runtime setup statements that csort will not move). Run::

    csort diff tests/data/csv_pipeline_unsorted.py
    csort run  tests/data/csv_pipeline_unsorted.py

Observe that ``_VALIDATORS`` and ``register_validator(...)`` stay in place
relative to each other because the call is a barrier.
"""

from __future__ import annotations

import csv
import enum
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

ALPHA_PATTERN = re.compile(r"^[A-Z_][A-Z0-9_]*$")

MIN_ROWS = 1
MAX_ROWS = 10_000
REQUIRED_COLUMNS = ("name", "email", "age")


class Severity(enum.Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class ValidationIssue:
    """A single validation finding for one row."""

    row: int
    column: str
    message: str
    severity: Severity = Severity.WARNING


@dataclass(frozen=True)
class CsvConfig:
    """Configuration for :func:`import_csv`."""

    delimiter: str = ","
    encoding: str = "utf-8"
    skip_header: bool = True


class ValidationError(Exception):
    """Raised when the CSV fails validation beyond ``MAX_ROWS`` issues."""

    def __init__(self, issues: list[ValidationIssue]) -> None:
        super().__init__(f"{len(issues)} validation issues")
        self.issues = issues


# --- runtime setup: a registry of validators ---------------------------------
# ``_VALIDATORS`` and the ``register_validator`` calls below form a *barrier
# group*: csort will not reorder ``_VALIDATORS`` past the calls that populate
# it, because the calls depend on it at import time.
_VALIDATORS: dict = {}


def register_validator(
    column: str,
) -> Callable[[Callable[[str], ValidationIssue | None]], Callable[[str], ValidationIssue | None]]:
    """Decorator: attach a validator function to *column*."""

    def decorator(
        fn: Callable[[str], ValidationIssue | None],
    ) -> Callable[[str], ValidationIssue | None]:
        _VALIDATORS[column] = fn
        return fn

    return decorator


@register_validator("email")
def _validate_email(value: str) -> ValidationIssue | None:
    if "@" not in value:
        return ValidationIssue(0, "email", "missing @", Severity.ERROR)
    return None


@register_validator("age")
def _validate_age(value: str) -> ValidationIssue | None:
    try:
        age = int(value)
    except ValueError:
        return ValidationIssue(0, "age", "not an integer", Severity.ERROR)
    if age < 0 or age > 150:
        return ValidationIssue(0, "age", "out of range", Severity.WARNING)
    return None


def validate_row(row_num: int, row: dict[str, str]) -> list[ValidationIssue]:
    """Run every registered validator against a single decoded *row*."""
    issues: list[ValidationIssue] = []
    for column, fn in _VALIDATORS.items():
        result = fn(row.get(column, ""))
        if result is not None:
            issues.append(ValidationIssue(row_num, column, result.message, result.severity))
    return issues


def read_rows(path: Path, config: CsvConfig) -> list[dict[str, str]]:
    """Low-level reader: decode *path* into a list of row dicts."""
    with path.open(encoding=config.encoding, newline="") as fh:
        reader = csv.DictReader(fh, delimiter=config.delimiter)
        return list(reader)


def import_csv(path: Path, config: CsvConfig | None = None) -> list[ValidationIssue]:
    """Top-level orchestrator: read, validate, and collect issues.

    Returns the list of :class:`ValidationIssue` objects; raises
    :class:`ValidationError` if there are more than ``MAX_ROWS`` issues.
    """
    cfg = config or CsvConfig()
    rows = read_rows(path, cfg)
    if len(rows) < MIN_ROWS:
        return [ValidationIssue(0, "", "file is empty", Severity.ERROR)]

    issues: list[ValidationIssue] = []
    for index, row in enumerate(rows, start=1):
        issues.extend(validate_row(index, row))
        if len(issues) > MAX_ROWS:
            raise ValidationError(issues)
    return issues


def main() -> int:
    """CLI entry point: print a summary of validation issues."""
    issues = import_csv(Path("data.csv"))
    for issue in issues:
        print(f"row {issue.row} [{issue.severity.value}] {issue.column}: {issue.message}")
    return 1 if any(i.severity == Severity.ERROR for i in issues) else 0


if TYPE_CHECKING:
    import io  # noqa: F401


if __name__ == "__main__":
    raise SystemExit(main())
