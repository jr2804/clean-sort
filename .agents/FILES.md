# AGENTS.md — FILES

Single source of truth for paths, config keys, and naming conventions.
Kept compact — agents hallucinate less when they know where definitions live.

## Pattern

- One file owns each class of definition (paths, config defaults, enums).
- Import from that file. Never hard-code values in other modules.
- Variables that address files get `_file` suffix; directories get `_dir`.

## Project-specific sources of truth

| What | Where | Key names |
|------|-------|-----------|
| Public API | `src/pyreorder/__init__.py` | `sort_source`, `would_change`, `Config`, `load_config`, `discover`, `VALID_STRATEGIES` |
| Config model & discovery | `src/pyreorder/config.py` | `Config` (`sections`, `strategies`, `class_methods_*`, `classification`, `unknown_section`, `module`) |
| Section classification | `src/pyreorder/classify.py` | `imports`, `typing_imports`, `module_constants`, `enums`, `dataclasses`, `classes`, `functions`, `main_block`, `unknown_section` |
| In-section sorters | `src/pyreorder/sorters.py` | `alpha`, `dependency` (directions `stepdown`, `abstraction`) |
| Strategy set | `src/pyreorder/config.py` | `VALID_STRATEGIES` = {`keep`, `alpha`, `stepdown`, `abstraction`} |
| Pipeline (Module reorder) | `src/pyreorder/pipeline.py` | `SectionSorter` |
| In-class method sort | `src/pyreorder/undersort.py` | `MethodSorter` (project's own sorter) |
| CLI (Typer app) | `src/pyreorder/cli/app.py` | `run`, `check`, `diff`, `config` |
| Project config | `pyproject.toml` | `[tool.pyreorder]`, `[tool.pyreorder.module]`, `[tool.pyreorder.strategy]`, `[tool.pyreorder.class_methods]` |
| Tooling tasks | `.config/mise/` | `format`, `format-md`, `lint`, `typecheck`, `spell` |
| Type-checker config | `ty.toml` | `include` = `src`/`tests`; excludes the `tests/data` fixtures |
| Agent skill | `skills/pyreorder/SKILL.md` | references `config.md`, `sort_programmatically.py` |
