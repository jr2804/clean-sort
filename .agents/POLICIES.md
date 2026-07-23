# Policies — clean-sort

## Boundaries

- NEVER fabricate paths, commits, APIs, config keys, env vars, test results, or capabilities. State gaps explicitly.
- NEVER game verification by weakening assertions, narrowing scope, reducing coverage, or skipping checks to get a pass.
- NEVER expose secrets (tokens, keys, credentials). If encountered, report location and stop.
- NEVER run or suggest destructive commands without explicit confirmation.
- Be direct. Avoid filler and agreement with incorrect premises.

## Priorities

If rules conflict, lower-numbered priority wins:

1. Correctness
2. Evidence
3. Safety
4. Minimal changes
5. Consistency
6. Performance

## Verification

- Preserve existing tests. Update tests when behavior changes.
- Run the narrowest relevant checks based on risk and changed surface.
- If checks already fail, report that baseline.
- If your change fails validation, make one targeted fix when cause is clear; otherwise stop and report.

## Project-specific policies

- Always use `csort` on modified files before committing.
- Keep the codebase idempotent under `csort`.
- Focus on module reorganization (grouping imports/globals/constants/classes/methods/etc).
- Skip ruff subcommands and integration with other sorting tools (isort, undersort, etc.).
