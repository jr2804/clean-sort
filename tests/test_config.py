"""Tests for configuration discovery and parsing."""

from __future__ import annotations

import warnings
from pathlib import Path

from clean_sort import Config, discover, load_config


def test_defaults() -> None:
    cfg = Config()
    assert cfg.sections[0] == "imports"
    assert cfg.strategy("functions") == "keep"
    assert cfg.class_methods_enabled is True
    assert cfg.import_engine == "none"


def test_from_table_strategy() -> None:
    cfg = Config.from_table({"strategy": {"functions": "stepdown"}})
    assert cfg.strategy("functions") == "stepdown"


def test_invalid_strategy_warns() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        cfg = Config.from_table({"strategy": {"functions": "bogus"}})
    assert cfg.strategy("functions") == "keep"
    assert any("unknown strategy" in str(w.message).lower() for w in caught)


def test_invalid_engine_falls_back() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        cfg = Config.from_table({"imports": {"engine": "weird"}})
    assert cfg.import_engine == "none"


def test_load_pyproject(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[tool.csort.module]\nsections = ["functions", "imports"]\n[tool.csort.strategy]\nfunctions = "alpha"\n',
        encoding="utf-8",
    )
    cfg = load_config(start=tmp_path)
    assert cfg.sections == ["functions", "imports"]
    assert cfg.strategy("functions") == "alpha"
    assert cfg.config_path
    assert cfg.config_path.name == "pyproject.toml"


def test_load_standalone_csort_toml(tmp_path: Path) -> None:
    (tmp_path / "csort.toml").write_text('[module]\nsections = ["classes"]\n', encoding="utf-8")
    cfg = load_config(start=tmp_path)
    assert cfg.sections == ["classes"]
    assert cfg.config_path
    assert cfg.config_path.name == "csort.toml"


def test_load_dotconfig(tmp_path: Path) -> None:
    (tmp_path / ".config").mkdir()
    (tmp_path / ".config" / "csort.toml").write_text("[class_methods]\nenabled = false\n", encoding="utf-8")
    cfg = load_config(start=tmp_path)
    assert cfg.class_methods_enabled is False


def test_undersort_backcompat(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[tool.undersort]\norder = ["private", "public"]\n', encoding="utf-8")
    cfg = load_config(start=tmp_path)
    assert cfg.class_methods_order == ["private", "public"]


def test_undersort_backcompat_skipped_when_csort_present(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[tool.csort.class_methods]\norder = ["public", "private", "protected"]\n[tool.undersort]\norder = ["private", "public", "protected"]\n',
        encoding="utf-8",
    )
    cfg = load_config(start=tmp_path)
    assert cfg.class_methods_order == ["public", "private", "protected"]


def test_discover_walks_up(tmp_path: Path) -> None:
    sub = tmp_path / "pkg" / "mod"
    sub.mkdir(parents=True)
    (tmp_path / "csort.toml").write_text('[module]\nsections = ["x"]\n', encoding="utf-8")
    found = discover(sub)
    assert found
    assert found.name == "csort.toml"


def test_explicit_overrides_discovery(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[tool.csort.module]\nsections = ["functions"]\n', encoding="utf-8")
    explicit = tmp_path / "csort.toml"
    explicit.write_text('[module]\nsections = ["classes"]\n', encoding="utf-8")
    cfg = load_config(explicit=explicit)
    assert cfg.sections == ["classes"]


def test_no_config_returns_defaults(tmp_path: Path) -> None:
    cfg = load_config(start=tmp_path)
    assert cfg.sections == Config().sections
    assert cfg.config_path is None
