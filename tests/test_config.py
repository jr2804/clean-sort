"""Tests for configuration discovery and parsing."""

from __future__ import annotations

import textwrap
import warnings
from pathlib import Path

from pyreorder import Config, discover, load_config


def test_defaults() -> None:
    cfg = Config()
    assert cfg.sections[0] == "imports"
    assert cfg.strategy("functions") == "keep"
    assert cfg.class_methods_enabled is True


def test_from_table_strategy() -> None:
    cfg = Config.from_table({"strategy": {"functions": "stepdown"}})
    assert cfg.strategy("functions") == "stepdown"


def test_invalid_strategy_warns() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        cfg = Config.from_table({"strategy": {"functions": "bogus"}})
    assert cfg.strategy("functions") == "keep"
    assert any("unknown strategy" in str(w.message).lower() for w in caught)


def test_load_pyproject(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[tool.preorder.module]\nsections = ["functions", "imports"]\n[tool.preorder.strategy]\nfunctions = "alpha"\n',
        encoding="utf-8",
    )
    cfg = load_config(start=tmp_path)
    assert cfg.sections == ["functions", "imports"]
    assert cfg.strategy("functions") == "alpha"
    assert cfg.config_path
    assert cfg.config_path.name == "pyproject.toml"


def test_load_standalone_csort_toml(tmp_path: Path) -> None:
    (tmp_path / "pyreorder.toml").write_text('[module]\nsections = ["classes"]\n', encoding="utf-8")
    cfg = load_config(start=tmp_path)
    assert cfg.sections == ["classes"]
    assert cfg.config_path
    assert cfg.config_path.name == "pyreorder.toml"


def test_load_dotconfig(tmp_path: Path) -> None:
    (tmp_path / ".config").mkdir()
    (tmp_path / ".config" / "pyreorder.toml").write_text("[class_methods]\nenabled = false\n", encoding="utf-8")
    cfg = load_config(start=tmp_path)
    assert cfg.class_methods_enabled is False


def test_discover_walks_up(tmp_path: Path) -> None:
    sub = tmp_path / "pkg" / "mod"
    sub.mkdir(parents=True)
    (tmp_path / "pyreorder.toml").write_text('[module]\nsections = ["x"]\n', encoding="utf-8")
    found = discover(sub)
    assert found
    assert found.name == "pyreorder.toml"


def test_explicit_overrides_discovery(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[tool.preorder.module]\nsections = ["functions"]\n', encoding="utf-8")
    explicit = tmp_path / "pyreorder.toml"
    explicit.write_text('[module]\nsections = ["classes"]\n', encoding="utf-8")
    cfg = load_config(explicit=explicit)
    assert cfg.sections == ["classes"]


def test_no_config_returns_defaults(tmp_path: Path) -> None:
    cfg = load_config(start=tmp_path)
    assert cfg.sections == Config().sections
    assert cfg.config_path is None


def test_transforms_table_parsed(tmp_path: Path) -> None:
    (tmp_path / "pyreorder.toml").write_text(
        "[transforms]\nhoist_inline_imports = true\nremove_type_checking = true\n",
        encoding="utf-8",
    )
    cfg = load_config(start=tmp_path)
    assert cfg.hoist_inline_imports is True
    assert cfg.remove_type_checking is True


def test_transforms_default_off() -> None:
    cfg = Config()
    assert cfg.hoist_inline_imports is False
    assert cfg.remove_type_checking is False


# ------------------------------------------------------------ legacy [tool.undersort]
def test_legacy_tool_undersort_pyproject(tmp_path: Path) -> None:
    # pyproject.toml spelling of the legacy config is honoured when the preorder
    # class_methods table is absent.
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        textwrap.dedent(
            """\
            [tool.undersort]
            order = ["private", "protected", "public"]
            method_type_order = ["static", "instance", "class"]
            """
        ),
        encoding="utf-8",
    )
    cfg = load_config(explicit=pyproject)
    assert cfg.class_methods_order == ["private", "protected", "public"]
    assert cfg.class_methods_type_order == ["static", "instance", "class"]
    assert cfg.class_methods_enabled is True  # legacy schema predates enabled


def test_legacy_top_level_undersort_csort_toml(tmp_path: Path) -> None:
    # Standalone preorder.toml also accepts a top-level [undersort] table.
    csort_toml = tmp_path / "pyreorder.toml"
    csort_toml.write_text(
        textwrap.dedent(
            """\
            [undersort]
            order = ["public", "private", "protected"]
            """
        ),
        encoding="utf-8",
    )
    cfg = load_config(explicit=csort_toml)
    assert cfg.class_methods_order == ["public", "private", "protected"]
    assert cfg.class_methods_type_order == ["instance", "class", "static"]  # default


def test_csort_class_methods_wins_over_legacy(tmp_path: Path) -> None:
    # When both tables exist the preorder one (closer, scoped to class_methods)
    # takes precedence.
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        textwrap.dedent(
            """\
            [tool.preorder.class_methods]
            order = ["public", "protected", "private"]

            [tool.undersort]
            order = ["private", "protected", "public"]
            """
        ),
        encoding="utf-8",
    )
    cfg = load_config(explicit=pyproject)
    assert cfg.class_methods_order == ["public", "protected", "private"]


def test_legacy_invalid_order_warns(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        textwrap.dedent(
            """\
            [tool.undersort]
            order = ["bogus"]
            """
        ),
        encoding="utf-8",
    )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        cfg = load_config(explicit=pyproject)
    assert cfg.class_methods_order == ["public", "protected", "private"]  # default
    assert any("invalid class_methods_order" in str(w.message) for w in caught)


# ------------------------------------------------------------- [discovery] table


def test_discovery_exclude_and_recursive(tmp_path: Path) -> None:
    cfg_file = tmp_path / "pyreorder.toml"
    cfg_file.write_text(
        textwrap.dedent(
            """\
            [discovery]
            exclude = ["vendor/**", "**/_generated.py"]
            recursive = false
            """
        ),
        encoding="utf-8",
    )
    cfg = load_config(explicit=cfg_file)
    assert cfg.exclude == ["vendor/**", "**/_generated.py"]
    assert cfg.recursive is False


def test_discovery_defaults_when_absent(tmp_path: Path) -> None:
    cfg_file = tmp_path / "pyreorder.toml"
    cfg_file.write_text('[strategy]\nfunctions = "alpha"\n', encoding="utf-8")
    cfg = load_config(explicit=cfg_file)
    assert cfg.exclude == []
    assert cfg.recursive is True


def test_discovery_invalid_exclude_warns(tmp_path: Path) -> None:
    cfg_file = tmp_path / "pyreorder.toml"
    cfg_file.write_text(
        textwrap.dedent(
            """\
            [discovery]
            exclude = "not-a-list"
            """
        ),
        encoding="utf-8",
    )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        cfg = load_config(explicit=cfg_file)
    assert cfg.exclude == []  # falls back to default
    assert any("discovery.exclude must be a list" in str(w.message) for w in caught)


# ---------------------------------------------------- [classification] table


def test_classification_dunder_exports_names_parsed(tmp_path: Path) -> None:
    cfg_file = tmp_path / "pyreorder.toml"
    cfg_file.write_text(
        textwrap.dedent(
            """\
            [classification]
            dunder_exports_names = ["__all__", "__version__", "__author__"]
            """
        ),
        encoding="utf-8",
    )
    cfg = load_config(explicit=cfg_file)
    assert cfg.dunder_exports_names == ["__all__", "__version__", "__author__"]


def test_classification_dunder_exports_names_default() -> None:
    assert Config().dunder_exports_names == ["__all__"]


def test_classification_invalid_dunder_exports_names_warns(tmp_path: Path) -> None:
    cfg_file = tmp_path / "pyreorder.toml"
    cfg_file.write_text(
        textwrap.dedent(
            """\
            [classification]
            dunder_exports_names = "not-a-list"
            """
        ),
        encoding="utf-8",
    )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        cfg = load_config(explicit=cfg_file)
    assert cfg.dunder_exports_names == ["__all__"]  # default
    assert any("dunder_exports_names must be a list" in str(w.message) for w in caught)
