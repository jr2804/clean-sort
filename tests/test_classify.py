"""Tests for top-level statement classification."""

from __future__ import annotations

import libcst as cst

from clean_sort import Config
from clean_sort.classify import (
    classify,
    is_module_docstring,
    primary_name,
    referenced_names,
)


def _body(src: str) -> list[cst.CSTNode]:
    return list(cst.parse_module(src).body)


def test_classify_imports() -> None:
    assert classify(_body("import os\n")[0], Config()) == "imports"
    assert classify(_body("from os import path\n")[0], Config()) == "imports"


def test_classify_module_constants() -> None:
    assert classify(_body("MAX_SIZE = 100\n")[0], Config()) == "module_constants"
    assert classify(_body("ALL_CAPS: int = 1\n")[0], Config()) == "module_constants"


def test_classify_dunder_exports() -> None:
    # __all__ classifies into the dedicated dunder_exports section by default.
    assert classify(_body('__all__ = ["MAX_SIZE"]\n')[0], Config()) == "dunder_exports"


def test_classify_dunder_not_in_exports_is_module_constant() -> None:
    # Dunders not listed in dunder_exports_names stay in module_constants.
    assert classify(_body('__version__ = "1.0.0"\n')[0], Config()) == "module_constants"


def test_classify_custom_dunder_exports_names() -> None:
    cfg = Config(dunder_exports_names=["__all__", "__version__"])
    assert classify(_body('__all__ = ["MAX_SIZE"]\n')[0], cfg) == "dunder_exports"
    assert classify(_body('__version__ = "1.0.0"\n')[0], cfg) == "dunder_exports"


def test_classify_non_constant_is_runtime_setup() -> None:
    # A non-constant assignment (lowercase/snake_case target) groups into
    # runtime_setup, not the unknown_section fallback.
    assert classify(_body("result = compute()\n")[0], Config()) == "runtime_setup"
    assert classify(_body("logger = get_logger(__name__)\n")[0], Config()) == "runtime_setup"


def test_classify_non_assignment_is_other() -> None:
    # Statements that are not imports/assignments/defs (e.g. a bare call) stay
    # in the unknown_section fallback and act as barriers.
    assert classify(_body("setup_registry()\n")[0], Config()) == "other"


def test_classify_enum() -> None:
    assert classify(_body("class Color(enum.Enum):\n    pass\n")[0], Config()) == "enums"
    assert classify(_body("class Flag(IntFlag):\n    pass\n")[0], Config()) == "enums"


def test_classify_dataclass() -> None:
    node = _body("@dataclass\nclass Pt:\n    x: int\n")[0]
    assert classify(node, Config()) == "dataclasses"


def test_classify_plain_class_and_function() -> None:
    assert classify(_body("class Foo:\n    pass\n")[0], Config()) == "classes"
    assert classify(_body("def foo():\n    pass\n")[0], Config()) == "functions"


def test_classify_main_block_and_type_checking() -> None:
    assert classify(_body('if __name__ == "__main__":\n    main()\n')[0], Config()) == "main_block"
    nodes = _body("if TYPE_CHECKING:\n    import os\n")
    assert classify(nodes[0], Config()) == "typing_imports"


def test_primary_name() -> None:
    assert primary_name(_body("def foo():\n    pass\n")[0]) == "foo"
    assert primary_name(_body("class Bar:\n    pass\n")[0]) == "Bar"
    assert primary_name(_body("import a.b.c\n")[0]) == "a.b.c"
    assert primary_name(_body("from x.y import z\n")[0]) == "x.y"
    assert primary_name(_body("MAX = 1\n")[0]) == "MAX"


def test_referenced_names() -> None:
    names = referenced_names(_body("def foo():\n    return bar() + baz\n")[0])
    assert {"bar", "baz"} <= names


def test_is_module_docstring() -> None:
    first = _body('"""doc"""\nimport os\n')[0]
    assert is_module_docstring(first)
    assert not is_module_docstring(_body("import os\n")[0])
