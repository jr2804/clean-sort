# AGENTS.md — HISTORY

Recorded decisions with git references. Read when relevant to current task.
Acts as simple long-term memory for the project.

## Format

| Date | Decision | Rationale | Git ref |
|------|----------|-----------|---------|
| YYYY-MM-DD | [description] | [why] | [commit hash/tag] |

## Guidance

- Record decisions that would be costly to rediscover.
- Note false turns and why they were rejected.
- Link to relevant commits.
- Keep entries brief — enough to reconstruct reasoning.

## Decisions

| Date | Decision | Rationale | Git ref |
|------|----------|-----------|---------|
| 2026-07-06 | Created Codeberg repo; adopted CalVer versioning; configured Forgejo Actions for auto-releases | Automated, date-based releases without manual tagging | — |
| 2026-07-07 | Scaffolded with copier-uv-plus; vendored the undersort sorter | Reuse proven in-class method ordering | — |
| 2026-07-08 | Implemented core sorting (alpha/stepdown/abstraction), config discovery, CLI (run/check/diff), 53 tests | First usable release | 2026.7.8.1 |
| 2026-09-30 | Moved canonical home Codeberg -> GitHub; releases now publish to PyPI (trusted publishing) | `clean-sort` was unreservable on PyPI (collides with existing `cleansort`) | d24dbac |
| 2026-09-30 | Renamed project clean-sort -> `pyreorder` (PyPI, import, source dir, skill) | Name free on PyPI and unambiguous | d24dbac |
| 2026-09-30 | Standardised the public surface on `pyreorder`: CLI `pyreorder` (+ `rord` short alias), `[tool.pyreorder]` table, `# pyreorder: off` directive; clean break, only auto-migrated `csort.*` paths retained | Consistent with the package and import name | d5421a5 |
