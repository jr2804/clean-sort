---
title: Section layout
---

## Section layout

`preorder` classifies every top-level statement into a _section_, then emits
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
| `runtime_setup`    | module-level assignments to non-constant names (`logger = ...`, `app = ...`) |
| `enums`            | classes whose base ends in `Enum` / `Flag`                     |
| `dataclasses`      | classes decorated `@dataclass`                                 |
| `classes`          | other `class` definitions                                      |
| `functions`        | top-level `def`                                                |
| `dunder_exports`   | assignments to configured dunder names (`__all__` by default)  |
| `main_block`       | `if __name__ == "__main__":`                                   |
| `other` (barrier)  | anything else — **never moved**                                |

A statement whose section is **not listed** in `module.sections` is also treated
as a barrier and kept in place.

### Default order

```toml
[tool.preorder.module]
sections = [
    "imports",
    "typing_imports",
    "module_constants",
    "runtime_setup",
    "enums",
    "dataclasses",
    "classes",
    "functions",
    "dunder_exports",
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

After `preorder run` (default `keep` strategy):

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

Statements `preorder` does not recognise — runtime setup such as
`app = typer.Typer()` or a module-level `setup()` call — become **barriers**.
Recognised statements only reorder _within_ the contiguous run between barriers,
so `preorder` never moves code across a statement it might depend on.

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

Use barriers (or a `# preorder: off` directive) whenever a top-level statement has
order-dependent side effects.

### Realistic examples

Five fully-formed sample modules live in `tests/data/`, each with an unsorted
input and committed sorted output. They demonstrate the section layout,
barriers, and strategies on real-world Python patterns:

```shell
preorder diff tests/data/web_service_unsorted.py     # stepdown + undersort
preorder diff tests/data/cli_app_unsorted.py          # the Typer barrier pattern
preorder diff tests/data/inventory_models_unsorted.py # alpha + rich undersort
```

See [Sorting modes](sorting-modes.md) for the full table of what each sample
demonstrates.
