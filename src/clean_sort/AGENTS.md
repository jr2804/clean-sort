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
- `undersort.py` (`MethodSorter`) reorders in-class methods; it is this project's own sorter, not an external tool.
- Opt-in import transforms (`transforms.py`) are the only transforms that mutate code beyond reordering:
  `hoist_inline_imports` and `remove_type_checking`. Both default off, run as a pre-pass before
  section sorting, and are potentially breaking (they change import timing).

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
