---
title: "ADR 0003: stepdown as the default strategy"
---

# ADR 0003: stepdown as the default strategy

- **Status:** Accepted
- **Date:** 2026-09-29
- **Deciders:** Jan Reimes

## Context and problem statement

Within a configured section, statements have to be put in *some* order.
`preorder` offers four strategies:

- **`keep`** — preserve the original order.
- **`alpha`** — alphabetise by statement name.
- **`stepdown`** — callers before callees (top-down narrative).
- **`abstraction`** — callees before callers (bottom-up dependency
  layering).

The choice between `stepdown` and `abstraction` affects how readable the
file is. The other two are mostly lexical (`keep`) or alphabetical
(`alpha`) and don't depend on the dependency graph.

## Considered options

1. **`alpha` by default** — predictable, no surprises, no dependency
   analysis. The cost: alphabetical order in a `functions` section
   scatters related code. Readers have to scan past `def authenticate`
   to find `def authorize` because the auth pair is split by all the
   other `a`-prefixed functions in the module.
2. **`abstraction` by default** — bottom-up layering. Low-level helpers
   come first, the entry point comes last. The cost: a reader opening the
   file sees the implementation details before the high-level logic.
3. **`stepdown` by default** — top-down layering. The entry point (or the
   first thing the module does) comes first; helpers come below. The cost:
   a reader following a function's definition has to scroll down past
   every function that calls it.

## Decision outcome

Chosen option: **`stepdown`** is the default for `functions` and `classes`
sections. Rationale:

- The "new contributor opens the file" mental model is top-down. They
  want to see what the module does before they care about how it does it.
- `stepdown` matches the layout of well-edited prose and matches the
  [Structured Programming][structured] convention.
- `abstraction` is one config line away for codebases that prefer it
  (`Config.strategies.functions = "abstraction"`).

[structured]: https://en.wikipedia.org/wiki/Structured_programming

`alpha` remains available for sections where order does not matter (e.g.
`imports`, where Ruff / isort own that decision anyway). `keep` is the
fallback when dependency analysis cannot make progress — e.g. when the
section contains statements with no resolvable names.

## Interactions with the forward-reference barrier

A statement whose right-hand side references a name defined in a later
section is treated as a barrier (ADR 0002) and is not part of the
dependency graph that `stepdown` consults. This means `stepdown` only
orders statements whose forward references have already been resolved —
which is what we want.

A practical consequence: if you have a `Color` enum and a
`_DEFAULT_COLOR = Color.RED` constant in the same `module_constants`
section, the barrier rule keeps `_DEFAULT_COLOR` in place until `Color`
is defined. `stepdown` then orders the rest of the constants around
those two, but the barrier-pair stays put.

## Consequences

Positive:

- New readers see the high-level logic first.
- The strategy composes cleanly with the forward-reference barrier.
- Switching to `abstraction` is one config line; the choice is not
  encoded in the code.

Negative:

- `stepdown` requires a name-resolution pass. It is slightly slower than
  `alpha`, but the difference is negligible for module-sized inputs.
- Cyclical dependencies force `keep` to win within the cycle. This
  matches the safety model from ADR 0002.

Neutral:

- The choice between `stepdown` and `abstraction` is a matter of style.
  The default reflects a position; it does not constrain it.

## References

- `src/pyreorder/sorters.py::dependency` — the topological sort
  implementation.
- `src/pyreorder/config.py::Config.strategies` — per-section strategy
  configuration.
- [Sorting modes](../sorting-modes.md) — user-facing documentation of
  the four strategies.
