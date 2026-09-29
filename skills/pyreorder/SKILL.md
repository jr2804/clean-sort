---
name: pyreorder
description: pyreorder (`preorder`) is an AST/CST-based structural sorter for Python source code. Use when the user wants to "sort", "reorder", "organize", or "clean up" the structure of Python files — grouping imports, constants, enums, dataclasses, classes, functions, and the `if __name__ == "__main__"` block into a canonical order; alphabetising or dependency-ordering functions (step-down rule); or reordering class methods by visibility (public/protected/private) and type (instance/class/static) like undersort. Triggers include "sort this module", "organize my python code", "put imports at the top", "step-down order my functions", "undersort this class", "sort methods by visibility", or running `preorder`. Prefer over manual reordering or over isort/ruff when the goal is *structural* (statement-level) ordering rather than import-only or formatting.
---

# pyreorder (`preorder`)

`preorder` reorders the **top-level statements** of a Python module into a
configurable section order and the **methods within each class** by visibility
and type. It is built on `libcst`, so comments and formatting are preserved. It
is a _structural_ sorter — it complements `ruff`/`isort` (imports) and `black`
(formatting), it does not replace them.

## Install

```shell
uv tool install pyreorder                 # or: git+https://codeberg.org/jr2804/pyreorder
preorder --version
```

## When to use

- A module has scattered imports, constants, classes, functions and you want a
  canonical layout.
- You want functions ordered by the **step-down rule** (caller before callee) or
  low-level-utilities-first (**abstraction**).
- You want class methods grouped public → protected → private, instance → class
  → static (undersort semantics).
- CI / pre-commit gate: `preorder check` exits non-zero if files aren't sorted.

Do **not** use preorder for import-only sorting (use `ruff`/`isort`) or for
formatting (use `ruff format`/`black`). preorder composes with both — run it
_after_ formatters.

## CLI

```shell
preorder run [PATHS...]            # sort in place (use `-` for stdin -> stdout)
preorder check [PATHS...]          # exit 1 if any file would change (CI / pre-commit)
preorder diff [PATHS...]           # print unified diffs
preorder config generate [--output FILE] [--with-comments] [--with-config FILE]  # produce a config template (merge from existing)
preorder config show               # print resolved config
preorder --version
```

Common options: `--config PATH`, `--exclude/-x GLOB`, `--no-recursive`,
`--no-class-methods`, `--section-only SECTIONS`, `--strategy-overrides OVERRIDES`,
`--hoist-inline-imports`, `--remove-type-checking`.

```shell
# editor / pre-commit friendly:
preorder run - < module.py > sorted.py
```

## Configuration

Discovered from (first wins, walking up): `--config`, `preorder.toml`,
`.config/preorder.toml`, `[tool.preorder]` in `pyproject.toml`. `[tool.undersort]` is
read for backwards-compatibility class-method ordering.

```toml
[module]
sections = ["imports", "typing_imports", "module_constants", "enums",
            "dataclasses", "classes", "functions", "dunder_exports", "main_block"]

[strategy]            # per-section in-section strategy; omit => "keep"
enums = "alpha"
functions = "stepdown"   # or "alpha" | "abstraction" | "keep"

[class_methods]       # undersort-style method ordering within each class
enabled = true
order = ["public", "protected", "private"]
method_type_order = ["instance", "class", "static"]
```

### Strategies

| value         | meaning                                          | safe for           |
| ------------- | ------------------------------------------------ | ------------------ |
| `keep`        | preserve original order (default)                | everything         |
| `alpha`       | alphabetical by primary name                     | imports, enums     |
| `stepdown`    | caller before callee (top-down narrative)        | functions, classes |
| `abstraction` | callee before caller (low-level utilities first) | functions, classes |

> **Caution:** `alpha` on `module_constants`/`classes`/`dataclasses` can break
> runtime order (constants that reference each other; inheritance). Always
> preview with `preorder diff` before applying.

## Safety model

preorder is conservative:

- **Barriers:** statements that don't map to a configured section (e.g.
  `app = typer.Typer()`, runtime setup) are never moved. Recognised statements
  only reorder _within_ their contiguous barrier-free run, so preorder never moves
  code across a statement it might depend on.
- **Pinned:** the module docstring and `from __future__ import ...` always stay
  first.
- **Opt-out:** a `# preorder: off` (or `# nosort`) comment in a file's header
  skips the file; the same comment on a class trailing line
  (`class C:  # preorder: off`) skips that class.
- **Idempotent:** running `preorder` twice never changes a file a second time.

## Opt-in import transforms

Two transforms go beyond reordering — they **mutate import statements** to fix
common antipatterns. Both are **off by default** and **potentially breaking**
(they change import timing). Enable them via CLI flags or `[transforms]` in
config.

### Hoist inline imports (`--hoist-inline-imports`)

Moves `import`/`from ... import` statements nested inside function bodies to the
top of the module. This fixes Ruff's `PLC0415` ("Import outside top-level") —
inline imports bury dependencies and make the module's dependency graph unclear.

```python
# BEFORE                          # AFTER (--hoist-inline-imports)
def _load():                      import json
    import json                   def _load():
    return json.loads(data)           return json.loads(data)
```

Duplicate imports from multiple functions are deduplicated. Imports inside
nested functions, `if`/`try`/`with` blocks, or class bodies are left in place.

Any `# noqa` linter-exclusion comment on a hoisted import is automatically
stripped — the suppression was only justified by the inline location.

### Remove TYPE_CHECKING (`--remove-type-checking`)

Deletes `if TYPE_CHECKING:` guards, de-indents the imports they contained, and
hoists them to the top. If `TYPE_CHECKING` was imported from `typing` and is now
unused, that import is cleaned up too.

`TYPE_CHECKING` guards diverge runtime from type-checker behaviour: guarded
imports never run, yet type checkers treat them as if they do. Modern Python
(`from __future__ import annotations`, PEP 563) makes them unnecessary.

```python
# BEFORE                          # AFTER (--remove-type-checking)
from typing import TYPE_CHECKING  import http.client
if TYPE_CHECKING:
    import http.client
```

If the `TYPE_CHECKING` block contains non-import statements (runtime code), the
block is left untouched for safety.

Any `# noqa` linter-exclusion comment on a dissolved import is automatically
stripped — the suppression was only justified by the TYPE_CHECKING guard.

## Programmatic API

```python
from pyreorder import sort_source, Config

cfg = Config(strategies={"functions": "stepdown"})
sorted_text = sort_source(source_text, cfg)
```

See `scripts/sort_programmatically.py` for a runnable example,
`references/` for the full config/classification reference, and `assets/` for a
sample file and config template.

Five realistic, fully-formed example modules (each with unsorted input and
committed sorted output) live in `tests/data/` and demonstrate every strategy:

| Sample             | Strategy      | What it shows                                           |
| ------------------ | ------------- | ------------------------------------------------------- |
| `web_service`      | `stepdown`    | enums, dataclasses, retry client, undersort on a class  |
| `csv_pipeline`     | `stepdown`    | runtime barriers (validator registry), `TYPE_CHECKING`  |
| `cli_app`          | `keep`        | the `app = typer.Typer()` barrier pattern               |
| `plugin_registry`  | `abstraction` | callee-first ordering in a plugin/middleware system     |
| `inventory_models` | `alpha`       | alpha on enums + functions, rich undersort in one class |

```shell
preorder diff tests/data/plugin_registry_unsorted.py
preorder diff tests/data/inventory_models_unsorted.py
```
