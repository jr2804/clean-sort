---
title: Code review — 2026-09-29
hide:
- feedback
- toc
---

# Code review — 2026-09-29

Automated review of the current `pyreorder` working tree at commit
`72c33b3` (the docs-additions commit on `main`). This report captures
the state of the code at that commit, not a proposed change set.

## Tool availability

| Tool | Status | Notes |
|---|---|---|
| `ruff` | (run `mise run lint` to populate) | Linter / formatter |
| `ty` | (run `mise run lint` to populate) | Type checker |
| `pytest` | (run `mise run test` to populate) | Test runner |
| `codespell` | (run `mise run spell` to populate) | Spell checker |

## Findings (placeholder)

Run the following locally to populate:

```bash
mise install
mise run lint   # ruff + ty + rumdl + codespell
mise run test   # pytest --cov
```

The results will be appended below.

## Static observations (read of the code, no execution)

- `src/pyreorder/pipeline.py` orchestrates the parse → classify → reorder →
  in-section-sort → render pipeline. Single entry point `sort_source`.
- `src/pyreorder/classify.py` owns section assignment and forward-reference
  barrier detection. The barrier rule is the load-bearing safety invariant
  (see ADR 0002).
- `src/pyreorder/sorters.py` exposes `alpha` and `dependency` (stepdown /
  abstraction). The dependency sort uses a topological pass on name
  references.
- `src/pyreorder/cache.py` owns the content-hash skip cache (see the
  Architecture page).
- `src/pyreorder/transforms.py` is the only stage that mutates code beyond
  reordering (`hoist_inline_imports`, `remove_type_checking`). Both default
  off.
- `src/pyreorder/config.py` is the single source of truth for recognized
  config keys; the `preorder config generate` subcommand reads it.
- `src/pyreorder/undersort.py` (`MethodSorter`) provides in-class method
  ordering; the legacy `[tool.undersort]` table is honoured as a fallback.

## File inventory

| Path | Lines | Notes |
|---|---|---|
| `src/pyreorder/pipeline.py` | 170 | |
| `src/pyreorder/classify.py` | 322 | |
| `src/pyreorder/sorters.py` | 103 | |
| `src/pyreorder/config.py` | 608 | |
| `src/pyreorder/cache.py` | 135 | |
| `src/pyreorder/transforms.py` | 799 | |
| `src/pyreorder/undersort.py` | 153 | |
| `src/pyreorder/__init__.py` | 35 | |
| `src/pyreorder/__main__.py` | 8 | |
| `src/pyreorder/cli/app.py` | 792 | |

## Test inventory

| Path | Lines | Notes |
|---|---|---|
| `tests/test_cache.py` | 185 | |
| `tests/test_classify.py` | 96 | |
| `tests/test_cli.py` | 496 | |
| `tests/test_config.py` | 257 | |
| `tests/test_data.py` | 125 | |
| `tests/test_pipeline.py` | 448 | |
| `tests/test_transforms.py` | 515 | |
| `tests/test_undersort.py` | 336 | |

## Public surface per module

### pipeline.py

```python
class SectionSorter(cst.CSTTransformer):
def _strip_leading_blanks(nodes: list[cst.CSTNode]) -> tuple[cst.CSTNode, ...]:
def sort_source(source: str, cfg: Config, *, filename: str = "<unknown>") -> str:
def would_change(source: str, cfg: Config, *, filename: str = "<unknown>") -> bool:
```

### classify.py

```python
class ClassifyContext:
def is_module_docstring(node: cst.CSTNode) -> bool:
def is_future_import(node: cst.CSTNode) -> bool:
def classify(node: cst.CSTNode, cfg, *, ctx: ClassifyContext | None = None) -> str:  # noqa: ANN001, PLR0911 - duck-typed Config
def _is_main_guard(if_node: cst.If) -> bool:
def _is_type_checking(if_node: cst.If) -> bool:
def _is_enum(class_node: cst.ClassDef) -> bool:
def _is_dataclass(class_node: cst.ClassDef) -> bool:
def has_future_annotations(module: cst.Module) -> bool:
def module_top_level_names(body: Sequence[cst.CSTNode]) -> dict[str, int]:
```

### sorters.py

```python
def alpha(nodes: list[cst.CSTNode]) -> list[cst.CSTNode]:
def dependency(nodes: list[cst.CSTNode], direction: str) -> list[cst.CSTNode]:
```

## Coverage gate

Configured:

```toml
    "pytest-cov>=5.0.0",
[tool.pytest-cov]
addopts = "--cov=pyreorder --cov-report=term-missing --cov-report=html --cov-report=xml"
fail_under = 90
```

## What to run when mise is available

```bash
mise install
mise run lint
mise run test
```

Append the actual output below when those commands finish.
