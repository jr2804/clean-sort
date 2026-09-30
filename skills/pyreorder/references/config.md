# Configuration & classification reference

## Config discovery

Searched in order (first match wins, walking up from the target file's
directory):

1. `--config PATH` (explicit)
2. `pyreorder.toml`
3. `.config/pyreorder.toml`
4. `[tool.pyreorder]` in `pyproject.toml`

`[tool.undersort]` (in `pyproject.toml`) is read as a fallback for
`class_methods.order` / `class_methods.method_type_order` when
`[tool.pyreorder.class_methods]` is absent.

## Schema

| table            | key                    | type / values                                    |
| ---------------- | ---------------------- | ------------------------------------------------ |
| `module`         | `sections`             | list of section names (ordered)                  |
| `strategy`       | `<section>`            | `keep` \| `alpha` \| `stepdown` \| `abstraction` |
| `class_methods`  | `enabled`              | bool                                             |
| `class_methods`  | `order`                | permutation of `public, protected, private`      |
| `class_methods`  | `method_type_order`    | permutation of `instance, class, static`         |
| `classification` | `constants_pattern`    | regex (default `^[A-Z_][A-Z0-9_]*$`)             |
| `classification` | `dunder_exports_names` | list of dunder names (default `["__all__"]`)     |
| `transforms`     | `hoist_inline_imports` | bool (default `false`)                           |
| `transforms`     | `remove_type_checking` | bool (default `false`)                           |

## Section classification (top-level statements)

| section            | matches                                                        |
| ------------------ | -------------------------------------------------------------- |
| `imports`          | `import`, `from ... import` (except `from __future__`)         |
| `typing_imports`   | `if TYPE_CHECKING:` block                                      |
| `module_constants` | assignments to `ALL_CAPS` or dunder (except `dunder_exports_names`) |
| `dunder_exports`   | assignments to configured dunder names (`__all__` by default) |
| `enums`            | classes whose base ends in `Enum`/`Flag`                       |
| `dataclasses`      | classes decorated `@dataclass`                                 |
| `classes`          | other `class` definitions                                      |
| `functions`        | top-level `def`                                                |
| `main_block`       | `if __name__ == "__main__":`                                   |
| `other` (barrier)  | anything else — **never moved**                                |

A statement whose section is not listed in `module.sections` is also treated as
a barrier (kept in place).

## Strategies

- **keep** — original order (default).
- **alpha** — stable alphabetical by primary name (function/class name, import
  module, constant target). Safe for imports/enums; risky for interdependent
  constants/classes.
- **stepdown** — topological order, **caller before callee** (the Clean Code
  step-down rule). Functions/classes only.
- **abstraction** — reverse of stepdown, **callee before caller** (low-level
  utilities first). Functions/classes only.

`stepdown`/`abstraction` fall back to `alpha` on other sections. Cycles keep
their original relative order.

## In-class method order (undersort)

Methods are grouped by `(visibility, method_type)` in the configured order,
stable within each group. Non-method statements keep their leading/trailing
position. Visibility: `public` (no underscore, and dunders like `__init__`),
`protected` (`_x`), `private` (`__x` non-dunder). Method type is derived from
`@classmethod` / `@staticmethod` decorators (else `instance`).

## Opt-out directives

- File: a `# pyreorder: off` or `# nosort` comment in the module header → file skipped.
- Class: `class C:  # pyreorder: off` (trailing) → that class's methods untouched.

## Opt-in import transforms (`[transforms]`)

Both transforms are **off by default** and **potentially breaking** (they change
import timing). They run as a pre-pass before section sorting, so hoisted
imports land in the `imports` bucket and get sorted with the rest.

### `hoist_inline_imports` (default `false`)

Moves `import`/`from ... import` statements nested directly inside function
bodies to the top of the module. Fixes Ruff `PLC0415` ("Import outside
top-level") — inline imports bury dependencies and make the module's dependency
graph unclear.

```toml
[transforms]
hoist_inline_imports = true
```

Behaviour:

- Only imports that are _direct children_ of a function body are hoisted.
- Imports inside nested functions, `if`/`try`/`with` blocks, or class bodies
  are left in place.
- Duplicate imports from multiple functions are deduplicated.
- `# noqa` linter-exclusion comments on hoisted imports are automatically
  stripped — the suppression was only justified by the inline location.

### `remove_type_checking` (default `false`)

Deletes `if TYPE_CHECKING:` guards, de-indents the imports they contained, and
hoists them to the top. If `TYPE_CHECKING` was imported from `typing` and is
now unused, that import is cleaned up too. `TYPE_CHECKING` guards diverge
runtime from type-checker behaviour; modern Python makes them unnecessary.

```toml
[transforms]
remove_type_checking = true
```

Behaviour:

- Handles both `if TYPE_CHECKING:` and `if typing.TYPE_CHECKING:` forms.
- If the block contains non-import statements (runtime code), it is left
  untouched for safety.
- `from typing import TYPE_CHECKING` is removed if unused after dissolution;
  other names imported from the same line are preserved.
- `# noqa` linter-exclusion comments on dissolved imports are automatically
  stripped — the suppression was only justified by the TYPE_CHECKING guard.
