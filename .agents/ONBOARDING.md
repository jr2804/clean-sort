# AGENTS.md — ONBOARDING

Read this when starting a new session. After first read, only revisit when
project structure or tooling changes significantly.

## Project

pyreorder — an AST-based Python module reorganizer that deterministically groups
imports/globals/constants/classes/methods into the correct order. Full docs at
`README.md` and `docs/`.

## Quick start

```bash
uv run pytest      # run the test suite
uv build           # build wheel + sdist
preorder check .      # verify files are already sorted
mise format-md     # format/lint markdown
```

## Entry points (read these first)

| File | Why |
|------|-----|
| `AGENTS.md` | Root rail — rules + `.agents/` index |
| `.agents/POLICIES.md` | Boundaries, priorities, verification |
| `.agents/FILES.md` | Source-of-truth locations |
| `src/pyreorder/__init__.py` | Public API (`sort_source`, `Config`, `load_config`) |

## Where to dig deeper

- `docs/` — user-facing documentation
- `.agents/HISTORY.md` — past decisions and rationale
- `src/pyreorder/AGENTS.md` — package-local contracts
- `tests/AGENTS.md` — testing conventions

## Available tools

- **preorder** — reorganize Python modules (CLI + `pyreorder` API)
- **mise / uv** — task running, env, build, format, lint
- **codegraph** — symbol search, call graphs
- **grepai** — find code by intent
- **bd / beads** — issue tracking and session persistence (`.agents/skills/beads/`)
