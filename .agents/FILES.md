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
| Public API | `src/clean_sort/__init__.py` | `sort_source`, `would_change`, `Config`, `load_config`, `discover`, `VALID_STRATEGIES` |
| Config model & discovery | `src/clean_sort/config.py` | `Config` (`sections`, `strategies`, `class_methods_*`, `classification`, `unknown_section`, `module`) |
| Section classification | `src/clean_sort/classify.py` | `imports`, `typing_imports`, `module_constants`, `enums`, `dataclasses`, `classes`, `functions`, `main_block`, `unknown_section` |
| In-section sorters | `src/clean_sort/sorters.py` | `alpha`, `dependency` (directions `stepdown`, `abstraction`) |
| Strategy set | `src/clean_sort/config.py` | `VALID_STRATEGIES` = {`keep`, `alpha`, `stepdown`, `abstraction`} |
| Pipeline (Module reorder) | `src/clean_sort/pipeline.py` | `SectionSorter` |
| In-class method sort | `src/clean_sort/undersort.py` | `MethodSorter` (project's own sorter) |
| CLI (Typer app) | `src/clean_sort/cli/app.py` | `run`, `check`, `diff`, `config` |
| Project config | `pyproject.toml` | `[tool.csort]`, `[tool.csort.module]`, `[tool.csort.strategy]`, `[tool.csort.class_methods]` |
| Tooling tasks | `.config/mise/` | `format`, `format-md`, `lint`, `typecheck`, `spell` |
| Agent skill | `skills/clean-sort/SKILL.md` | references `config.md`, `sort_programmatically.py` |
