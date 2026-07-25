# AGENTS.md — MAINTENANCE

How to keep `.agents/` files current.

## Process

1. When a rule changes, update the owning file — never another file.
2. When adding a new `.agents/` file, add it to the index table in root `AGENTS.md`.
3. After any `.agents/` change, check the index for stale entries.

## Principles

- **Single source of truth.** Each rule lives in exactly one file. Cross-reference,
  never duplicate.
- **AGENTS.md is an index.** It points to `.agents/` files, does not replace them.
- **No tree figures.** Use `rg --files | tree-cli --fromfile` on demand.

## File update triggers

| File            | Update when                                               |
| --------------- | --------------------------------------------------------- |
| `ONBOARDING.md` | Project structure, tooling, or entry points change        |
| `POLICIES.md`   | Boundaries, priorities, or verification change            |
| `FILES.md`      | Path constants, config keys, or naming conventions change |
| `HISTORY.md`    | Notable decision made or resolved                         |

## Release process

Pushing to `main` runs `.forgejo/workflows/release.yml`, which auto-creates a CalVer
tag (`YYYY.M.N`) and publishes a Forgejo release. To suppress, include
`[skip release]` in the **head** commit message.
