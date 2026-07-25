# Configuration & classification reference

## Config discovery

Searched in order (first match wins, walking up from the target file's
directory):

1. `--config PATH` (explicit)
2. `csort.toml`
3. `.config/csort.toml`
4. `[tool.csort]` in `pyproject.toml`

`[tool.undersort]` (in `pyproject.toml`) is read as a fallback for
`class_methods.order` / `class_methods.method_type_order` when
`[tool.csort.class_methods]` is absent.

## Schema

| table            | key                 | type / values                                    |
| ---------------- | ------------------- | ------------------------------------------------ |
| `module`         | `sections`          | list of section names (ordered)                  |
| `strategy`       | `<section>`         | `keep` \| `alpha` \| `stepdown` \| `abstraction` |
| `class_methods`  | `enabled`           | bool                                             |
| `class_methods`  | `order`             | permutation of `public, protected, private`      |
| `class_methods`  | `method_type_order` | permutation of `instance, class, static`         |
| `classification` | `constants_pattern` | regex (default `^[A-Z_][A-Z0-9_]*$`)             |

## Section classification (top-level statements)

| section            | matches                                                        |
| ------------------ | -------------------------------------------------------------- |
| `imports`          | `import`, `from ... import` (except `from __future__`)         |
| `typing_imports`   | `if TYPE_CHECKING:` block                                      |
| `module_constants` | assignments to `ALL_CAPS` or dunder (`__all__`, `__version__`) |
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

- File: a `# csort: off` or `# nosort` comment in the module header → file skipped.
- Class: `class C:  # csort: off` (trailing) → that class's methods untouched.
