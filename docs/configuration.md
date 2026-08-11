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

> ### Legacy `[tool.undersort]` / `[undersort]`
>
> For backwards compatibility, `class_methods.order` and
> `class_methods.method_type_order` are read from a `[tool.undersort]` table
> (in `pyproject.toml`) or a top-level `[undersort]` table (in standalone
> configs) when `[tool.csort.class_methods]` is absent. The `enabled` flag
> predates the legacy schema and is csort-only. Prefer `[tool.csort]`.

### Schema

| Table            | Key                 | Type / values                                    |
| ---------------- | ------------------- | ------------------------------------------------ |
| `module`         | `sections`          | ordered list of section names                    |
| `strategy`       | `<section>`         | `keep` \| `alpha` \| `stepdown` \| `abstraction` |
| `class_methods`  | `enabled`           | `bool`                                           |
| `class_methods`  | `order`             | permutation of `public`, `protected`, `private`  |
| `class_methods`  | `method_type_order` | permutation of `instance`, `class`, `static`     |
| `classification` | `constants_pattern` | regex (default `^[A-Z_][A-Z0-9_]*$`)             |
| `classification` | `dunder_exports_names` | list of dunder names (default `["__all__"]`)  |

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
    "runtime_setup",
    "enums",
    "dataclasses",
    "classes",
    "functions",
    "dunder_exports",
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

Dunder names like `__all__` classify into a dedicated `dunder_exports` section
that is placed after `functions` and before `main_block`. By default only
`__all__` is treated this way; extend the list to keep `__version__`,
`__author__`, etc. near the bottom of the module too:

```toml
[tool.csort.classification]
dunder_exports_names = ["__all__", "__version__", "__author__"]
```

Any dunder not listed here still classifies into `module_constants`.

### Command-line overrides

Five flags let you deviate from the file config without editing it:

| Flag                     | Effect                                                                   |
| ------------------------ | ------------------------------------------------------------------------ |
| `--section-only`         | Restrict reordering to the given comma-separated sections.               |
| `--strategy-overrides`   | Override per-section strategy, e.g. `functions=alpha`.                   |
| `--class-methods-order`  | Override method visibility order, e.g. `private,public,protected`.       |
| `--method-type-order`    | Override method-type order, e.g. `static,instance,class`.                |
| `--fail` / `--no-fail`   | Control whether `csort run` exits non-zero when files change (`run` only). |

The order/type flags accept a **permutation** of `public`/`protected`/`private` or
`instance`/`class`/`static` respectively; an invalid permutation warns and
falls back to the configured order.

`--fail` / `--no-fail` (`csort run` only) controls the exit code when files
were modified. The default is controlled by `[cli] fail_on_changed` (see
below); `--no-fail` is useful when running `csort` from a formatter task
that always writes and should not surface as a failure.

```shell
# Only reorder the functions section, using step-down ordering:
csort run src/ --section-only functions --strategy-overrides functions=stepdown

# Restrict to several sections; each reorders independently:
csort run src/ --section-only functions,classes --strategy-overrides functions=stepdown,classes=keep

# Reorder methods so private comes first, regardless of the file config:
csort run src/ --class-methods-order private,protected,public
```

These map onto the corresponding `Config` fields and are resolved on top of
the discovered file config.

### `[cli]` table

```toml
[cli]
# Exit non-zero when `csort run` modifies files (default: true).
# Pre-commit hooks and CI rely on this to detect drift. Override per-invocation
# with `--no-fail` (useful from formatter tasks that always write).
fail_on_changed = true

# Content-hash skip cache: avoids re-parsing already-sorted files.
# Default: on, stored in ~/.cache/csort/<project-slug>/cache.json
# cache = true
# cache_dir = ".csort-cache"  # override location (relative to cwd or absolute)

# Parallel file processing: 0 = serial, negative = auto (int(0.75*cpu_count())).
# Default: 0 (serial). Use --jobs/-j to override per-invocation.
# jobs = 0
# Parallel backend: "process" (multiprocessing) or "thread" (threading).
# Default: "process". Use --parallel-backend to override per-invocation.
# parallel_backend = "process"
```

The cache stores ``sha256(sorted_output)`` keyed by ``(config_signature, source_hash)``.
On a repeat run, if the file's current content hash matches the cached sorted hash,
the file is skipped entirely — no parse, no sort, no write. The cache is safe by
construction: any edit changes the source hash and forces a full sort; any config
or version change changes the signature and forces a full sort.

Disable per-invocation with ``--no-cache``, or permanently with ``[cli] cache = false``.

Parallel processing uses a process pool (``"process"``) or thread pool (``"thread"``).
The process pool is recommended for CPU-bound work (libcst parsing/sorting); the thread
pool may be useful when I/O (file reads) is the bottleneck. Stdin mode always runs
serially regardless of the ``jobs`` setting.

### `[discovery]` table

Controls which files `csort` scans when given a directory.

```toml
[discovery]
# Glob patterns to exclude (merged with --exclude flags on the command line).
exclude = ["vendor/**", "**/_generated.py"]
# Whether to descend into subdirectories (default: true).
# --no-recursive overrides this per-invocation.
recursive = true
```

`exclude` patterns are matched with :mod:`fnmatch` against both the full path
and the file name; patterns from the config are combined with any `--exclude`
flags (CLI patterns append, they do not replace).

### Opt-out directives

- **Whole file:** a `# csort: off` (or `# nosort`) comment anywhere in the
  module header skips the file entirely.
- **Single class:** `class C:  # csort: off` leaves that class's methods
  untouched.

### Generating a config template

`csort config generate` produces a csort.toml template from the current
config schema. Without options it prints the default template to stdout.

```shell
# Print the default template
csort config generate

# Write it to a file (must end in .toml)
csort config generate --output csort.toml

# Add explanatory comments for each setting
csort config generate --with-comments --output csort.toml

# Merge values from an existing config (upgrade path for new versions):
# recognized keys are carried forward; unknown/deprecated keys are dropped
# with a warning on stderr.
csort config generate --with-config old-csort.toml --output csort.toml
```

The schema is the single source of truth: `generate` only emits keys that the
currently-installed csort recognizes. This makes it the right tool for upgrading
an old config when new options appear or old ones are removed.

### Programmatic configuration

```python
from clean_sort import Config, sort_source

cfg = Config(
    strategies={"functions": "stepdown", "enums": "alpha"},
    class_methods_enabled=True,
    class_methods_order=["public", "protected", "private"],
    class_methods_type_order=["instance", "class", "static"],
)
sorted_text = sort_source(source_text, cfg)
```

See the [API reference](reference/api.md) for the full `Config` surface.
