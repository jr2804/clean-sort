# AGENTS.md — src/clean_sort

## Purpose

Primary package: AST-based, deterministic Python module reorganization.

## Ownership

Core library code. Config and the Typer CLI also live here (`config.py`, `cli/app.py`).

## Local Contracts

- Sorting is read-only with respect to semantics: only statement _order_ changes, never code.
- Section order is defined by `Config.sections`; classification lives in `classify.py`.
- In-section strategy per section via `Config.strategies`: `keep` | `alpha` | `stepdown` | `abstraction`.
- Unrecognised top-level nodes land in `unknown_section` (default `other`) and act as barriers — never reordered.
- **Forward-reference barrier**: A module-level constant whose RHS references a name defined in a later
  section (e.g. ``_DEFAULT_COLOR = Color.RED`` where ``Color`` is an enum) is treated as a barrier —
  it stays in place rather than being hoisted to ``module_constants``. This prevents ``NameError`` at
  import time. When ``from __future__ import annotations`` is active, annotation-only names in
  ``AnnAssign`` are excluded from the check.
- `undersort.py` (`MethodSorter`) reorders in-class methods; it is this project's own sorter, not an external tool.
  Legacy users may still set `class_methods.order` and `class_methods.method_type_order` under a
  `[tool.undersort]` table (in `pyproject.toml`) or a top-level `[undersort]` table (in standalone
  configs); `Config.load` falls back to that when `[tool.csort.class_methods]` is absent. The CLI
  mirrors both knobs with `--class-methods-order` and `--method-type-order` on every command.
- Opt-in import transforms (`transforms.py`) are the only transforms that mutate code beyond reordering:
  `hoist_inline_imports` and `remove_type_checking`. Both default off, run as a pre-pass before
  section sorting, and are potentially breaking (they change import timing).
- `csort run` exits with code 1 when it modifies any file (pre-commit/CI friendly). This is governed
  by `Config.fail_on_changed` (default `True`), configurable via `[cli] fail_on_changed` and
  overridable per-invocation with `--fail` / `--no-fail`. `csort check` is unaffected and always
  exits 1 when files would change.
- File discovery is governed by `Config.exclude` (glob list) and `Config.recursive` (bool, default `True`),
  configurable via `[discovery]`. CLI `--exclude` patterns merge with (append to) the config list;
  `--no-recursive` overrides `recursive=true` per-invocation.
- **Content-hash skip cache**: csort caches the hash of sorted output keyed by ``(config_signature, source_hash)``.
  On repeat runs, files whose content hash matches the cached sorted hash are skipped entirely (no parse,
  no sort). Default location: ``~/.cache/csort/<project-slug>/cache.json``. Configurable via
  ``[cli] cache_dir``; disabled via ``[cli] cache = false`` or ``--no-cache``. The cache is safe by
  construction: it only skips files that are already in their sorted state.

## Work Guidance

- Add new sections/strategies by extending `DEFAULT_SECTIONS` / `VALID_STRATEGIES` and the classifier.
- Keep `sort_source` idempotent: re-running on already-sorted input changes nothing.

## Verification

- `uv run pytest src` (or the full suite)
- `uv run ruff check src tests`
- `uv run ty check src tests`
- `csort check src` — package files must already be sorted

## Child DOX Index

None yet (leaf package).
