# AGENTS.md — tests

## Purpose

pytest behavioural suite for clean-sort. Guards sorting correctness and idempotency.

## Ownership

Mirrors `src/clean_sort/` structure with one test file per module.

## Local Contracts

- Tests must preserve existing coverage; add or extend only for directly affected behavior.
- Idempotency is a first-class property: `sort_source(sort_source(src)) == sort_source(src)`.
- Coverage gate `fail_under=90` is configured in `pyproject.toml` (`[tool.pytest-cov]`).

## Work Guidance

- Prefer small, targeted tests over broad refactors.
- `tests/conftest.py` provides shared fixtures.

## Verification

- `uv run pytest` — full suite with coverage
- `uv run pytest tests/test_cli.py` — CLI option coverage (`--section-only`, `--strategy-overrides`)

## Child DOX Index

None.
