# AGENTS.md — tests

## Purpose

pytest behavioural suite for pyreorder. Guards sorting correctness and idempotency.

## Ownership

Mirrors `src/pyreorder/` structure with one test file per module.

## Local Contracts

- Tests must preserve existing coverage; add or extend only for directly affected behavior.
- Idempotency is a first-class property: `sort_source(sort_source(src)) == sort_source(src)`.
- Coverage gate `fail_under=90` is configured in `pyproject.toml` (`[tool.pytest-cov]`).

## Work Guidance

- Prefer small, targeted tests over broad refactors.
- `tests/conftest.py` provides shared fixtures.

## Verification

- `uv run pytest` — full suite with coverage
- `uv run pytest tests/test_cli.py` — CLI option coverage (`--section-only`, `--strategy-overrides`, `--class-methods-order`, `--method-type-order`)
- `uv run pytest tests/test_undersort.py` — `MethodSorter` unit tests (visibility/type buckets, ordering, `nosort` / `pyreorder: off` directives, modified flag)
- `uv run pytest tests/test_config.py` — config discovery, legacy `[tool.undersort]` fallback
- `uv run pytest tests/test_transforms.py` — opt-in import transforms (hoist, TYPE_CHECKING removal)
- `uv run pytest tests/test_docs_assets.py` — docs build-input guards (Mermaid fence present, credits generator prints)

## Child DOX Index

None.
