"""Tests for opt-in import transforms (inline hoist + TYPE_CHECKING removal)."""

from __future__ import annotations

from clean_sort import Config, sort_source, would_change


def sort(src: str, **kwargs) -> str:
    return sort_source(src, Config(**kwargs))


# --------------------------------------------------------- inline import hoist
def test_hoist_inline_import_removes_from_function() -> None:
    src = "def f():\n    import json\n    return json.loads('{}')\n"
    out = sort(src, hoist_inline_imports=True)
    assert "import json" in out.split("def f")[0]  # before the function
    assert "import json" not in out.split("def f")[1]  # not in the body


def test_hoist_inline_import_deduplicates() -> None:
    src = "def _load():\n    import json\n    return json.loads('{}')\ndef _save():\n    import json\n    json.dumps([])\n"
    out = sort(src, hoist_inline_imports=True)
    assert out.count("import json") == 1


def test_hoist_inline_import_preserves_function_body() -> None:
    src = "import os\ndef f():\n    import json\n    return json.loads('{}')\n"
    out = sort(src, hoist_inline_imports=True)
    assert "return json.loads('{}')" in out


def test_hoist_inline_import_idempotent() -> None:
    src = "import os\n\ndef _load():\n    import json\n    return json.loads('{}')\n\ndef _save():\n    import json\n    json.dumps([])\n"
    once = sort(src, hoist_inline_imports=True)
    assert sort(once, hoist_inline_imports=True) == once


def test_hoist_inline_import_off_by_default() -> None:
    src = "def f():\n    import json\n    return json.loads('{}')\n"
    out = sort_source(src, Config())  # default: off
    assert "import json" not in out.split("def f")[0]


def test_hoist_inline_import_leaves_nested_function_imports() -> None:
    # imports inside a nested function are NOT hoisted (only direct body)
    src = "def outer():\n    def inner():\n        import json\n        return json.loads('{}')\n    return inner()\n"
    out = sort(src, hoist_inline_imports=True)
    # The import stays inside inner()
    assert "import json" in out.split("def inner")[1]


def test_hoist_inline_import_from_form() -> None:
    src = "def f():\n    from os.path import join\n    return join('a', 'b')\n"
    out = sort(src, hoist_inline_imports=True)
    assert "from os.path import join" in out.split("def f")[0]


# ------------------------------------------------------- TYPE_CHECKING removal
def test_remove_type_checking_dissolves_guard() -> None:
    src = "if TYPE_CHECKING:\n    import http.client\n\nx = 1\n"
    out = sort(src, remove_type_checking=True)
    assert "TYPE_CHECKING" not in out
    assert "import http.client" in out


def test_remove_type_checking_removes_unused_import() -> None:
    src = "from typing import TYPE_CHECKING\n\nif TYPE_CHECKING:\n    import http.client\n\nx = 1\n"
    out = sort(src, remove_type_checking=True)
    assert "TYPE_CHECKING" not in out
    assert "import http.client" in out


def test_remove_type_checking_preserves_other_typing_names() -> None:
    src = "from typing import TYPE_CHECKING, Any\n\nif TYPE_CHECKING:\n    import http.client\n\nx: Any = 1\n"
    out = sort(src, remove_type_checking=True)
    assert "TYPE_CHECKING" not in out
    assert "Any" in out
    assert "import http.client" in out


def test_remove_type_checking_idempotent() -> None:
    src = "from typing import TYPE_CHECKING\n\nif TYPE_CHECKING:\n    import http.client\n\nclass C: pass\n"
    once = sort(src, remove_type_checking=True)
    assert sort(once, remove_type_checking=True) == once


def test_remove_type_checking_off_by_default() -> None:
    src = "if TYPE_CHECKING:\n    import http.client\n\nx = 1\n"
    out = sort_source(src, Config())  # default: off
    assert "TYPE_CHECKING" in out


def test_remove_type_checking_skips_blocks_with_non_imports() -> None:
    # If the TYPE_CHECKING block has runtime code, we leave it alone.
    src = "if TYPE_CHECKING:\n    import os\n    x = 1\n"
    out = sort(src, remove_type_checking=True)
    assert "TYPE_CHECKING" in out  # untouched


def test_remove_type_checking_attribute_form() -> None:
    # typing.TYPE_CHECKING attribute access form
    src = "import typing\n\nif typing.TYPE_CHECKING:\n    import http.client\n\nx = 1\n"
    out = sort(src, remove_type_checking=True)
    assert "import http.client" in out


# --------------------------------------------------------- combined / edge cases
def test_both_transforms_off_by_default_no_change() -> None:
    src = "from typing import TYPE_CHECKING\n\nif TYPE_CHECKING:\n    import os\n\ndef f():\n    import json\n"
    assert sort_source(src, Config()) == src


def test_would_change_with_transforms() -> None:
    src = "def f():\n    import json\n    return 1\n"
    assert would_change(src, Config(hoist_inline_imports=True)) is True
    assert would_change(src, Config()) is False


def test_transforms_respect_file_disable() -> None:
    src = "# csort: off\ndef f():\n    import json\n    return 1\n"
    assert sort_source(src, Config(hoist_inline_imports=True)) == src


# --------------------------------------------------------- additional coverage
def test_hoist_mixed_import_and_code_line() -> None:
    # import + non-import on the same SimpleStatementLine — import removed, code kept
    src = "def f():\n    import json; x = 1\n    return json.loads('{}')\n"
    out = sort(src, hoist_inline_imports=True)
    assert "import json" in out.split("def f")[0]
    assert "x = 1" in out.split("def f")[1]


def test_hoist_dedup_with_alias() -> None:
    # same module, different alias — both kept; same alias — deduped
    src = "def f():\n    import json as j\n    return j.loads('{}')\ndef g():\n    import json as j\n    j.dumps([])\n"
    out = sort(src, hoist_inline_imports=True)
    assert out.count("import json as j") == 1


def test_remove_type_checking_with_elif_chain() -> None:
    # if TYPE_CHECKING / elif TYPE_CHECKING — both dissolved
    src = "if TYPE_CHECKING:\n    import os\nelif TYPE_CHECKING:\n    import sys\nx = 1\n"
    out = sort(src, remove_type_checking=True)
    assert "import os" in out
    assert "import sys" in out
    assert "TYPE_CHECKING" not in out


def test_remove_type_checking_with_else_block_skipped() -> None:
    # if TYPE_CHECKING / else with code — left untouched (non-import in else)
    src = "if TYPE_CHECKING:\n    import os\nelse:\n    x = 1\n"
    out = sort(src, remove_type_checking=True)
    assert "TYPE_CHECKING" in out  # untouched


def test_both_transforms_together() -> None:
    src = "from typing import TYPE_CHECKING\n\nif TYPE_CHECKING:\n    import http.client\n\ndef f():\n    import json\n    return 1\n"
    out = sort(src, hoist_inline_imports=True, remove_type_checking=True)
    assert "TYPE_CHECKING" not in out
    assert "import http.client" in out
    assert "import json" in out


def test_remove_type_checking_star_import_preserved() -> None:
    # from typing import * — should not crash, TYPE_CHECKING stays in *
    src = "from typing import *\n\nif TYPE_CHECKING:\n    import os\n\nx = 1\n"
    out = sort(src, remove_type_checking=True)
    assert "import os" in out


def test_hoist_preserves_compound_statements_in_body() -> None:
    # import + if/for block — both survive, import hoisted
    src = "def f():\n    import json\n    for i in range(3):\n        pass\n    return json.loads('{}')\n"
    out = sort(src, hoist_inline_imports=True)
    assert "import json" in out.split("def f")[0]
    assert "for i in range(3)" in out
    assert "return json.loads" in out


# --------------------------------------------------------- # noqa stripping
def test_hoist_strips_noqa_from_hoisted_import() -> None:
    # An inline import carrying a # noqa suppression loses it when hoisted.
    src = "def f():\n    import json  # noqa: PLC0415\n    return json.loads('{}')\n"
    out = sort(src, hoist_inline_imports=True)
    assert "import json" in out.split("def f")[0]
    assert "noqa" not in out


def test_hoist_strips_bare_noqa_from_hoisted_import() -> None:
    # Bare ``noqa`` (no codes) is stripped too.
    src = "def f():\n    import json  # noqa\n    return 1\n"
    out = sort(src, hoist_inline_imports=True)
    assert "import json" in out.split("def f")[0]
    assert "noqa" not in out


def test_hoist_no_strip_no_trailing_whitespace() -> None:
    # After stripping the noqa, no trailing whitespace is left on the line.
    src = "def f():\n    import json  # noqa: PLC0415\n    return 1\n"
    out = sort(src, hoist_inline_imports=True)
    hoisted_line = out.splitlines()[0]
    assert hoisted_line == "import json"


def test_hoist_preserves_non_noqa_comment_on_hoisted_import() -> None:
    # A non-noqa comment is preserved on the hoisted import.
    src = "def f():\n    import json  # used for parsing\n    return json.loads('{}')\n"
    out = sort(src, hoist_inline_imports=True)
    assert "import json  # used for parsing" in out


def test_remove_type_checking_strips_noqa_from_hoisted_import() -> None:
    # An import inside a TYPE_CHECKING block carrying # noqa loses it.
    src = "if TYPE_CHECKING:\n    import http.client  # noqa: F401\n\nx = 1\n"
    out = sort(src, remove_type_checking=True)
    assert "import http.client" in out
    assert "noqa" not in out


def test_remove_type_checking_strips_noqa_no_trailing_whitespace() -> None:
    # No trailing whitespace left after stripping the noqa.
    src = "if TYPE_CHECKING:\n    import http.client  # noqa: F401\n\nx = 1\n"
    out = sort(src, remove_type_checking=True)
    for line in out.splitlines():
        assert line.rstrip() == line or line == line.rstrip()


def test_remove_type_checking_preserves_non_noqa_comment() -> None:
    # A non-noqa comment on a TYPE_CHECKING import is preserved.
    src = "if TYPE_CHECKING:\n    import http.client  # type-only dep\n\nx = 1\n"
    out = sort(src, remove_type_checking=True)
    assert "import http.client  # type-only dep" in out


def test_noqa_strip_is_case_insensitive() -> None:
    # ``NOQA`` (uppercase) is also stripped.
    src = "def f():\n    import json  # NOQA\n    return 1\n"
    out = sort(src, hoist_inline_imports=True)
    assert "NOQA" not in out
    assert "noqa" not in out
