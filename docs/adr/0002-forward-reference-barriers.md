---
title: "ADR 0002: Forward-reference barriers"
---

# ADR 0002: Forward-reference barriers

- **Status:** Accepted
- **Date:** 2026-09-29
- **Deciders:** Jan Reimes

## Context and problem statement

A naive section-based reorder can break a module. Consider:

```python
import logging
logger = logging.getLogger(__name__)

def setup():
    logger.info("starting")
```

If the `runtime_setup` section is configured to come after `imports`, the
constant assignment `logger = logging.getLogger(__name__)` moves with it,
and the file still works. But:

```python
import logging

def setup():
    logger.info("starting")

logger = logging.getLogger(__name__)
```

If `runtime_setup` is configured to come *before* `functions`, the naive
reorder produces:

```python
import logging
logger = logging.getLogger(__name__)

def setup():
    logger.info("starting")
```

That works. But:

```python
_DEFAULT_COLOR = Color.RED  # Color is defined further down

def make_default():
    return _DEFAULT_COLOR

class Color(enum.Enum):
    RED = 1
    GREEN = 2
```

If we hoist `_DEFAULT_COLOR` into the `module_constants` section ahead of
`Color`, the import order at runtime is `_DEFAULT_COLOR = Color.RED` →
`NameError: name 'Color' is not defined`.

`csort` needs a rule that says *when not to move a statement*.

## Considered options

1. **No barriers** — always reorder. Breaks forward references. Rejected.
2. **Acyclic-dependency topological sort (like `ssort`)** — sound, but
   refuses to reorder code with cycles, and Python modules routinely have
   cycles via `TYPE_CHECKING` imports and runtime-rebound names.
3. **Forward-reference detection per statement** — keep a statement in
   place if its right-hand side names a value defined in a later section.
   Conservative: only moves code we can prove is safe to move.

## Decision outcome

Chosen option: **3 — forward-reference detection per statement**.

The implementation lives in `classify.py` and is consulted from
`pipeline.SectionSorter`. For each module-level assignment whose right-hand
side references a name defined in a later configured section, the
assignment is treated as a *barrier*: it stays in its original position,
and the surrounding barrier-free run of movable statements is reordered
around it.

A side effect of barriers is that any statement we **cannot classify** is
also treated as a barrier. This is by design — `csort`'s stance is "leave
unfamiliar code alone". The cost is occasional modules with strange
top-level statements (third-party decorators, runtime-generated class
attributes) that never move; the benefit is that `csort` is safe to run on
a codebase it has never seen.

## Edge case: `from __future__ import annotations`

When `from __future__ import annotations` is active, annotations are
strings and are not evaluated at runtime. Names that appear *only* in
`AnnAssign` targets should not trigger the forward-reference barrier.

The implementation excludes annotation-only names from the barrier check
when the future import is present. See
`_has_forward_ref` in `classify.py` and the test in
`tests/test_classify.py::test_forward_ref_barrier_with_future_annotations`.

## Consequences

Positive:

- `csort` is safe to run on a module it has never seen.
- Cycle tolerance: forward-reference detection handles cyclical
  module-level references by leaving the cycle in place.

Negative:

- The check is conservative — there are cases where a statement *could*
  safely move because the runtime evaluation order is benign, but `csort`
  will not move it. Users can split the assignment or use
  `Config.sections` to opt the statement into a fixed section.

Neutral:

- The barrier rule interacts with `runtime_setup`: see ADR 0003 for the
  carve-out that puts `app = typer.Typer()` ahead of functions.

## References

- `src/clean_sort/classify.py::classify`, `_has_forward_ref`,
  `_is_runtime_setup_assignment`.
- `src/clean_sort/pipeline.py::SectionSorter.leave_Module`.
- `tests/test_classify.py` — forward-reference barrier tests.
