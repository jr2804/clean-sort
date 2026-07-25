---
title: Configuration
---

## Configuration

`csort` is configured with a small TOML schema. The same schema is read from a
standalone `csort.toml`, a `.config/csort.toml`, or a `[tool.csort]` table in
`pyproject.toml`. A minimal config needs no file at all — the defaults below
already produce a canonical layout.

### Discovery order

When `csort` processes a file it searches for configuration, **first match
wins**, walking up from the file's own directory:

1. `--config PATH` passed on the command line (explicit path).
2. `csort.toml` in the current / target directory.
3. `.config/csort.toml`.
4. `[tool.csort]` table inside `pyproject.toml`.

If no configuration is found, built-in defaults are used.

> ### Legacy `[tool.undersort]`
>
> For backwards compatibility, `class_methods.order` and
> `class_methods.method_type_order` are read from a `[tool.undersort]` table
> when `[tool.csort.class_methods]` is absent. Prefer `[tool.csort]`.

### Schema

| Table            | Key                 | Type / values                                    |
| ---------------- | ------------------- | ------------------------------------------------ |
| `module`         | `sections`          | ordered list of section names                    |
| `strategy`       | `<section>`         | `keep` \| `alpha` \| `stepdown` \| `abstraction` |
| `class_methods`  | `enabled`           | `bool`                                           |
| `class_methods`  | `order`             | permutation of `public`, `protected`, `private`  |
| `class_methods`  | `method_type_order` | permutation of `instance`, `class`, `static`     |
| `classification` | `constants_pattern` | regex (default `^[A-Z_][A-Z0-9_]*$`)             |

Any value of `sections` that is **not** a recognised section name acts as a
barrier (see [Section layout](section-layout.md)).

### Examples

#### Minimal: defaults only

No file required. `csort` uses the canonical section order and `keep` strategy
everywhere except `enums`, which default to `alpha`.

#### Recommended starting point

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

[tool.csort.strategy]
enums = "alpha"
# functions = "stepdown"   # caller before callee (top-down narrative)
# classes = "keep"

[tool.csort.class_methods]
enabled = true
order = ["public", "protected", "private"]
method_type_order = ["instance", "class", "static"]
```

#### Per-section strategy overrides

Set a strategy only for the sections you care about. Omitted sections keep
their original order (`keep`).

```toml
[tool.csort.strategy]
enums = "alpha"
functions = "stepdown"
classes = "abstraction"
```

#### Customising constant detection

By default a top-level assignment is treated as a _module constant_ when its
target matches `^[A-Z_][A-Z0-9_]*$` (e.g. `MAX_CONN`, `__version__`). Change the
pattern to widen or narrow it:

```toml
[tool.csort.classification]
constants_pattern = "^[A-Z][A-Z0-9_]*$"
```

### Command-line overrides

Two flags let you deviate from the file config without editing it:

| Flag                   | Effect                                                     |
| ---------------------- | ---------------------------------------------------------- |
| `--section-only`       | Restrict reordering to the given comma-separated sections. |
| `--strategy-overrides` | Override per-section strategy, e.g. `functions=alpha`.     |

```shell
# Only reorder the functions section, using step-down ordering:
csort run src/ --section-only functions --strategy-overrides functions=stepdown

# Restrict to several sections; each reorders independently:
csort run src/ --section-only functions,classes --strategy-overrides functions=stepdown,classes=keep
```

These map onto `Config.sections` and `Config.strategies` respectively and are
resolved on top of the discovered file config.

### Opt-out directives

- **Whole file:** a `# csort: off` (or `# nosort`) comment anywhere in the
  module header skips the file entirely.
- **Single class:** `class C:  # csort: off` leaves that class's methods
  untouched.

### Programmatic configuration

```python
from clean_sort import Config, sort_source

cfg = Config(
    strategies={"functions": "stepdown", "enums": "alpha"},
    class_methods={"enabled": True, "order": ["public", "protected", "private"]},
)
sorted_text = sort_source(source_text, cfg)
```

See the [API reference](reference/api.md) for the full `Config` surface.
