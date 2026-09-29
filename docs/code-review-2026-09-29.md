---
title: Code review — 2026-09-29
hide:
- feedback
- toc
---

# Code review — 2026-09-29

Automated review of the current `clean-sort` working tree at commit
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

- `src/clean_sort/pipeline.py` orchestrates the parse → classify → reorder →
  in-section-sort → render pipeline. Single entry point `sort_source`.
- `src/clean_sort/classify.py` owns section assignment and forward-reference
  barrier detection. The barrier rule is the load-bearing safety invariant
  (see ADR 0002).
- `src/clean_sort/sorters.py` exposes `alpha` and `dependency` (stepdown /
  abstraction). The dependency sort uses a topological pass on name
  references.
- `src/clean_sort/cache.py` owns the content-hash skip cache (see the
  Architecture page).
- `src/clean_sort/transforms.py` is the only stage that mutates code beyond
  reordering (`hoist_inline_imports`, `remove_type_checking`). Both default
  off.
- `src/clean_sort/config.py` is the single source of truth for recognized
  config keys; the `csort config generate` subcommand reads it.
- `src/clean_sort/undersort.py` (`MethodSorter`) provides in-class method
  ordering; the legacy `[tool.undersort]` table is honoured as a fallback.
