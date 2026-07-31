# clean-sort

[![status: alpha](https://img.shields.io/badge/status-alpha-orange)](https://codeberg.org/jr2804/clean-sort)
[![license: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![python](https://img.shields.io/badge/python-3.11+-blue)](https://www.python.org)

**AST-based Python module reorganizer.**

`csort` reorders the top-level statements of a Python module into a canonical
section layout (imports → globals → constants → classes → functions → `main`)
and reorders the methods inside each class by visibility and type. It is built
on [`libcst`](https://github.com/Instagram/LibCST), so comments and formatting
are preserved.

It is a **module reorganizer**: it focuses on grouping and ordering
imports/globals/constants/classes/methods/etc. It does not integrate with
other sorting tools (isort, undersort, etc.) or provide ruff subcommands.

## Install

```shell
uv tool install clean-sort
csort --version
```

## Quick start

```shell
csort run src/                 # sort files in place
csort check src/               # exit 1 if anything would change (CI / pre-commit)
csort diff src/                # preview changes
csort config generate          # write/print a csort.toml template (--with-comments, --with-config)
```

### Before → after

Given this module:

```python
import sys

def main():
    greet()

def greet():
    print("hi")

class Service:
    def _close(self):
        ...
    def start(self):
        ...

MAX_CONN = 10

if __name__ == "__main__":
    main()
```

`csort run` (with `functions = "stepdown"`) produces:

```python
import sys

MAX_CONN = 10

class Service:
    def start(self):
        ...
    def _close(self):     # public methods first, then protected

def main():               # caller before callee (step-down rule)
    greet()

def greet():
    print("hi")

if __name__ == "__main__":
    main()
```

## Configuration

Discovered from (first wins, walking up from the target file): `--config`,
`csort.toml`, `.config/csort.toml`, `[tool.csort]` in `pyproject.toml`.

```toml
[tool.csort.module]
sections = [
    "imports", "typing_imports", "module_constants", "enums",
    "dataclasses", "classes", "functions", "main_block",
]

[tool.csort.strategy]            # per-section; omit => "keep"
enums = "alpha"
functions = "stepdown"           # "alpha" | "stepdown" | "abstraction" | "keep"

[tool.csort.class_methods]       # undersort-style ordering within each class
enabled = true
order = ["public", "protected", "private"]
method_type_order = ["instance", "class", "static"]

```

### Strategies

| value         | meaning                                          | applies to         |
| ------------- | ------------------------------------------------ | ------------------ |
| `keep`        | preserve original order (default)                | any section        |
| `alpha`       | alphabetical by primary name                     | imports, enums     |
| `stepdown`    | caller before callee (top-down narrative)        | functions, classes |
| `abstraction` | callee before caller (low-level utilities first) | functions, classes |

> **Caution:** `alpha` on `module_constants` / `classes` / `dataclasses` can
> break runtime order (interdependent constants, inheritance). Always preview
> with `csort diff` first.

## Safety model

`csort` is conservative by design:

- **Barriers** — statements that don't map to a configured section (runtime
  setup like `app = typer.Typer()`) are never moved. Recognised statements only
  reorder _within_ their contiguous barrier-free run, so csort never moves code
  across a statement it might depend on.
- **Pinned** — the module docstring and `from __future__ import ...` always stay
  first.
- **Opt-out** — a `# csort: off` (or `# nosort`) comment in a file's header
  skips the file; `class C:  # csort: off` skips that class.
- **Idempotent** — running `csort` twice never changes a file a second time.

## Programmatic API

```python
from clean_sort import sort_source, Config

cfg = Config(strategies={"functions": "stepdown"})
sorted_text = sort_source(source_text, cfg)
```

## Pre-commit

```yaml
repos:
  - repo: https://codeberg.org/jr2804/clean-sort
    rev: v0.1.0
    hooks:
      - id: csort
```

## Agent skill

An installable agent skill lives in [`skills/clean-sort`](skills/clean-sort).
Install it for your AI assistant:

```shell
bun x skills add https://codeberg.org/jr2804/clean-sort.git -s clean-sort -a universal -y
```

## Development

```shell
uv sync --dev           # install dev dependencies
uv run pytest           # tests
uvx ruff check .        # lint
uvx ruff format .       # format
```

## Acknowledgements

The in-class method sorter is an adapted reimplementation of
[undersort](https://github.com/kivicode/undersort) (MIT). Dependency-aware
function ordering was inspired by [ssort](https://github.com/bwhmather/ssort),
[sdsort](https://github.com/eirikurt/sdsort) and
[ABSort](https://github.com/MapleCCC/ABSort). See
[Credits](https://codeberg.org/jr2804/clean-sort/src/branch/main/docs/credits.md).

## License

MIT — see [LICENSE](LICENSE).
