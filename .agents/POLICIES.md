# AGENTS.md — POLICIES

Always applicable. Boundaries, priorities, verification, checklist.

## Priorities

1. Correctness
2. Evidence
3. Safety
4. Minimal changes
5. Consistency
6. Performance

## Boundaries

- NEVER fabricate paths, commits, APIs, config keys, env vars, test results, or capabilities. State gaps explicitly.
- NEVER game verification by weakening assertions, narrowing scope, reducing coverage, or skipping checks to get a pass.
- NEVER expose secrets (tokens, keys, credentials). If encountered, report location and stop.
- NEVER run or suggest destructive commands (`rm -rf`, `git reset --hard`, `git push --force`) without explicit confirmation.
- NEVER commit or push, and never run Dolt remote sync, without explicit user authority (conservative beads profile).
- NEVER delete or move files without explicit instruction.

## Change constraints

- Minimal, surgical edits. Preserve existing style.
- No new dependencies without explicit instruction.
- No unrelated refactoring while fixing a bug.
- When changing tests, update only directly affected tests.

## Completion checklist

- Change solves the stated problem
- Relevant validation ran (or gaps explicitly stated)
- No unintended side effects introduced
- No secrets added or exposed
- Modified Python files are idempotent under `csort`

## Content rules (keep AGENTS.md lean)

- **No tree views.** Generate on demand with `rg --files | tree-cli --fromfile`.
- **No history.** Git log has it. Only record decisions costly to rediscover (in `.agents/HISTORY.md` with commit refs).
- **No TODO lists.** Use `bd` / beads for task tracking.
- **csort scope.** Module reorganization only; do not integrate ruff/isort or other external sorting tools.

## Verification

- Reorganize: `csort check` (no diff = clean) or `uv run python -m clean_sort`
- Lint: `uv run ruff check src tests`
- Format: `uv run ruff format src tests`
- Typecheck: `uv run ty check src tests`
- Test: `uv run pytest` (coverage gate `fail_under=90` in pyproject)
- Markdown: `mise format-md` then `rumdl check`

## Response format

Concise and specific. No filler, intros, or restated requirements.
Answer direct questions directly.

For review/debugging/analysis: findings with references, conclusion,
approach. Mention caveats.

## Closeout

1. Run verification
2. Report docs intentionally left unchanged and why
