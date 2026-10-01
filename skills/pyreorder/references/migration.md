# Migrating a project from `csort` / `clean-sort`

Projects that used the earlier `csort` / `clean-sort` names need their config,
invocations and imports updated. pyreorder renames the **on-disk paths**
itself; everything else is a manual edit.

## Name map

| Old (`csort` / `clean-sort`)          | New (`pyreorder`)                    |
| ------------------------------------- | ------------------------------------ |
| `[tool.csort]` in `pyproject.toml`    | `[tool.pyreorder]`                   |
| `csort.toml`, `clean-sort.toml`       | `pyreorder.toml`                     |
| `.config/csort.toml`                  | `.config/pyreorder.toml`             |
| `# csort: off` directive              | `# pyreorder: off`                   |
| CLI `csort`, `clean-sort`             | CLI `pyreorder`, short alias `rord`  |
| pre-commit hook id `csort`            | hook id `pyreorder`                  |
| import package `clean_sort`           | `pyreorder`                          |
| distribution `clean-sort`             | `pyreorder`                          |
| `~/.config/csort/`, `~/.config/clean-sort/` | `~/.config/pyreorder/config.toml` |
| `~/.cache/csort/`, `~/.cache/clean-sort/`   | `~/.cache/pyreorder/`          |
| `.csort-cache/`, `.clean-sort-cache/`       | `.pyreorder-cache/`            |

`# nosort` and `[tool.undersort]` are **unchanged** — no migration needed.

## Migrated automatically

`pyreorder.migrate.migrate_if_needed()` runs whenever pyreorder loads its
configuration — every `run`, `check`, `diff` and `config` command — and renames
the legacy **file and directory** paths:

- `csort.toml` / `clean-sort.toml` → `pyreorder.toml`
- `~/.config/csort/` and `~/.config/clean-sort/` (holding `csort.toml`,
  `clean-sort.toml` or `config.toml`) → `~/.config/pyreorder/config.toml`
- `~/.cache/csort/` and `~/.cache/clean-sort/` → `~/.cache/pyreorder/`
- `.csort-cache/` and `.clean-sort-cache/` → `.pyreorder-cache/`

Four details decide whether it runs for you:

- **It runs once per machine.** A successful migration writes
  `~/.cache/pyreorder/.migrated-from-csort`; once that sentinel exists, later
  invocations skip migration entirely. A second checkout with legacy names is
  *not* migrated — rename those by hand.
- **It refuses to overwrite.** If `pyreorder.toml` already exists, the legacy
  file is left in place and reported as `WARN: would overwrite`. Merge them
  yourself.
- **It is silent.** The CLI discards the report, so the renames happen with no
  output at all. Call the functions below to see what a run did.
- **A project-relative `.config/csort.toml` is not covered.** Only the two
  root-level filenames are renamed; move `.config/csort.toml` to
  `.config/pyreorder.toml` by hand.

To inspect the outcome, call the functions directly. They perform the renames —
there is no dry-run flag — and `report.log()` writes one
`pyreorder-migrate: renamed …` line per path to stderr:

```python
from pyreorder.migrate import migrate_legacy_cache, migrate_legacy_config

for report in (migrate_legacy_config(), migrate_legacy_cache()):
    print(report.renamed, report.would_overwrite, report.skipped)
    report.log()
```

## Change by hand

### 1. The `[tool.csort]` table

Not migrated. pyreorder reads `[tool.pyreorder]` only, so a leftover
`[tool.csort]` is silently ignored and the project runs on defaults — which can
*change* how it sorts. Rename the table:

```toml
# pyproject.toml
[tool.csort]        # → [tool.pyreorder]
[tool.csort.strategy]   # → [tool.pyreorder.strategy]
```

Every `[tool.csort.*]` sub-table must be renamed too.

### 2. Command invocations

Anywhere the old command is called. Search first:

```shell
rg -n --hidden -g '!.git' -g '!uv.lock' -e '\bcsort\b' -e 'clean[-_]sort' .
```

Replace `csort` with `pyreorder` (or `rord` where brevity matters) in:

| Where                         | What to look for                                  |
| ----------------------------- | ------------------------------------------------- |
| `Makefile`, `justfile`        | `csort run`, `csort check` recipe lines           |
| `mise.toml` / `.mise.toml`    | `[tasks.*]` runs                                  |
| `package.json`                | `scripts`                                         |
| `tox.ini`, `noxfile.py`       | test/lint envs                                    |
| `.github/workflows/*.yml`     | `run:` steps, GitHub Actions `uses:`/cache keys   |
| `Dockerfile`, `*.sh`, `*.ps1` | `RUN`/shell lines                                 |
| `pre-commit` config           | see below                                         |

`csort check` is the usual CI gate — keep the same verb:

```diff
-  run: csort check src tests
+  run: pyreorder check src tests
```

### 3. Pre-commit hook

The hook id changed, so an old config resolves to nothing. Update both the `rev`
and the id:

```yaml
repos:
  - repo: https://github.com/jr2804/pyreorder
    rev: 2026.09.5          # or any released CalVer tag
    hooks:
      - id: pyreorder       # was: csort
```

`rev` is a CalVer tag — the old `v0.1.0`-style pins never existed.

### 4. Dependency and import name

The distribution is `pyreorder` and the import package is `pyreorder`:

```diff
- clean-sort @ git+https://codeberg.org/jr2804/clean-sort
+ pyreorder @ git+https://github.com/jr2804/pyreorder
```

```diff
- from clean_sort import sort_source, Config
+ from pyreorder import sort_source, Config
```

Re-run `uv sync` / `uv lock` afterwards so the lockfile and any vendored copies
resolve to the new name. `uv tool install csort` also needs
`uv tool install pyreorder`.

### 5. `# csort: off` directives in source

Only `pyreorder: off` and `nosort` are recognised. An old marker is inert, so
the file gets sorted when it previously was not:

```diff
- # csort: off
+ # pyreorder: off
```

The same applies to a per-class trailing comment
(`class C:  # csort: off` → `# pyreorder: off`).

### 6. Docs, links and ignore rules

- Docs, README, badges and CI links pointing at
  `codeberg.org/jr2804/clean-sort` → `github.com/jr2804/pyreorder`.
- `.gitignore` entries for `.csort-cache/` → `.pyreorder-cache/`.
- A bundled copy of the old skill (`skills/clean-sort/`, or references in
  `AGENTS.md`) → `skills/pyreorder/`.

## Verify

```shell
rg -n --hidden -g '!.git' -g '!uv.lock' -e '\bcsort\b' -e 'clean[-_]sort' .   # expect no live hits
pyreorder config show      # the resolved config, not the defaults
pyreorder check .          # exit 1 only for genuinely unsorted files
```

`pyreorder config show` is the one that catches a missed `[tool.csort]` rename:
the settings will be there instead of silently reverting to defaults.
