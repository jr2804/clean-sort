---
title: "ADR 0001: libcst for AST manipulation"
---

# ADR 0001: libcst for AST manipulation

- **Status:** Accepted
- **Date:** 2026-09-29
- **Deciders:** Jan Reimes

## Context and problem statement

`pyreorder` reads Python source, reorders top-level statements and class members,
and writes the file back. The tool needs an AST representation that:

- Survives a round-trip without changing formatting (quotes, parentheses,
  comments, whitespace inside expressions).
- Exposes enough node metadata to classify statements into sections.
- Runs on Python 3.11+ (matching the project's `requires-python`).

The candidate libraries are `ast`, `libcst`, `redbaron`, and `astroid`. Each
differs on the format-preservation axis, which is the load-bearing constraint
for a *reorder-only* tool.

## Considered options

1. **`libcst`** — Concrete Syntax Tree with full formatting preservation.
2. **`ast`** — Built-in Abstract Syntax Tree. Preserves no formatting.
3. **`redbaron`** — F-string preservation was historically flaky; project
   is no longer actively maintained.
4. **`astroid`** — Adds type-inference metadata; does not preserve formatting.

## Decision outcome

Chosen option: **libcst**. Reasons:

- Round-trip preservation lets `pyreorder` claim a safety property: a file that
  does not need reordering produces a byte-identical output. Users can run
  `pyreorder` on CI with a `--check` flag and trust that the only diffs are
  real reorders.
- `libcst` carries whitespace, parentheses, and trailing comments as
  *metadata* on each node, so we never lose them when transforming the
  tree.
- The library exposes a `CSTTransformer` API that visits the tree with
  `leave_*` callbacks, which fits the pipeline shape (one transformer per
  stage).

The trade-off is performance: `libcst` is slower than `ast` for pure parse,
and it holds the entire file in memory. For `pyreorder` this is acceptable
because (a) files are bounded by Python's import-graph in practice and
(b) the `cache.py` layer short-circuits unchanged files.

## Consequences

Positive:

- Byte-identical no-op output (testable in CI).
- Comments, decorators, and trailing commas survive reordering.
- `libcst.parse_module` failure is recoverable — we surface it as a parse
  error and leave the file untouched.

Negative:

- Slower than `ast` for the parse step.
- `libcst` requires Python ≥ 3.9; we already require 3.11+ so this is moot.

Neutral:

- We depend on a third-party package. A future Python version with a
  format-preserving parser would let us migrate, but no such parser exists
  yet in the standard library.

## References

- `src/pyreorder/pipeline.py` — the parse + render entry points.
- `tests/test_pipeline.py` — round-trip tests that assert byte-identical
  output for unchanged files.
- [libcst documentation](https://libcst.readthedocs.io/)
