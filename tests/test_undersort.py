"""Unit tests for ``clean_sort.undersort`` (in-class method sorting).

These tests pin the public contract:

* Visibility buckets: dunders are ``public``; ``__name`` is ``private``;
  ``_name`` is ``protected``; otherwise ``public``.
* Method-type buckets: ``@classmethod`` → ``class``, ``@staticmethod`` →
  ``static``, otherwise ``instance``.
* Default ordering: public → protected → private, instance → class → static.
* Custom ordering reshuffles method groups while keeping stability inside
  each group.
* ``# nosort`` per-method marker locks a method at its original index;
  ``# nosort`` / ``# csort: off`` on the file header disables the file.
* Non-method class-body items keep their leading/trailing position; methods
  alone are reordered.
* Decorators accessed via dotted form (``a.classmethod``) still count.
"""

from __future__ import annotations

import textwrap
import warnings

import libcst as cst
import pytest

from clean_sort import Config, sort_source
from clean_sort.undersort import (
    MethodSorter,
    file_disabled,
    has_disable_comment,
    method_type,
    method_visibility,
)


# ---------------------------------------------------------------------- helpers
def _sort_methods(src: str, **kwargs) -> str:
    return sort_source(textwrap.dedent(src), Config(**kwargs))


def _sort_with_sorter(src: str, **kwargs) -> tuple[str, MethodSorter]:
    cfg = Config(**kwargs)
    module = cst.parse_module(textwrap.dedent(src))
    sorter = MethodSorter(cfg.class_methods_order, cfg.class_methods_type_order)
    new_module = module.visit(sorter)
    return new_module.code, sorter


# ---------------------------------------------------------- visibility buckets
@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("__init__", "public"),  # dunder
        ("__str__", "public"),
        ("_helper", "protected"),
        ("__secret", "private"),
        ("run", "public"),
    ],
)
def test_method_visibility(name: str, expected: str) -> None:
    assert method_visibility(name) == expected


# -------------------------------------------------------------- type buckets
def _class_method(src: str) -> cst.FunctionDef:
    """Return the first method of the first class in ``src``."""
    module = cst.parse_module(src)
    cls = module.body[0]
    assert isinstance(cls, cst.ClassDef)
    func = cls.body.body[0]
    assert isinstance(func, cst.FunctionDef), f"expected FunctionDef, got {type(func).__name__}"
    return func


def test_method_type_instance_default() -> None:
    fn = _class_method("class C:\n    def m(self):\n        pass\n")
    assert method_type(fn) == "instance"


def test_method_type_classmethod() -> None:
    fn = _class_method("class C:\n    @classmethod\n    def m(cls):\n        pass\n")
    assert method_type(fn) == "class"


def test_method_type_staticmethod() -> None:
    fn = _class_method("class C:\n    @staticmethod\n    def m():\n        pass\n")
    assert method_type(fn) == "static"


def test_method_type_dotted_decorator() -> None:
    # Decorators resolved as ``a.classmethod`` must still match.
    fn = _class_method("class C:\n    @a.classmethod\n    def m(cls):\n        pass\n")
    assert method_type(fn) == "class"


# ------------------------------------------------------------------- ordering
def test_default_order_groups_visibility_then_type() -> None:
    # public instance (start), public static (make), public class (create),
    # private instance (__secret).
    src = textwrap.dedent(
        """\
        class C:
            def __secret(self):
                pass
            @staticmethod
            def make():
                pass
            @classmethod
            def create(cls):
                pass
            def start(self):
                pass
        """
    )
    out = _sort_methods(src)

    def pos(name: str) -> int:
        return out.index(f"def {name}")

    # Within public: instance → class → static (default).
    assert pos("start") < pos("create")
    assert pos("create") < pos("make")
    # After every public method comes the private one.
    assert pos("make") < pos("__secret")


def test_custom_visibility_order_private_first() -> None:
    src = textwrap.dedent(
        """\
        class C:
            def pub(self):
                pass
            def __priv(self):
                pass
        """
    )
    out = _sort_methods(src, class_methods_order=["private", "protected", "public"])
    assert out.index("def __priv") < out.index("def pub")


def test_custom_type_order_static_first() -> None:
    src = textwrap.dedent(
        """\
        class C:
            def i(self):
                pass
            @staticmethod
            def s():
                pass
        """
    )
    out = _sort_methods(src, class_methods_type_order=["static", "instance", "class"])
    assert out.index("def s") < out.index("def i")


def test_invalid_order_warns_and_keeps_default() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        Config.from_table({"class_methods": {"order": ["nope", "public"]}})
    assert any("invalid class_methods_order" in str(w.message) for w in caught)


# ----------------------------------------------------------------- directives
def test_file_disabled_nosort_header() -> None:
    src = textwrap.dedent(
        """\
        # nosort
        def b():
            pass
        def a():
            pass
        """
    )
    out = _sort_methods(src, strategies={"functions": "alpha"})
    assert out == src  # file-level nosort = full skip


def test_per_method_nosort_locks_position() -> None:
    src = textwrap.dedent(
        """\
        class C:
            def pub(self):
                pass
            def __priv(self):  # nosort
                pass
            def prot(self):
                pass
        """
    )
    cfg = Config(class_methods_order=["private", "protected", "public"])
    out = sort_source(src, cfg)
    # Order should be pub, __priv (locked), prot.
    assert (
        out.index("def pub")
        < out.index("def __priv")
        < out.index("def prot")
    )


def test_per_method_csort_off_locks_position() -> None:
    src = textwrap.dedent(
        """\
        class C:
            def pub(self):
                pass
            def __priv(self):  # csort: off
                pass
            def prot(self):
                pass
        """
    )
    cfg = Config(class_methods_order=["private", "protected", "public"])
    out = sort_source(src, cfg)
    assert out.index("def pub") < out.index("def __priv") < out.index("def prot")


def test_class_disable_directive_trailing() -> None:
    src = textwrap.dedent(
        """\
        class C:  # csort: off
            def _z(self):
                pass
            def a(self):
                pass
        """
    )
    out = _sort_methods(src)
    assert out.index("def _z") < out.index("def a")


def test_has_disable_comment_handles_node_without_comment() -> None:
    # Constructing a bare class with no comments; the helper must not crash.
    module = cst.parse_module("class C:\n    pass\n")
    cls = module.body[0]
    assert isinstance(cls, cst.ClassDef)
    assert has_disable_comment(cls) is False


# ------------------------------------------------------- non-method body items
def test_module_constants_in_class_body_keep_position() -> None:
    src = textwrap.dedent(
        """\
        class C:
            KEEP_ME = 1
            def _z(self):
                pass
            def a(self):
                pass
        """
    )
    out = _sort_methods(src)
    # Leading non-method stays first; methods reorder, but KEEP_ME stays before them.
    assert out.index("KEEP_ME") < out.index("def a")


def test_trailing_docstring_keeps_position() -> None:
    src = textwrap.dedent(
        """\
        class C:
            def _z(self):
                pass
            def a(self):
                pass
            \"\"\"trailing doc\"\"\"
        """
    )
    out = _sort_methods(src)
    # After resorting, trailing non-method must remain at the end.
    assert out.index('"""trailing doc"""') > out.index("def a")


# --------------------------------------------------------------- modified flag
def test_modified_flag_true_when_order_changes() -> None:
    # Input is reverse of default visibility; the sorter must reorder.
    src = textwrap.dedent(
        """\
        class C:
            def _z(self):
                pass
            def a(self):
                pass
        """
    )
    _, sorter = _sort_with_sorter(src)
    assert sorter.modified is True


def test_modified_flag_false_when_already_sorted() -> None:
    src = textwrap.dedent(
        """\
        class C:
            def a(self):
                pass
            def b(self):
                pass
        """
    )
    cfg = Config(class_methods_order=["public", "protected", "private"])
    module = cst.parse_module(src)
    sorter = MethodSorter(cfg.class_methods_order, cfg.class_methods_type_order)
    module.visit(sorter)
    # Both are public instance → no reordering happens.
    assert sorter.modified is False


def test_modified_flag_false_for_empty_class() -> None:
    src = "class C:\n    pass\n"
    module = cst.parse_module(src)
    sorter = MethodSorter()
    module.visit(sorter)
    assert sorter.modified is False


# ------------------------------------------------------------- file_disabled
def test_file_disabled_helper_false_when_no_marker() -> None:
    module = cst.parse_module("import os\n")
    assert file_disabled(module) is False


def test_file_disabled_helper_true_for_csort_off() -> None:
    module = cst.parse_module("# csort: off\nimport os\n")
    assert file_disabled(module) is True


# --------------------------------------------------------------------- end-to-end
def test_pipeline_end_to_end_matches_undersort_semantics() -> None:
    # Smoke test that the full pipeline (sort_source) actually calls MethodSorter
    # after SectionSorter, with class_methods_enabled=True (default).
    src = textwrap.dedent(
        """\
        class C:
            def _prot(self):
                pass
            def pub(self):
                pass
        """
    )
    out = sort_source(src, Config())
    assert out.index("def pub") < out.index("def _prot")
