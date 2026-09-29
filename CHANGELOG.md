# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- **Documentation overhaul**: New `Architecture` page with two Mermaid
  pipeline diagrams (per-stage data flow and per-file work decomposition);
  new `Comparison with other tools` page positioning `preorder` against
  `isort`, Ruff `I001`, `undersort`, `ssort`, `sdsort`, and `ABSort`
  (with verified references to each tool's documented behavior);
  new `Architecture Decision Records` directory under `docs/adr/` with
  three ADRs covering the libcst parser choice (0001), the
  forward-reference barrier rule (0002), and the `stepdown` default
  strategy (0003).


- **Project rename**: clean-sort → pyreorder. New PyPI package name is
  `pyreorder` (the `clean-sort` name is unreservable due to PyPI's
  ultranormalization filter colliding with the existing `cleansort`
  project). The CLI command is now `preorder`; the import name is
  `pyreorder`; the source dir is `src/pyreorder/`. The skill is renamed
  from `clean-sort` to `pyreorder`. The legacy `[tool.csort]` config
  table is still honoured as a back-compat alias for `[tool.preorder]`.

- **`runtime_setup` section**: Module-level assignments to non-constant names
  (``logger = get_logger(__name__)``, ``app = typer.Typer()``) now group into
  a new `runtime_setup` bucket (default order: after `module_constants`)
  instead of acting as barriers. An import below such a statement can now
  migrate up to the imports block. The forward-reference barrier is extended
  to cover `runtime_setup` assignments, preventing `NameError` for
  assignments that reference later-defined names.

- **`preorder config generate` subcommand**: produces a preorder.toml template from
  the current config schema. Supports `--output FILE` (must end in `.toml`),
  `--with-comments` (explanatory comments for each setting), and `--with-config
  FILE` (merges recognized values from an existing config; invalid/deprecated
  keys are dropped with warnings). The schema is now the single source of truth
  for recognized config keys. Replaces the old `preorder config init`.

- **Content-hash skip cache**: preorder now caches sorted-output hashes keyed by
  ``(config_signature, source_hash)``. On repeat runs, files whose content hash
  matches the cached sorted hash are skipped entirely (no parse, no sort).
  Default location: ``~/.cache/preorder/<project-slug>/cache.json``. Configurable
  via ``[cli] cache_dir``; disabled via ``[cli] cache = false`` or
  ``--no-cache``. Safe by construction: only skips files already in sorted
  state.

- **Parallel file processing**: preorder can sort files in parallel using a
  process pool (``parallel_backend = "process"``, default) or thread pool
  (``"thread"``). Configure via ``[cli] jobs`` (0 = serial, negative = auto
  ``int(0.75*cpu_count())``) or ``--jobs``/``-j`` per-invocation. Stdin mode
  always runs serially.

- **`[discovery]` config table**: Persistent file-discovery options previously
  only available as CLI flags. `exclude` (glob list, merged with `--exclude`
  flags) and `recursive` (bool, default `true`; `--no-recursive` overrides).

- **`--fail` / `--no-fail` CLI flag and `[cli] fail_on_changed` config**: Control whether
  `preorder run` exits non-zero when files are modified. Default remains exit 1 on change
  (pre-commit/CI friendly); `--no-fail` (or `[cli] fail_on_changed = false`) exits 0, useful
  when running preorder from a formatter task that always writes. `preorder check` is unaffected.

### Fixed

- **Forward-reference barrier for module-level constants** (issue #1): A
  module-level constant whose RHS references a name defined in a later section
  (e.g. ``_DEFAULT_COLOR = Color.RED`` where ``Color`` is an enum) is now
  treated as a barrier — it stays in place rather than being hoisted to
  ``module_constants``. This prevents ``NameError`` at import time.

### Added

- **``from __future__ import annotations`` awareness**: When the module has
  ``from __future__ import annotations``, annotation-only names in
  ``AnnAssign`` are excluded from the forward-reference check, since
  annotations are not evaluated at runtime.

- Initial project structure from [copier-uv-plus](<https://github.com/Jan> Reimes/copier-uv-plus).
