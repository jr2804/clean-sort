---
title: Section layout
---

## Section layout

`csort` classifies every top-level statement into a *section*, then emits
sections in a fixed order. Within a section, statements are ordered by the
section's [strategy](sorting-modes.md). The result is a predictable,
readable module shape: imports first, constants before classes, helpers near
the bottom, and the `main` guard last.

### How statements are classified

| Section            | Matches                                                        |
| ------------------ | -------------------------------------------------------------- |
| `imports`          | `import`, `from ... import` (except `from __future__`)         |
| `typing_imports`   | `if TYPE_CHECKING:` block                                      |
| `module_constants` | assignments to `ALL_CAPS` or dunder (`__all__`, `__version__`) |
| `enums`            | classes whose base ends in `Enum` / `Flag`                     |
| `dataclasses`      | classes decorated `@dataclass`                                 |
| `classes`          | other `class` definitions                                      |
| `functions`        | top-level `def`                                                |
| `main_block`       | `if __name__ == "__main__":`                                   |
| `other` (barrier)  | anything else — **never moved**                                |

A statement whose section is **not listed** in `module.sections` is also treated
as a barrier and kept in place.

### Default order

```toml
[tool.csort.module]
sections = [
    "imports",
    "typing_imports",
    "module_constants",
    "enums",
    "dataclasses",
    "classes",
    "functions",
    "main_block",
]
```

### Worked example: constants above classes

Before:

```python
class Service:
    def start(self):
        ...

MAX_CONN = 10
API_URL = "https://example.com"

import os
```

After `csort run` (default `keep` strategy):

```python
import os

MAX_CONN = 10
API_URL = "https://example.com"

class Service:
    def start(self):
        ...
```

Imports float to the top, module constants sit above the class, and the class
moves below the constants — exactly the "constants above classes" ordering the
layout guarantees.

### Pinned statements

Two things are never reordered, even if they appear out of place:

- the **module docstring**, and
- `from __future__ import ...` statements (these must stay at the very top of
  the module to be valid Python).

### Barriers

Statements `csort` does not recognise — runtime setup such as
`app = typer.Typer()` or a module-level `setup()` call — become **barriers**.
Recognised statements only reorder *within* the contiguous run between barriers,
so `csort` never moves code across a statement it might depend on.

Before (a barrier splits the functions):

```python
def bootstrap():
    ...

app = typer.Typer()          # barrier: not a recognised section

def handler():
    ...

def helper():
    ...
```

After: `bootstrap` stays above the barrier; `handler` and `helper` reorder
among themselves below it, but nothing crosses the `app = ...` line.

```python
def bootstrap():
    ...

app = typer.Typer()          # barrier: unchanged, never crossed

def handler():
    ...

def helper():
    ...
```

Use barriers (or a `# csort: off` directive) whenever a top-level statement has
order-dependent side effects.
