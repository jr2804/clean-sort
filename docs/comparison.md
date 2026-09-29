---
title: Comparison with other tools
---

# Comparison with other tools

`csort` is one of several Python source-organisation tools. This page positions
it against the alternatives so you can pick the right tool for your codebase.

## At a glance

| Tool | Scope | Strategy | Format-preserving | Touches class bodies | Touches imports |
|---|---|---|---|---|---|
| **csort** | Whole module | Configurable (keep / alpha / stepdown / abstraction) | Yes (libcst) | Yes | No (forward-reference aware) |
| [isort][isort] | Imports only | Alphabetical by module, with case/known-first-party config | Yes | No | Yes |
| [Ruff][ruff] `I001` | Imports only | Same engine as isort | Yes | No | Yes |
| [undersort][undersort] | Class bodies only | Method category (dunder / init / public / private / …) | Yes | Yes | No |
| [ssort][ssort] | Whole module | Topological sort of top-level + class members | Yes | Yes | No |
| [sdsort][sdsort] | Whole module | Step-down rule (callers precede callees) | Yes | Yes | No |
| [ABSort][absort] | Whole module | Topological sort on abstraction-level DAG (Zhang-Shasha) | No | Yes | No |

[isort]: https://pycqa.github.io/isort/
[ruff]: https://docs.astral.sh/ruff/rules/unsorted-imports/
[undersort]: https://github.com/filipdanic/undersort
[ssort]: https://pypi.org/project/ssort/
[sdsort]: https://dev.to/romdevin/improving-python-code-comprehension-top-down-documentation-for-bottom-up-implementations-2dbc
[absort]: https://github.com/MapleCCC/ABSort

## How they differ

### Imports: `isort` and Ruff

`isort` and Ruff's `I001` rule do one thing and do it well: sort `import`
statements. They group by source (stdlib / third-party / local), alphabetise
within each group, and dedupe. They do not look at anything outside the
imports block.

`csort` does **not** sort imports — it leaves the imports block alone. The
rationale is that `isort` / Ruff already do this job perfectly, and combining
two tools that both touch the same lines leads to merge conflicts and
unpredictable diffs. Use both: `csort` for everything except imports,
`isort` / Ruff for the imports themselves.

### Class bodies: `undersort`

`undersort` orders methods inside a class: dunders first, then `__init__`,
then public methods, then private methods. It does not touch anything
outside the class body.

`csort` includes the same method ordering as part of its pipeline
(`sorters.MethodSorter`), so if you already use `csort` you do not need
`undersort`. The legacy `[tool.undersort]` table in `pyproject.toml` is
honoured as a fallback when `[tool.csort.class_methods]` is absent — see
[Configuration](configuration.md).

### Whole module: `ssort`, `sdsort`, `ABSort`

These three tools each take a different stance on statement ordering:

- **`ssort`** runs a topological sort on dependencies. Statement A stays
  before statement B iff A does not depend on B. Within classes, attributes
  are pinned in their original order, then lifecycle methods, then regular
  methods in dependency order, then other dunders in a fixed order.
- **`sdsort`** applies the *step-down rule*: callers precede callees. The
  "high-level logic" of a module (the entry point) sits at the top, helpers
  below.
- **`ABSort`** ranks statements by abstraction level (topological sort on
  the strongly connected components of the dependency graph), with optional
  Zhang-Shasha-based tie-breaking that reorders statements at the same
  abstraction level by AST similarity.

`csort`'s `stepdown` and `abstraction` strategies overlap with `sdsort` and
`ABSort` respectively. The differences are practical:

| | `csort` | `ssort` / `sdsort` / `ABSort` |
|---|---|---|
| **Section ordering** | Configurable: imports → constants → runtime setup → functions → classes → main | Single global order (always topological) |
| **Barriers** | Forward-reference aware; unrecognised statements stay put | No barriers — every statement is sortable |
| **Formatting** | libcst round-trip is byte-identical | libcst / native CST; some tools normalise whitespace |
| **Configuration** | One TOML file; per-section strategies; per-class method ordering | Tool-specific flags / config |
| **Class-body sort** | Yes (configurable, with `undersort` fallback) | Yes (`ssort` has fixed lifecycle order; `ABSort` ranks by AST similarity) |
| **Imports** | No — delegated to `isort` / Ruff | No — same |
| **Safety stance** | "leave unfamiliar code alone" | "reorder everything it can see" |

## When to pick `csort`

`csort` is the right tool when **at least two of these are true**:

- Your module has both a top-level structure (imports, constants, runtime
  setup, functions, classes) **and** class bodies that benefit from a fixed
  method order.
- You want to delegate import sorting to `isort` / Ruff and have a single
  tool own the rest of the file.
- You have code that `csort` cannot classify — third-party decorators,
  conditional `__all__` updates, runtime-generated class attributes — and
  you want those statements to **stay where they are**.
- You care that reformatting the file with `csort` does not introduce
  whitespace, quote-style, or comment-position changes.

## When to pick something else

- **Just imports?** Use `isort` or Ruff's `I001`. `csort` will not touch
  them.
- **Just class bodies?** `undersort` does it in one flag.
- **Topological correctness is your top priority?** `ssort` is more
  thorough: it never breaks a dependency. `csort` is more conservative —
  it does not move code it cannot prove is safe to move.
- **Top-down readability is your top priority?** `sdsort` makes the
  high-level logic sit at the top of every file, automatically.
- **You want maximal reordering and minimal diff?** `ABSort` sorts by
  abstraction level with syntax-tree similarity tie-breaking — minimal diff
  within an abstraction tier.

## Using them together

A typical Python project can run all of these in sequence without
conflict:

```bash
# 1. Reorganise whole module (csort)
csort src/

# 2. Sort imports (isort or ruff)
isort src/
# or: ruff check --select I --fix src/

# 3. Format (black or ruff format)
black src/
# or: ruff format src/
```

`csort` is designed to be run **first** because its forward-reference
barriers assume that other tools have not yet moved the imports block. Run
`isort` and `black` afterward; their output is independent of the rest of
the file.
