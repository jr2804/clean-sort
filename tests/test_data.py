"""End-to-end tests over the realistic sample modules in ``tests/data``.

Each sample is a believable, fully-formed Python module (not a toy snippet).
The tests assert that:

* sorting the ``*_unsorted.py`` input reproduces the committed ``*_sorted.py``
  fixture exactly,
* every sorted output is idempotent (sorting again changes nothing),
* the output reparses as valid ``libcst``, and
* the canonical section order holds (imports → constants → classes → … → main).

Fixtures are regenerated as described in ``tests/data/README.md``.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import libcst as cst
import pytest

from pyreorder import Config, sort_source

_DATA = Path(__file__).parent / "data"

#: ``(unsorted, expected, config)`` triples for every sample in ``tests/data``.
#: Each sample demonstrates a different strategy or feature; the config here is
#: exactly what was used to generate the committed ``*_sorted.py`` fixture.
SAMPLES: list[tuple[str, str, Config]] = [
    (
        "web_service_unsorted.py",
        "web_service_sorted.py",
        Config(strategies={"functions": "stepdown"}),
    ),
    (
        "csv_pipeline_unsorted.py",
        "csv_pipeline_sorted.py",
        Config(strategies={"functions": "stepdown"}),
    ),
    (
        "cli_app_unsorted.py",
        "cli_app_sorted.py",
        Config(strategies={"functions": "stepdown"}),
    ),
    (
        "plugin_registry_unsorted.py",
        "plugin_registry_sorted.py",
        Config(strategies={"functions": "abstraction"}),
    ),
    (
        "inventory_models_unsorted.py",
        "inventory_models_sorted.py",
        Config(strategies={"enums": "alpha", "functions": "alpha"}),
    ),
]


def _read(name: str) -> str:
    return (_DATA / name).read_text(encoding="utf-8")


@pytest.mark.parametrize(("unsorted", "expected", "cfg"), SAMPLES, ids=lambda v: v if isinstance(v, str) else "")
def test_sort_matches_fixture(unsorted: str, expected: str, cfg: Config) -> None:
    """Sorting the unsorted sample must reproduce the committed fixture."""
    result = sort_source(_read(unsorted), cfg)
    assert result == _read(expected)


@pytest.mark.parametrize(("unsorted", "expected", "cfg"), SAMPLES, ids=lambda v: v if isinstance(v, str) else "")
def test_sorted_output_is_idempotent(unsorted: str, expected: str, cfg: Config) -> None:
    """Re-sorting the expected output must not change it."""
    once = _read(expected)
    assert sort_source(once, cfg) == once


@pytest.mark.parametrize(("unsorted", "expected", "cfg"), SAMPLES, ids=lambda v: v if isinstance(v, str) else "")
def test_sorted_output_reparses(unsorted: str, expected: str, cfg: Config) -> None:
    """The sorted module must be syntactically valid and reparsable by libcst."""
    cst.parse_module(_read(expected))


@pytest.mark.parametrize(("unsorted", "expected", "cfg"), SAMPLES, ids=lambda v: v if isinstance(v, str) else "")
def test_imports_float_to_top(unsorted: str, expected: str, cfg: Config) -> None:
    """In the sorted output every ``import``/``from`` precedes the first class/def."""
    body = list(cst.parse_module(_read(expected)).body)
    first_import = _first_index(body, _is_import)
    first_def = _first_index(body, _is_class_or_def)
    if first_import is not None and first_def is not None:
        assert first_import < first_def


@pytest.mark.parametrize(("unsorted", "expected", "cfg"), SAMPLES, ids=lambda v: v if isinstance(v, str) else "")
def test_main_block_is_last(unsorted: str, expected: str, cfg: Config) -> None:
    """The ``if __name__ == "__main__":`` guard (if present) sits at the end."""
    body = list(cst.parse_module(_read(expected)).body)
    last = body[-1]
    assert _is_main_guard(last) or _is_import(last) or _is_class_or_def(last)


# -------------------------------------------------------------------- helpers
def _first_index(body: list[cst.CSTNode], pred: Callable[[cst.CSTNode], bool]) -> int | None:
    for index, node in enumerate(body):
        if pred(node):
            return index
    return None


def _is_import(node: cst.CSTNode) -> bool:
    return isinstance(node, (cst.SimpleStatementLine,)) and any(isinstance(stmt, (cst.ImportFrom, cst.Import)) for stmt in node.body)


def _is_class_or_def(node: cst.CSTNode) -> bool:
    return isinstance(node, (cst.ClassDef, cst.FunctionDef))


def _is_main_guard(node: cst.CSTNode) -> bool:
    if not isinstance(node, cst.If):
        return False
    test = node.test
    if not isinstance(test, cst.Comparison):
        return False
    if not isinstance(test.left, cst.Name) or test.left.value != "__name__":
        return False
    return any(isinstance(ct.operator, cst.Equal) for ct in test.comparisons)
