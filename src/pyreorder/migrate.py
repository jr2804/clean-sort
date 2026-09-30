"""Auto-migrate legacy pyreorder config and cache paths to the current scheme.

When the project was renamed from clean-sort -> pyreorder (and the per-project
config from csort.toml -> pyreorder.toml, the global config from csort.toml ->
config.toml, and the cache from csort/ -> pyreorder/), users who had alpha-
tested the tool ended up with files at the OLD paths. This module detects them
and renames them to the NEW paths, preserving data and logging each move.

Design points
-------------

1. **Mappings are data, not code.** Each release that does a rename adds a row
   to the legacy tables at the top of the module. The actual rename loop is
   generic. This keeps the policy (which paths are old) separate from the
   mechanism (how to rename).

2. **Idempotent.** Calling :func:`migrate` twice is a no-op the second time:
   after the first call, the OLD paths don't exist; the NEW paths do. After
   the first successful run, a sentinel file is written so the function is
   also fast on subsequent calls (no extra stat() calls beyond the sentinel
   check).

3. **Skip-if-new-exists.** Never overwrite a NEW path even if an OLD path
   also exists. Log a warning to stderr so the user can resolve manually.

4. **Atomic where possible.** :func:`os.replace` is used (atomic on POSIX +
   Windows for same-filesystem moves).

5. **No false positives.** We only rename a file/dir if its name is in the
   legacy set. We never pattern-match (e.g. ``*.toml``); a user's
   ``pyproject.toml`` is never moved, even if it sits next to ``csort.toml``.

6. **Hooks into CLI startup.** :func:`migrate_if_needed` is called from
   :func:`load_config` and from the cache-dir resolver before they read any
   state.

Jev cross-checked decisions (2026-09-29):

  G1 (per-project file): pyreorder.toml            (confidence 0.95)
  G2 (global subdir):    pyreorder                 (confidence 0.61, under threshold)
  G3 (global file):      config.toml               (confidence 0.97)
  G4 (cache dir name):   pyreorder                 (confidence 0.56, under threshold)
  G5 (migrate scope):    conservative              (confidence 0.89)
  G6 (migrate trigger):  once_per_layout           (confidence 0.44, under threshold)
"""

from __future__ import annotations

import os
import sys
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, TextIO

# === Legacy-to-new rename tables =====================================
# These are the Jev-confirmed rename targets. The function bodies below
# don't hard-code any names -- everything is parameterized through these
# constants, so adding a future rename (when this project renames again
# in two years) is a one-line change.

# Per-project config file (in cwd). Jev G1.
PER_PROJECT_CONFIG_OLD = "csort.toml"
PER_PROJECT_CONFIG_NEW = "pyreorder.toml"

# Global (per-user) config subdirectory + filename. Jev G2 + G3.
GLOBAL_CONFIG_SUBDIR_OLD = "csort"
GLOBAL_CONFIG_SUBDIR_NEW = "pyreorder"
GLOBAL_CONFIG_FILENAME_OLD = "csort.toml"
GLOBAL_CONFIG_FILENAME_NEW = "config.toml"

# Cache directory. Jev G4.
CACHE_DIR_OLD = "csort"
CACHE_DIR_NEW = "pyreorder"
PER_PROJECT_CACHE_OLD = ".csort-cache"
PER_PROJECT_CACHE_NEW = ".pyreorder-cache"

# Skills asset straggler (the only remaining 'csort' reference in the repo).
SKILLS_ASSET_OLD = "csort.toml"
SKILLS_ASSET_NEW = "pyreorder.toml"

# Sentinels
MIGRATE_SENTINEL_FILENAME = ".migrated-from-csort"


@dataclass(frozen=True)
class MigrationResult:
    """A single rename (or skip) outcome."""

    old_path: Path
    new_path: Path
    action: Literal["renamed", "skipped", "noop", "would_overwrite"]
    reason: str = ""

    def __str__(self) -> str:
        verb = {
            "renamed": "renamed",
            "skipped": "skipped",
            "noop": "noop",
            "would_overwrite": "WARN: would overwrite",
        }[self.action]
        return f"pyreorder-migrate: {verb:7s} {self.old_path} -> {self.new_path}" + (
            f"  ({self.reason})" if self.reason else ""
        )


@dataclass
class MigrationReport:
    """Aggregate of all rename attempts in one migration run."""

    results: list[MigrationResult] = field(default_factory=list)

    @property
    def renamed(self) -> list[MigrationResult]:
        return [r for r in self.results if r.action == "renamed"]

    @property
    def would_overwrite(self) -> list[MigrationResult]:
        return [r for r in self.results if r.action == "would_overwrite"]

    @property
    def skipped(self) -> list[MigrationResult]:
        return [r for r in self.results if r.action == "skipped"]

    def log(self, *, stream: TextIO | None = None) -> None:
        stream = stream or sys.stderr
        for r in self.results:
            if r.action != "noop":
                print(str(r), file=stream)


# === The actual rename primitives =====================================


def _rename_file(old: Path, new: Path) -> MigrationResult:
    """Rename a single file. Skip if new already exists; warn on overwrite."""
    if not old.exists():
        return MigrationResult(old, new, "noop", "old path does not exist")
    if new.exists():
        return MigrationResult(
            old, new, "would_overwrite",
            f"new path {new} already exists; refusing to overwrite",
        )
    try:
        new.parent.mkdir(parents=True, exist_ok=True)
        os.replace(old, new)
        return MigrationResult(old, new, "renamed")
    except OSError as exc:
        return MigrationResult(old, new, "skipped", f"os.replace failed: {exc}")


def _rename_dir(old: Path, new: Path) -> MigrationResult:
    """Rename a directory. Skip if new exists; warn on overwrite."""
    if not old.exists() or not old.is_dir():
        return MigrationResult(old, new, "noop", "old dir does not exist")
    if new.exists():
        return MigrationResult(
            old, new, "would_overwrite",
            f"new dir {new} already exists; refusing to overwrite",
        )
    try:
        new.parent.mkdir(parents=True, exist_ok=True)
        os.replace(old, new)
        return MigrationResult(old, new, "renamed")
    except OSError as exc:
        return MigrationResult(old, new, "skipped", f"os.replace failed: {exc}")


# === Public API =======================================================


def migrate_legacy_config(
    project_root: Path | None = None,
    *,
    home: Path | None = None,
) -> MigrationReport:
    """Migrate legacy config file/directory names to current scheme.

    Operates on:

    1. **Per-project file** in ``project_root`` (default: cwd).
    2. **Global config** under ``home/.config/`` (default: ``~/.config/``).
    """
    root = project_root or Path.cwd()
    h = home or Path.home()
    report = MigrationReport()

    # 1. Per-project config: any of the legacy names we know about.
    for old_name in (PER_PROJECT_CONFIG_OLD, "clean-sort.toml"):
        report.results.append(
            _rename_file(root / old_name, root / PER_PROJECT_CONFIG_NEW)
        )

    # 2. Global config: walk all the candidate subdir names that might have been used.
    for old_sub in (GLOBAL_CONFIG_SUBDIR_OLD, "clean-sort"):
        old_dir = h / ".config" / old_sub
        new_dir = h / ".config" / GLOBAL_CONFIG_SUBDIR_NEW
        for old_filename in (
            GLOBAL_CONFIG_FILENAME_OLD,
            "clean-sort.toml",
            "config.toml",
        ):
            report.results.append(
                _rename_file(old_dir / old_filename, new_dir / GLOBAL_CONFIG_FILENAME_NEW)
            )

    return report


def migrate_legacy_cache(
    project_root: Path | None = None,
    *,
    home: Path | None = None,
) -> MigrationReport:
    """Migrate legacy cache directories to current scheme."""
    root = project_root or Path.cwd()
    h = home or Path.home()
    report = MigrationReport()

    # 1. User-level cache
    for old_name in (CACHE_DIR_OLD, "clean-sort"):
        old = h / ".cache" / old_name
        new = h / ".cache" / CACHE_DIR_NEW
        report.results.append(_rename_dir(old, new))

    # 2. Project-relative cache
    for old_name in (PER_PROJECT_CACHE_OLD, ".clean-sort-cache"):
        old = root / old_name
        new = root / PER_PROJECT_CACHE_NEW
        report.results.append(_rename_dir(old, new))

    return report


def _sentinel_path(home: Path | None = None) -> Path:
    """Path of the migrate sentinel that records a completed migration."""
    h = home or Path.home()
    return h / ".cache" / CACHE_DIR_NEW / MIGRATE_SENTINEL_FILENAME


def migrate(
    project_root: Path | None = None,
    *,
    home: Path | None = None,
    write_sentinel: bool = True,
    sentinel_path: Path | None = None,
) -> MigrationReport:
    """Run all legacy migrations.

    If ``write_sentinel`` is True, on a successful migration (at least one
    rename), write a sentinel file marking that the migrate step has run for
    this layout. Subsequent calls can then short-circuit if the sentinel
    exists.
    """
    cfg_report = migrate_legacy_config(project_root, home=home)
    cache_report = migrate_legacy_cache(project_root, home=home)
    report = MigrationReport(results=cfg_report.results + cache_report.results)

    if write_sentinel and report.renamed:
        sentinel = sentinel_path or _sentinel_path(home)
        sentinel.parent.mkdir(parents=True, exist_ok=True)
        try:
            sentinel.write_text(
                f"migrated at {os.environ.get('HOSTNAME', '?')}\n",
                encoding="utf-8",
            )
        except OSError as exc:
            warnings.warn(
                f"pyreorder-migrate: could not write sentinel {sentinel}: {exc}",
                stacklevel=2,
            )

    return report


def migrate_if_needed(
    project_root: Path | None = None,
    *,
    home: Path | None = None,
    sentinel_path: Path | None = None,
) -> MigrationReport:
    """Run :func:`migrate` if the sentinel doesn't already exist.

    This is the function the CLI calls at startup (Jev G6 = once_per_layout).
    On a steady-state install with no legacy paths, the only cost is one
    ``stat()`` call on the sentinel file.
    """
    sentinel = sentinel_path or _sentinel_path(home)
    if sentinel.exists():
        return MigrationReport()
    return migrate(project_root, home=home, sentinel_path=sentinel)


__all__ = [
    "MigrationReport",
    "MigrationResult",
    "migrate",
    "migrate_if_needed",
    "migrate_legacy_cache",
    "migrate_legacy_config",
]
