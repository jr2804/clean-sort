"""Tests for the sort pipeline: section ordering, strategies, class methods."""

from __future__ import annotations

import libcst as cst

from clean_sort import Config, sort_source, would_change

KEEP = Config()  # within-section order preserved by default


def sort(src: str, **kwargs) -> str:
    return sort_source(src, Config(**kwargs))


# --------------------------------------------------------------- structural
def test_section_ordering_imports_before_functions() -> None:
    out = sort_source("def f():\n    pass\nimport os\n", KEEP)
    assert out.index("import os") < out.index("def f")


def test_module_constants_before_classes() -> None:
    out = sort_source("class C:\n    pass\nMAX = 1\n", KEEP)
    assert out.index("MAX = 1") < out.index("class C")


def test_typing_imports_before_classes() -> None:
    src = "class C:\n    pass\nif TYPE_CHECKING:\n    import os\n"
    out = sort_source(src, KEEP)
    assert out.index("TYPE_CHECKING") < out.index("class C")


def test_main_block_after_functions() -> None:
    src = 'if __name__ == "__main__":\n    run()\ndef run():\n    pass\n'
    out = sort_source(src, KEEP)
    assert out.index("def run") < out.index("if __name__")


def test_enum_before_plain_classes() -> None:
    src = "class Plain:\n    pass\nclass Color(enum.Enum):\n    pass\n"
    out = sort_source(src, KEEP)
    assert out.index("class Color") < out.index("class Plain")


def test_docstring_pinned() -> None:
    out = sort('"""mod"""\ndef b():\n    pass\ndef a():\n    pass\n', strategies={"functions": "alpha"})
    assert out.startswith('"""mod"""')
    assert out.index("def a") < out.index("def b")


def test_imports_default_keep_order() -> None:
    out = sort_source("import zeta\nimport alpha\n", KEEP)
    assert out.index("import zeta") < out.index("import alpha")


def test_barrier_setup_not_moved() -> None:
    # `app = make_app()` is unrecognised -> a barrier that stays put, so the
    # function decorated with it is never moved above it.
    src = "app = make_app()\n@app.cmd\ndef run():\n    return 1\n"
    out = sort_source(src, Config(strategies={"functions": "alpha"}))
    assert out.index("app = make_app") < out.index("def run")


def test_recognized_not_crossing_barrier() -> None:
    # two function runs separated by a barrier stay separated; alpha does not
    # pull `a` across the barrier to join `b`.
    src = "def b():\n    pass\nbarrier = make()\ndef a():\n    pass\n"
    out = sort_source(src, Config(strategies={"functions": "alpha"}))
    assert out.index("def b") < out.index("barrier = make")
    assert out.index("barrier = make") < out.index("def a")


def test_future_import_pinned_first() -> None:
    src = '"""doc"""\nimport os\nfrom __future__ import annotations\n'
    out = sort_source(src, Config(strategies={"imports": "alpha"}))
    assert out.startswith('"""doc"""')
    assert out.index("__future__") < out.index("import os")


# ------------------------------------------------------------------ strategies
def test_alpha_functions() -> None:
    out = sort("def b():\n    pass\ndef a():\n    pass\n", strategies={"functions": "alpha"})
    assert out.index("def a") < out.index("def b")


def test_stepdown_caller_first() -> None:
    out = sort(
        "def low():\n    return 1\ndef high():\n    return low()\n",
        strategies={"functions": "stepdown"},
    )
    assert out.index("def high") < out.index("def low")


def test_abstraction_callee_first() -> None:
    out = sort(
        "def low():\n    return 1\ndef high():\n    return low()\n",
        strategies={"functions": "abstraction"},
    )
    assert out.index("def low") < out.index("def high")


def test_dependency_cycle_keeps_order() -> None:
    out = sort(
        "def a():\n    b()\ndef b():\n    a()\n",
        strategies={"functions": "stepdown"},
    )
    assert out.index("def a") < out.index("def b")


def test_stepdown_falls_back_to_alpha_off_functions() -> None:
    # stepdown on a non-functions section is not a dependency sort.
    out = sort("B = 2\nA = 1\n", strategies={"module_constants": "stepdown"})
    assert out.index("A = 1") < out.index("B = 2")


# --------------------------------------------------------------- class methods
def test_class_methods_visibility_order() -> None:
    src = "class C:\n    def _prot(self):\n        pass\n    def pub(self):\n        pass\n"
    out = sort_source(src, KEEP)
    assert out.index("def pub") < out.index("def _prot")


def test_class_methods_disabled_keeps_order() -> None:
    src = "class C:\n    def _prot(self):\n        pass\n    def pub(self):\n        pass\n"
    out = sort_source(src, Config(class_methods_enabled=False))
    assert out.index("def _prot") < out.index("def pub")


def test_method_type_ordering() -> None:
    src = "class C:\n    @staticmethod\n    def s():\n        pass\n    def i(self):\n        pass\n"
    out = sort_source(src, KEEP)
    assert out.index("def i") < out.index("def s")


# ----------------------------------------------------------------- directives
def test_file_disable_directive() -> None:
    src = "# csort: off\ndef b():\n    pass\ndef a():\n    pass\n"
    assert sort_source(src, Config(strategies={"functions": "alpha"})) == src


def test_class_disable_trailing_comment() -> None:
    src = "class C:  # csort: off\n    def _prot(self):\n        pass\n    def pub(self):\n        pass\n"
    out = sort_source(src, KEEP)
    assert out.index("def _prot") < out.index("def pub")


# ------------------------------------------------------------------- invariants
def test_idempotent() -> None:
    src = '"""doc"""\nimport os\nMAX = 1\ndef a():\n    return b()\ndef b():\n    return 1\n'
    once = sort_source(src, Config(strategies={"functions": "stepdown"}))
    assert sort_source(once, Config(strategies={"functions": "stepdown"})) == once


def test_roundtrip_reparses() -> None:
    src = "import os\n\nclass C:\n    def _z(self):\n        pass\n    def a(self):\n        pass\n\nMAX = 1\n"
    cst.parse_module(sort_source(src, KEEP))


def test_would_change() -> None:
    unsorted = "def b():\n    pass\ndef a():\n    pass\n"
    assert would_change(unsorted, Config(strategies={"functions": "alpha"})) is True
    assert would_change("import os\n", KEEP) is False


def test_empty_and_single_statement_unchanged() -> None:
    assert sort_source("", KEEP) == ""
    assert sort_source("import os\n", KEEP) == "import os\n"


# --------------------------------------------- section restriction (--section-only)
def test_restricted_sections_reorder_only_those() -> None:
    # `sections=["functions"]` means only the functions bucket may move; an
    # import is excluded from reordering and stays put as a barrier.
    src = "def b():\n    pass\ndef a():\n    pass\nimport os\n"
    cfg = Config(sections=["functions"], strategies={"functions": "alpha"})
    out = sort_source(src, cfg)
    assert out.index("def a") < out.index("def b")
    assert out.index("import os") > out.index("def b")


def test_restricted_sections_keep_order_of_excluded() -> None:
    # With `functions` excluded, they keep their original order while the
    # allowed bucket (imports) still hoists to the top.
    src = "def b():\n    pass\ndef a():\n    pass\nimport os\n"
    out = sort_source(src, Config(sections=["imports"]))
    assert out.index("def b") < out.index("def a")
    assert out.index("import os") > out.index("def a")


def test_restricted_sections_multi_reorder_independently() -> None:
    # Each allowed bucket reorders within itself (imports alpha, functions alpha).
    src = "def b():\n    pass\ndef a():\n    pass\nimport zeta\nimport alpha\n"
    cfg = Config(
        sections=["imports", "functions"],
        strategies={"functions": "alpha", "imports": "alpha"},
    )
    out = sort_source(src, cfg)
    assert out.index("import alpha") < out.index("import zeta")
    assert out.index("def a") < out.index("def b")


# ------------------------------------------- strategy overrides (--strategy-overrides)
def test_strategy_override_reorders_previously_kept() -> None:
    # Without an override functions keep order; the override (functions=alpha)
    # is exactly what `--strategy-overrides functions=alpha` injects into the config.
    src = "def b():\n    pass\ndef a():\n    pass\n"
    kept = sort_source(src, Config())
    assert kept.index("def b") < kept.index("def a")
    overridden = sort_source(src, Config(strategies={"functions": "alpha"}))
    assert overridden.index("def a") < overridden.index("def b")
