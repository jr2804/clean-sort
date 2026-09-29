"""Tests for the sort pipeline: section ordering, strategies, class methods."""

from __future__ import annotations

import textwrap

import libcst as cst

from pyreorder import Config, sort_source, would_change

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


def test_dunder_exports_after_functions() -> None:
    # __all__ moves to the dunder_exports section, after functions and
    # before the main guard.
    src = '"""doc"""\nimport os\n\n__all__ = ["main"]\n\n\ndef main():\n    pass\n'
    out = sort_source(src, KEEP)
    assert out.index("def main") < out.index("__all__")


def test_dunder_exports_before_main_block() -> None:
    src = 'if __name__ == "__main__":\n    main()\n\n__all__ = ["main"]\n\n\ndef main():\n    pass\n'
    out = sort_source(src, KEEP)
    assert out.index("__all__") < out.index("if __name__")
    assert out.index("def main") < out.index("__all__")


def test_dunder_exports_moves_from_top() -> None:
    # Previously __all__ was hoisted to module_constants (top); now it sinks
    # to the bottom, next to the main guard.
    src = '"""doc"""\nimport sys\n\n__all__ = ["main"]\n\nMAX_SIZE = 10\n\n\ndef main():\n    pass\n'
    out = sort_source(src, KEEP)
    assert out.index("import sys") < out.index("MAX_SIZE")
    assert out.index("MAX_SIZE") < out.index("def main")
    assert out.index("def main") < out.index("__all__")


def test_dunder_exports_idempotent() -> None:
    src = '"""doc"""\nimport sys\n\n__all__ = ["main"]\n\nMAX_SIZE = 10\n\n\ndef main():\n    pass\n'
    once = sort_source(src, KEEP)
    twice = sort_source(once, KEEP)
    assert once == twice


def test_non_export_dunder_stays_module_constants() -> None:
    # __version__ is not in the default exports list, so it stays in
    # module_constants at the top.
    src = '"""doc"""\nimport sys\n\n__version__ = "1.0.0"\n\n\ndef main():\n    pass\n'
    out = sort_source(src, KEEP)
    assert out.index("__version__") < out.index("def main")


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
    # pull `a` across the barrier to join `b`. A bare call is a genuine barrier
    # (unrecognised statement), unlike a non-constant assignment (runtime_setup).
    src = "def b():\n    pass\nsetup_registry()\ndef a():\n    pass\n"
    out = sort_source(src, Config(strategies={"functions": "alpha"}))
    assert out.index("def b") < out.index("setup_registry")
    assert out.index("setup_registry") < out.index("def a")


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
    src = "# preorder: off\ndef b():\n    pass\ndef a():\n    pass\n"
    assert sort_source(src, Config(strategies={"functions": "alpha"})) == src


def test_class_disable_trailing_comment() -> None:
    src = "class C:  # preorder: off\n    def _prot(self):\n        pass\n    def pub(self):\n        pass\n"
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


# --------------------------------------------- forward-reference barriers
# A module-level constant whose RHS references a name defined in a later
# section must be treated as a barrier (left in place) to prevent NameError.


def test_constant_referencing_enum_stays_in_place() -> None:
    # Case 1 from issue #1: _DEFAULT_COLOR = Color.RED must stay after Color.
    src = textwrap.dedent("""\
        from enum import StrEnum
        class Color(StrEnum):
            RED = "red"
        _DEFAULT_COLOR = Color.RED
    """)
    out = sort_source(src, Config())
    assert out.index("class Color") < out.index("_DEFAULT_COLOR")


def test_constant_referencing_class_stays_in_place() -> None:
    # _ASSET_PREFIX = {AssetKind.TABLE: ...} must stay after AssetKind.
    src = textwrap.dedent("""\
        from enum import StrEnum
        class AssetKind(StrEnum):
            TABLE = "table"
        _ASSET_PREFIX = {AssetKind.TABLE: "prefix"}
    """)
    out = sort_source(src, Config())
    assert out.index("class AssetKind") < out.index("_ASSET_PREFIX")


def test_constant_referencing_function_stays_in_place() -> None:
    # _REGISTRY = {"a": _helper_a} must stay after _helper_a.
    src = textwrap.dedent("""\
        def _helper_a():
            pass
        _REGISTRY = {"a": _helper_a}
    """)
    out = sort_source(src, Config(strategies={"functions": "stepdown"}))
    assert out.index("def _helper_a") < out.index("_REGISTRY")


def test_constant_referencing_imported_name_moves_normally() -> None:
    # _OS_PATH = os.path must still be classified as module_constants
    # (no false positive — os is imported, not forward-defined).
    src = textwrap.dedent("""\
        import os
        _OS_PATH = os.path
    """)
    out = sort_source(src, Config())
    # _OS_PATH stays in module_constants (after imports), not a barrier.
    assert "_OS_PATH" in out
    assert "import os" in out


def test_constant_referencing_builtin_moves_normally() -> None:
    # _MAX = max(1, 2) must still hoist (no false positive).
    src = "_MAX = max(1, 2)\n"
    out = sort_source(src, Config())
    assert "_MAX" in out


def test_safe_constants_still_group() -> None:
    # Unrelated constants still group into module_constants and reorder
    # within the section (alpha order when configured).
    src = textwrap.dedent("""\
        def f():
            pass
        _B = 2
        _A = 1
    """)
    out = sort_source(src, Config(strategies={"module_constants": "alpha"}))
    assert out.index("_A") < out.index("_B")
    assert out.index("_B") < out.index("def f")


def test_annotation_only_ref_with_future_annotations_not_barrier() -> None:
    # With ``from __future__ import annotations``, annotation-only references
    # are not evaluated at runtime and must not trigger the barrier.
    src = textwrap.dedent("""\
        from __future__ import annotations
        from typing import Callable
        class Later:
            pass
        _REG: Callable[[Later], None] = lambda x: None
    """)
    out = sort_source(src, Config())
    # _REG should be in module_constants (before Later), not a barrier.
    assert out.index("_REG") < out.index("class Later")


def test_forward_reference_barrier_is_idempotent() -> None:
    # Re-sorting the fixed output changes nothing.
    src = textwrap.dedent("""\
        from enum import StrEnum
        class Color(StrEnum):
            RED = "red"
        _DEFAULT_COLOR = Color.RED
    """)
    once = sort_source(src, Config())
    twice = sort_source(once, Config())
    assert once == twice


# ------------------------------------------------- runtime_setup section
# Module-level non-constant assignments (logger, app, client, ...) group into
# the ``runtime_setup`` section instead of acting as barriers.


def test_runtime_setup_after_imports_and_constants() -> None:
    # logger = ... lands in runtime_setup, ordered after imports/constants.
    src = textwrap.dedent("""\
        import os
        logger = get_logger(__name__)
        MAX_CONN = 10
        def handler():
            pass
    """)
    out = sort_source(src, Config())
    assert out.index("import os") < out.index("MAX_CONN")
    assert out.index("MAX_CONN") < out.index("logger =")
    assert out.index("logger =") < out.index("def handler")


def test_reexport_import_hoists_above_runtime_setup() -> None:
    # An import below a runtime_setup statement must migrate up to the imports
    # block (the barrier no longer blocks it).
    src = textwrap.dedent("""\
        from knox.logging import get_logger

        logger = get_logger(__name__)

        from knox.llm import set_user_providers  # re-export
    """)
    out = sort_source(src, Config())
    assert out.index("from knox.logging") < out.index("from knox.llm")
    assert out.index("from knox.llm") < out.index("logger =")


def test_runtime_setup_referencing_later_name_is_barrier() -> None:
    # A runtime_setup assignment referencing a later-defined name must stay put
    # (same forward-reference safety as constants).
    src = textwrap.dedent("""\
        import os
        class Service:
            pass
        handler = _make_handler(Service)
        _make_handler = lambda cls: cls()
    """)
    out = sort_source(src, Config())
    # handler references Service (classes section, after runtime_setup) -> barrier
    assert out.index("class Service") < out.index("handler =")


def test_runtime_setup_referencing_imported_name_moves() -> None:
    # A runtime_setup assignment referencing only imported/builtin names is safe
    # and reorders normally (no false barrier).
    src = textwrap.dedent("""\
        import os
        logger = get_logger(os.name)
        MAX_CONN = 10
    """)
    out = sort_source(src, Config())
    assert out.index("MAX_CONN") < out.index("logger =")


def test_runtime_setup_groups_keeping_original_order() -> None:
    # Multiple runtime_setup statements group together in their original order
    # (default strategy is "keep").
    src = textwrap.dedent("""\
        import os
        logger = get_logger(__name__)
        app = typer.Typer()
        def handler():
            pass
    """)
    out = sort_source(src, Config())
    logger_pos = out.index("logger =")
    app_pos = out.index("app =")
    handler_pos = out.index("def handler")
    assert logger_pos < app_pos < handler_pos


def test_runtime_setup_referencing_constant_is_safe() -> None:
    # A runtime_setup assignment may reference a module_constant (defined before
    # runtime_setup) — not a forward ref.
    src = textwrap.dedent("""\
        import os
        MAX_CONN = 10
        client = connect(host, MAX_CONN)
        def connect(host, n):
            return n
    """)
    out = sort_source(src, Config())
    assert out.index("MAX_CONN") < out.index("client =")
