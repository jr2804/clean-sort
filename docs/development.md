---
title: Development
---

## Development

Contributor setup, checks, and the release process for `pyreorder`.

### Requirements

- Python 3.11+ (CI runs 3.11, 3.12, and 3.13 on Linux, macOS, and Windows)
- [uv](https://docs.astral.sh/uv/) for environments and tooling
- [mise](https://mise.jdx.dev/) (optional) for the task shortcuts below

### Setup

```shell
git clone https://github.com/jr2804/pyreorder
cd pyreorder
uv sync --dev
```

`uv sync --dev` creates `.venv` and installs the runtime, test, and documentation
dependencies together with `pyreorder` itself in editable mode.

### Tasks

`mise` wraps the common commands. Each task maps to the plain invocation CI also
uses, so you can run the underlying tool directly if you prefer.

| Task             | Underlying command                                 | Purpose                          |
| ---------------- | -------------------------------------------------- | -------------------------------- |
| `mise dev`       | `uv sync --dev`                                    | Install/refresh the environment  |
| `mise test`      | `pytest --cov=pyreorder --cov-report=term-missing` | Run the test suite with coverage |
| `mise lint`      | `ruff check src tests --fix --unsafe-fixes`        | Lint and auto-fix                |
| `mise format`    | `ruff format src tests`                            | Format Python sources            |
| `mise format-md` | `rumdl fmt --config .config/rumdl.toml`            | Lint and reformat Markdown       |
| `mise typecheck` | `ty check src tests`                               | Static type checking             |
| `mise spell`     | `codespell src tests`                              | Spell check                      |
| `mise docs`      | `zensical build --clean`                           | Build the documentation site     |

Run the whole gate before opening a pull request:

```shell
mise test && mise lint && mise typecheck && mise spell && mise docs
```

### Tests

```shell
uv run pytest                                 # full suite
uv run pytest tests/test_transforms.py -q     # one module
uv run pytest -k type_checking -q             # one topic
```

`tests/data/` holds the end-to-end corpus: each `*_unsorted.py` input has a
committed `*_sorted.py` output that the tests assert against. See
`tests/data/README.md` for how to regenerate a fixture after changing sorter
behaviour.

### Type checking

`ty.toml` scopes the check to `src/` and `tests/`, and excludes `tests/data/`:
those files are fixtures — deliberately-unsorted inputs plus the sorter's
canonical outputs — not hand-maintained code.

### Documentation site

The site is built with [Zensical](https://zensical.org/) from `docs/`, plus
root-level pages pulled in by snippet (`README.md` becomes Overview,
`CONTRIBUTING.md` becomes Contributing, `CHANGELOG.md` becomes Changelog).
Configuration lives in `zensical.toml`.

```shell
uv run zensical serve      # live preview on http://localhost:8000
uv run zensical build      # one-off build into site/
```

CI builds the site on every pull request and deploys it to
<https://jr2804.github.io/pyreorder/> on every push to `main`.

### Pre-commit hooks

This repository ships `.pre-commit-config.yaml` (ruff, ruff-format, codespell,
and `pyreorder` itself). Install the hooks once per clone:

```shell
uv run pre-commit install
uv run pre-commit run --all-files
```

To use `pyreorder` as a hook in another project, add the published hook — `rev`
is any release tag:

```yaml
repos:
  - repo: https://github.com/jr2804/pyreorder
    rev: 2026.09.5
    hooks:
      - id: pyreorder
```

### Releasing

Releases are automatic and use calendar versioning (`YYYY.M.N`).

1. Push or merge to `main`.
2. `.github/workflows/release.yml` computes the next `YYYY.M.N` tag, creates and
   pushes it, builds the wheel and sdist, publishes to PyPI via trusted
   publishing (OIDC), and creates a GitHub Release with both artifacts attached.
3. There is no version to bump by hand: `uv-dynamic-versioning` derives the
   version from the git tag, and the tag is the source of truth.

Add `[skip release]` to the head commit message to suppress a release, for
example on a documentation-only push.

### Project layout

| Path                          | Contents                                             |
| ----------------------------- | ---------------------------------------------------- |
| `src/pyreorder/pipeline.py`   | Orchestration: parse → classify → sort → emit        |
| `src/pyreorder/classify.py`   | Maps each top-level statement to a section           |
| `src/pyreorder/sorters.py`    | In-section strategies (`alpha`, dependency-based)    |
| `src/pyreorder/undersort.py`  | In-class method ordering                             |
| `src/pyreorder/transforms.py` | Opt-in transforms (import hoisting, `TYPE_CHECKING`) |
| `src/pyreorder/config.py`     | Configuration model, discovery, and schema           |
| `src/pyreorder/cache.py`      | Content-hash skip cache                              |
| `src/pyreorder/cli/`          | Typer CLI                                            |
| `tests/data/`                 | End-to-end fixtures (unsorted/sorted pairs)          |
| `docs/`                       | Documentation site sources                           |
| `skills/pyreorder/`           | Bundled agent skill                                  |

See [Architecture](architecture.md) for the pipeline stage by stage.
