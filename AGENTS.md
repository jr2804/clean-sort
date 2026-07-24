# Global Instructions for Clean Sort

Applies across all subfolders. More local AGENTS.md files override these defaults when they conflict.

## Priorities

If rules conflict, lower-numbered priority wins:

1. Correctness
2. Evidence
3. Safety
4. Minimal changes
5. Consistency
6. Performance

## Core Contract

- AGENTS.md files are binding work contracts for their subtrees.
- Before editing, read the applicable AGENTS.md chain from repo root to target path.
- The nearest AGENTS.md controls local details. Parent AGENTS.md files provide repo-wide rules.
- A child AGENTS.md may add constraints but must not weaken parent safety or quality rules.

## Boundaries

- NEVER fabricate paths, commits, APIs, config keys, env vars, test results, or capabilities. State gaps explicitly.
- NEVER game verification by weakening assertions, narrowing scope, reducing coverage, or skipping checks to get a pass.
- NEVER expose secrets (tokens, keys, credentials). If encountered, report location and stop.
- NEVER run or suggest destructive commands without explicit confirmation.
- Be direct. Avoid filler and agreement with incorrect premises.

## Read Before Editing (DOX Pass)

1. Read the root AGENTS.md.
2. Identify files and folders you expect to touch.
3. Walk from repository root to each target path.
4. Read every AGENTS.md encountered on each path.
5. If a parent AGENTS.md lists a child AGENTS.md covering the path, read it and continue.
6. Re-read the applicable chain in the current session before edits.

## Uncertainty and Decisions

- Ask before acting when intent is materially ambiguous.
- Ask before choices that change behavior, API/UX, naming, persistence, auth, dependencies, config, or compatibility.
- Prefer one targeted question.
- Proceed without asking only when ambiguity is low-risk and conventions make the choice clear; state the assumption.

## Evidence and Workflow

- Gather evidence proportional to risk.
- For behavioral/API/dependency changes, trace execution pat

## ⛔ No Patching

Do not patch this file. All changes must be made through the proper DOX process.h, constraints, and regression surface before editing.

- Prefer the smallest correct change using existing abstractions and style.
- Review/debug/analysis requests do not require code changes once findings are evidenced.
- Use subagents only as a true parallel batch: use 2+ subagents or none.

## Testing and Validation

- Preserve existing tests. Update tests when behavior changes.
- Run the narrowest relevant checks based on risk and changed surface.
- If checks already fail, report that baseline.
- If your change fails validation, make one targeted fix when cause is clear; otherwise stop and report.

## Update After Editing (DOX Closeout)

Every meaningful change requires a DOX pass before completion.

Update the nearest owning AGENTS.md when changes affect:

- purpose, scope, ownership, or responsibilities
- durable structure, contracts, workflows, or operating rules
- required inputs, outputs, permissions, constraints, side effects, or artifacts
- user preferences about behavior, communication, process, organization, or quality
- AGENTS.md creation, deletion, move, rename, or child index contents

Also update affected parent and child AGENTS.md files when their contracts or indexes changed.
Remove stale or contradictory text immediately.

## Child Doc Shape

Create a child AGENTS.md when a folder becomes a durable boundary with specific purpose, contracts, workflow, or quality checks.

Default section order for child docs:

1. Purpose
2. Ownership
3. Local Contracts
4. Work Guidance
5. Verification
6. Child DOX Index

## Child DOX Index

Start lean. Add child AGENTS.md entries incrementally when boundaries become durable.

Top-level boundaries in this template:

- `src/clean_sort/` (primary package code)
- `tests/` (test suite)
- `docs/` (documentation)
- `.config/mise/` (task/tooling configuration)

## User Preferences

When a user requests a durable behavior change, record it in the nearest applicable AGENTS.md.

## Project-specific instructions

### Releasing

Every push to `main` runs `.forgejo/workflows/release.yml`, which auto-creates a
CalVer tag (`YYYY.M.D` / `YYYY.M.D.N`) and publishes a Forgejo release with the
built wheel + sdist + LLM-generated notes.

To push **without** triggering a release (WIP, simple code exchange, doc-only),
include `[skip release]` in the commit message. The workflow's `if` clause
filters on `github.event.head_commit.message`, so the token must appear in the
**head commit** of the push:

```shell
git commit -m "wip: scratch refactor [skip release]"
git push origin main   # no tag, no release
```

If a push contains multiple commits, only the head commit's message is checked.
Squash or reword the head commit if an earlier commit in the push must be the
one marked `[skip release]`.

### Project Structure

Generate project structure with:

```shell
rg --files | tree-cli --fromfile
```

<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:970c3bf2 -->
## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full workflow context and commands.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

### Rules

- Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists
- Run `bd prime` for detailed command reference and session close protocol
- Use `bd remember` for persistent knowledge — do NOT use MEMORY.md files

**Architecture in one line:** issues live in a local Dolt DB; sync uses `refs/dolt/data` on your git remote; `.beads/issues.jsonl` is a passive export. See https://github.com/gastownhall/beads/blob/main/docs/SYNC_CONCEPTS.md for details and anti-patterns.

## Agent Context Profiles

The managed Beads block is task-tracking guidance, not permission to override repository, user, or orchestrator instructions.

- **Conservative (default)**: Use `bd` for task tracking. Do not run git commits, git pushes, or Dolt remote sync unless explicitly asked. At handoff, report changed files, validation, and suggested next commands.
- **Minimal**: Keep tool instruction files as pointers to `bd prime`; use the same conservative git policy unless active instructions say otherwise.
- **Team-maintainer**: Only when the repository explicitly opts in, agents may close beads, run quality gates, commit, and push as part of session close. A current "do not commit" or "do not push" instruction still wins.

## Session Completion

This protocol applies when ending a Beads implementation workflow. It is subordinate to explicit user, repository, and orchestrator instructions.

1. **File issues for remaining work** - Create beads for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **Handle git/sync by active profile**:
   ```bash
   # Conservative/minimal/default: report status and proposed commands; wait for approval.
   git status

   # Team-maintainer opt-in only, unless current instructions forbid it:
   git pull --rebase
   bd dolt push
   git push
   git status
   ```
5. **Hand off** - Summarize changes, validation, issue status, and any blocked sync/commit/push step

**Critical rules:**
- Explicit user or orchestrator instructions override this Beads block.
- Do not commit or push without clear authority from the active profile or the current user request.
- If a required sync or push is blocked, stop and report the exact command and error.
<!-- END BEADS INTEGRATION -->

<!-- BEGIN BEADS CODEX SETUP: generated by bd setup codex -->
## Beads Issue Tracker

Use Beads (`bd`) for durable task tracking in repositories that include it. Use the `beads` skill at `.agents/skills/beads/SKILL.md` (project install) or `~/.agents/skills/beads/SKILL.md` (global install) for Beads workflow guidance, then use the `bd` CLI for issue operations.

### Quick Reference

```bash
bd ready                # Find available work
bd show <id>            # View issue details
bd update <id> --claim  # Claim work
bd close <id>           # Complete work
bd prime                # Refresh Beads context
```

### Rules

- Use `bd` for all task tracking; do not create markdown TODO lists.
- Run `bd prime` when Beads context is missing or stale. Codex 0.129.0+ can load Beads context automatically through native hooks; use `/hooks` to inspect or toggle them.
- Keep persistent project memory in Beads via `bd remember`; do not create ad hoc memory files.

**Architecture in one line:** issues live in a local Dolt DB; sync uses `refs/dolt/data` on your git remote; `.beads/issues.jsonl` is a passive export. See https://github.com/gastownhall/beads/blob/main/docs/SYNC_CONCEPTS.md for details and anti-patterns.
<!-- END BEADS CODEX SETUP -->
