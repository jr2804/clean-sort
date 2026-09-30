# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- **Documentation site is published**: `ci.yml` deploys the built site to GitHub
  Pages from `main`, and the repository homepage and `[project.urls]` point at it.
- **Development page** covering setup, the `mise` tasks, testing, type checking,
  the docs build, pre-commit hooks, the release process, and the project layout.

### Changed

- **Project status is beta** (`Development Status :: 4 - Beta`).
- The release workflow now **stamps `[Unreleased]`** in `CHANGELOG.md` with the new
  CalVer version and date before tagging, so a released change never stays listed
  as "Unreleased".
- Maintainer address in the package metadata, code of conduct, and beads export
  replaced with a placeholder.

### Fixed

- **Mermaid diagrams render.** `zensical.toml` overrode Zensical's default
  `custom_fences` list (which ships the `mermaid` fence), so every diagram was
  emitted as a plain code block.
- **The generated dependency list on the credits page renders.** The generator only
  printed under `if __name__ == "__main__"`, but `markdown-exec` runs it with a
  synthetic `__name__` and emits nothing when no output is produced.
- **Dropped a fabricated `.pyc-source cache`** from the architecture page; the
  package has a single content-hash cache.

## [2026.09.6] - 2026-09-30

### Added

- **Documentation overhaul**: New `Architecture` page with two Mermaid
  pipeline diagrams (per-stage data flow and per-file work decomposition);
  new `Comparison with other tools` page positioning `pyreorder` against
  `isort`, Ruff `I001`, `undersort`, `ssort`, `sdsort`, and `ABSort`
  (with verified references to each tool's documented behavior);
  new `Architecture Decision Records` directory under `docs/adr/` with
  three ADRs covering the libcst parser choice (0001), the
  forward-reference barrier rule (0002), and the `stepdown` default
  strategy (0003).

- **Project rename**: clean-sort → pyreorder. New PyPI package name is
  `pyreorder` (the `clean-sort` name is unreservable due to PyPI's
  ultranormalization filter colliding with the existing `cleansort`
  project). The CLI command is `pyreorder` (short alias: `rord`); the
  import name is `pyreorder`; the source dir is `src/pyreorder/`; the
  config table is `[tool.pyreorder]`; the disable directive is
  `# pyreorder: off`. The skill is renamed from `clean-sort` to
  `pyreorder`. Legacy `csort.*` config/cache paths are auto-migrated by
  `pyreorder.migrate`; no other compatibility aliases are provided.

- **`runtime_setup` section**: Module-level assignments to non-constant names
  (``logger = get_logger(__name__)``, ``app = typer.Typer()``) now group into
  a new `runtime_setup` bucket (default order: after `module_constants`)
  instead of acting as barriers. An import below such a statement can now
  migrate up to the imports block. The forward-reference barrier is extended
  to cover `runtime_setup` assignments, preventing `NameError` for
  assignments that reference later-defined names.

- **`pyreorder config generate` subcommand**: produces a pyreorder.toml template from
  the current config schema. Supports `--output FILE` (must end in `.toml`),
  `--with-comments` (explanatory comments for each setting), and `--with-config
  FILE` (merges recognized values from an existing config; invalid/deprecated
  keys are dropped with warnings). The schema is now the single source of truth
  for recognized config keys. Replaces the old `pyreorder config init`.

- **Content-hash skip cache**: pyreorder now caches sorted-output hashes keyed by
  ``(config_signature, source_hash)``. On repeat runs, files whose content hash
  matches the cached sorted hash are skipped entirely (no parse, no sort).
  Default location: ``~/.cache/pyreorder/<project-slug>/cache.json``. Configurable
  via ``[cli] cache_dir``; disabled via ``[cli] cache = false`` or
  ``--no-cache``. Safe by construction: only skips files already in sorted
  state.

- **Parallel file processing**: pyreorder can sort files in parallel using a
  process pool (``parallel_backend = "process"``, default) or thread pool
  (``"thread"``). Configure via ``[cli] jobs`` (0 = serial, negative = auto
  ``int(0.75*cpu_count())``) or ``--jobs``/``-j`` per-invocation. Stdin mode
  always runs serially.

- **`[discovery]` config table**: Persistent file-discovery options previously
  only available as CLI flags. `exclude` (glob list, merged with `--exclude`
  flags) and `recursive` (bool, default `true`; `--no-recursive` overrides).

- **`--fail` / `--no-fail` CLI flag and `[cli] fail_on_changed` config**: Control whether
  `pyreorder run` exits non-zero when files are modified. Default remains exit 1 on change
  (pre-commit/CI friendly); `--no-fail` (or `[cli] fail_on_changed = false`) exits 0, useful
  when running pyreorder from a formatter task that always writes. `pyreorder check` is unaffected.

- **``from __future__ import annotations`` awareness**: When the module has
  ``from __future__ import annotations``, annotation-only names in
  ``AnnAssign`` are excluded from the forward-reference check, since
  annotations are not evaluated at runtime.

- Initial project structure from [copier-uv-plus](https://github.com/jr2804/copier-uv-plus).

### Fixed

- **Forward-reference barrier for module-level constants** (issue #1): A
  module-level constant whose RHS references a name defined in a later section
  (e.g. ``_DEFAULT_COLOR = Color.RED`` where ``Color`` is an enum) is now
  treated as a barrier — it stays in place rather than being hoisted to
  ``module_constants``. This prevents ``NameError`` at import time.
