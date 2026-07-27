---
title: Sorting modes
---

## Sorting modes

Each section is ordered by a _strategy_. Set it per section under
`[tool.csort.strategy]`, or override on the fly with
`--strategy-overrides`. Four strategies exist:

| Value         | Meaning                                          | Applies to                |
| ------------- | ------------------------------------------------ | ------------------------- |
| `keep`        | Preserve original order (default)                | any section               |
| `alpha`       | Stable alphabetical by primary name              | imports, enums, constants |
| `stepdown`    | Caller before callee (top-down narrative)        | functions, classes        |
| `abstraction` | Callee before caller (low-level utilities first) | functions, classes        |

`stepdown` / `abstraction` only make sense for functions and classes; applied
to other sections they fall back to `alpha`. Cycles keep their original relative
order.

### `keep`

The default. Statements stay exactly where you wrote them; `csort` only moves
them between sections, never reorders within one.

### `alpha`

Stable alphabetical ordering by the statement's primary name — the import
module, the enum/class name, or the constant target.

```python
# before
def zebra():
    ...
def apple():
    ...
def mango():
    ...

# after (alpha)
def apple():
    ...
def mango():
    ...
def zebra():
    ...
```

> ### Caution
>
> `alpha` is safe for `imports` and `enums`, but reordering interdependent
> `module_constants` or `classes` (inheritance, forward references) can raise
> `NameError` / `MRO` errors at runtime. Always preview with `csort diff`
> before committing an `alpha` reordering of constants or classes.

### `stepdown` — caller before callee

The _Clean Code_ step-down rule: a caller appears **above** the functions it
calls, giving a top-down reading order.

```python
# before
def greet(name):
    print(f"hi {name}")

def main():
    greet("world")

def helper():
    ...

# after (functions = "stepdown")
def main():          # top-level caller first
    greet("world")

def greet(name):     # called by main
    print(f"hi {name}")

def helper():        # unused helper last
    ...
```

### `abstraction` — callee before caller

The reverse: low-level utilities appear **first**, high-level orchestration
**last**. Useful when you want the building blocks at the top of the file.

```python
# before
def main():
    greet("world")

def greet(name):
    print(f"hi {name}")

# after (functions = "abstraction")
def greet(name):     # leaf utility first
    print(f"hi {name}")

def main():          # orchestrator last
    greet("world")
```

#### `stepdown` vs `abstraction` at a glance

|                   | `stepdown`          | `abstraction`          |
| ----------------- | ------------------- | ---------------------- |
| Reading direction | top-down narrative  | bottom-up construction |
| Where callers sit | above their callees | below their callees    |
| Good for          | onboarding a reader | exposing primitives    |

### In-class method ordering (undersort)

Independent of the section strategy, `csort` reorders methods _within_ each
class using undersort semantics — grouped by visibility then method type,
stable within each group:

```python
# before
class Service:
    def _internal(self):
        ...
    def start(self):
        ...
    @staticmethod
    def make():
        ...
    def __secret(self):
        ...

# after (order = public, protected, private; method_type = instance, class, static)
class Service:
    def start(self):            # public instance
        ...
    @staticmethod
    def make():         # public static
        ...
    def _internal(self):        # protected instance
        ...
    def __secret(self):         # private instance
        ...
```

Configure the grouping under `[tool.csort.class_methods]`, or disable it with
`enabled = false`. A `class C:  # csort: off` trailing comment opts a single
class out; `# nosort` works the same. Per-method `# nosort` (or `# csort: off`)
locks that single method at its original index even when the class is reordered.

For one-off invocations, pass the overrides on the command line:

```shell
csort run src/ --class-methods-order private,protected,public
csort run src/ --method-type-order static,instance,class
```

These resolve on top of the discovered file config and apply to every command
(`run`, `check`, `diff`). The legacy `[tool.undersort]` (or top-level
`[undersort]` in standalone configs) is still read for `order` and
`method_type_order` when `[tool.csort.class_methods]` is absent.

### Trying it out safely

Always preview changes before writing them. `csort diff` shows a unified diff
without touching the file, and `csort check` (exit-code based) is ideal for CI
or pre-commit hooks:

```shell
csort diff src/                            # preview every change
csort run src/ --strategy-overrides functions=stepdown
csort check src/                           # exit 1 if anything would change
```

### Realistic examples

The repository ships with five fully-formed sample modules in `tests/data/`
that demonstrate every strategy and feature on believable Python code — not
toy snippets. Each has an `*_unsorted.py` input and its committed
`*_sorted.py` output:

| Sample                                  | Strategy shown              | Highlights                                                               |
| --------------------------------------- | --------------------------- | ------------------------------------------------------------------------ |
| `web_service_{unsorted,sorted}.py`      | `stepdown`                  | dataclasses, enums, retry loop, undersort on `Client`                    |
| `csv_pipeline_{unsorted,sorted}.py`     | `stepdown`                  | runtime barriers (`_VALIDATORS` + `register_validator`), `TYPE_CHECKING` |
| `cli_app_{unsorted,sorted}.py`          | `keep` (default)            | the classic `app = typer.Typer()` barrier keeping commands together      |
| `plugin_registry_{unsorted,sorted}.py`  | `abstraction`               | callee-first ordering: leaf utilities before the orchestrator            |
| `inventory_models_{unsorted,sorted}.py` | `alpha` (enums + functions) | rich undersort: all visibility/type combinations in one class            |

Try them:

```shell
csort diff tests/data/plugin_registry_unsorted.py
csort run tests/data/inventory_models_unsorted.py --strategy-overrides enums=alpha,functions=alpha
```
