"""Tests for src/pyreorder/migrate.py.

Tests use pytest's ``tmp_path`` fixture for an isolated filesystem and
``monkeypatch`` to redirect HOME so we don't touch the real user dir.

Covered:
  - per-project config file rename (csort.toml, preorder.toml -> pyreorder.toml)
  - global config rename (~/.config/<old>/<old_filename> -> ~/.config/<new>/<new_filename>)
  - user-cache rename (~/.cache/<old>/ -> ~/.cache/<new>/)
  - project-cache rename (./.<old>-cache/ -> ./.<new>-cache/)

Safety properties:
  - idempotent (running twice is a no-op)
  - never overwrites a NEW path that already exists
  - never moves pyproject.toml (the test fixture sets one up at the project root)
  - sentinel short-circuits subsequent calls
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from pyreorder.migrate import (
    CACHE_DIR_NEW,
    GLOBAL_CONFIG_FILENAME_NEW,
    GLOBAL_CONFIG_SUBDIR_NEW,
    MIGRATE_SENTINEL_FILENAME,
    PER_PROJECT_CACHE_NEW,
    PER_PROJECT_CONFIG_NEW,
    MigrationReport,
    migrate,
    migrate_if_needed,
    migrate_legacy_cache,
    migrate_legacy_config,
)


@pytest.fixture
def fs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An isolated filesystem rooted at tmp_path with HOME set to a subdir."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    return tmp_path


# --- Per-project config -----------------------------------------------


def test_per_project_preorder_to_pyreorder(fs: Path) -> None:
    (fs / "preorder.toml").write_text("# interim\n", encoding="utf-8")
    report = migrate_legacy_config(project_root=fs)
    assert len(report.renamed) == 1
    assert (fs / PER_PROJECT_CONFIG_NEW).exists()
    assert (fs / PER_PROJECT_CONFIG_NEW).read_text() == "# interim\n"
    assert not (fs / "preorder.toml").exists()


def test_per_project_csort_to_pyreorder(fs: Path) -> None:
    (fs / "csort.toml").write_text("# legacy\n", encoding="utf-8")
    report = migrate_legacy_config(project_root=fs)
    assert len(report.renamed) == 1
    assert (fs / PER_PROJECT_CONFIG_NEW).read_text() == "# legacy\n"


def test_pyproject_unaffected(fs: Path) -> None:
    pyproject = fs / "pyproject.toml"
    pyproject.write_text('[tool.preorder]\nstrategy = "keep"\n', encoding="utf-8")
    (fs / "csort.toml").write_text("# legacy\n", encoding="utf-8")
    migrate_legacy_config(project_root=fs)
    assert pyproject.read_text() == '[tool.preorder]\nstrategy = "keep"\n'
    assert (fs / PER_PROJECT_CONFIG_NEW).exists()


def test_no_legacy_config_no_op(fs: Path) -> None:
    report = migrate_legacy_config(project_root=fs)
    assert report.renamed == []


def test_does_not_overwrite_existing_new(fs: Path) -> None:
    (fs / "csort.toml").write_text("# old\n", encoding="utf-8")
    (fs / PER_PROJECT_CONFIG_NEW).write_text("# new and important\n", encoding="utf-8")
    report = migrate_legacy_config(project_root=fs)
    assert len(report.would_overwrite) >= 1
    assert (fs / "csort.toml").exists()
    assert (fs / PER_PROJECT_CONFIG_NEW).read_text() == "# new and important\n"


# --- Global config -----------------------------------------------------


def test_global_config_rename(fs: Path) -> None:
    home = Path(os.environ["HOME"])
    old_dir = home / ".config" / "preorder"
    old_dir.mkdir(parents=True)
    (old_dir / "preorder.toml").write_text("# legacy\n", encoding="utf-8")
    report = migrate_legacy_config(project_root=fs)
    new_dir = home / ".config" / GLOBAL_CONFIG_SUBDIR_NEW
    assert (new_dir / GLOBAL_CONFIG_FILENAME_NEW).exists()
    assert (new_dir / GLOBAL_CONFIG_FILENAME_NEW).read_text() == "# legacy\n"
    assert not (old_dir / "preorder.toml").exists()


# --- Cache -------------------------------------------------------------


def test_user_cache_rename(fs: Path) -> None:
    home = Path(os.environ["HOME"])
    old = home / ".cache" / "preorder"
    old.mkdir(parents=True)
    (old / "someproject").mkdir()
    (old / "someproject" / "cache.json").write_text("{}", encoding="utf-8")
    report = migrate_legacy_cache(project_root=fs)
    new = home / ".cache" / CACHE_DIR_NEW
    assert (new / "someproject" / "cache.json").exists()
    assert (new / "someproject" / "cache.json").read_text() == "{}"
    assert not old.exists()


def test_project_cache_rename(fs: Path) -> None:
    (fs / ".preorder-cache").mkdir()
    (fs / ".preorder-cache" / "x.json").write_text("x", encoding="utf-8")
    report = migrate_legacy_cache(project_root=fs)
    assert (fs / PER_PROJECT_CACHE_NEW / "x.json").exists()
    assert not (fs / ".preorder-cache").exists()


# --- Idempotency -------------------------------------------------------


def test_migrate_is_idempotent(fs: Path) -> None:
    (fs / "csort.toml").write_text("# x\n", encoding="utf-8")
    first = migrate(project_root=fs)
    assert len(first.renamed) >= 1
    second = migrate(project_root=fs)
    assert second.renamed == []
    assert all(r.action == "noop" for r in second.results)


def test_migrate_if_needed_short_circuits_on_sentinel(fs: Path) -> None:
    home = Path(os.environ["HOME"])
    sentinel = home / ".cache" / CACHE_DIR_NEW / MIGRATE_SENTINEL_FILENAME
    sentinel.parent.mkdir(parents=True)
    sentinel.write_text("migrated\n", encoding="utf-8")
    (fs / "csort.toml").write_text("# x\n", encoding="utf-8")
    report = migrate_if_needed(project_root=fs)
    assert report.results == []  # sentinel short-circuited
    assert (fs / "csort.toml").exists()  # not touched


def test_migrate_combined(fs: Path) -> None:
    """End-to-end: per-project, global config, user cache, project cache."""
    home = Path(os.environ["HOME"])
    (fs / "csort.toml").write_text("# cfg\n", encoding="utf-8")
    (home / ".config" / "preorder").mkdir(parents=True)
    (home / ".config" / "preorder" / "preorder.toml").write_text("# gcfg\n", encoding="utf-8")
    (home / ".cache" / "preorder").mkdir(parents=True)
    (home / ".cache" / "preorder" / "abc").mkdir()
    (fs / ".preorder-cache").mkdir()
    (fs / ".preorder-cache" / "y").write_text("z", encoding="utf-8")
    report = migrate(project_root=fs)
    assert len(report.renamed) >= 4
    assert (fs / PER_PROJECT_CONFIG_NEW).exists()
    assert (home / ".config" / GLOBAL_CONFIG_SUBDIR_NEW / GLOBAL_CONFIG_FILENAME_NEW).exists()
    assert (home / ".cache" / CACHE_DIR_NEW / "abc").exists()
    assert (fs / PER_PROJECT_CACHE_NEW / "y").exists()


def test_sentinel_written_after_rename(fs: Path) -> None:
    home = Path(os.environ["HOME"])
    (fs / "csort.toml").write_text("# x\n", encoding="utf-8")
    migrate(project_root=fs)
    sentinel = home / ".cache" / CACHE_DIR_NEW / MIGRATE_SENTINEL_FILENAME
    assert sentinel.exists()
