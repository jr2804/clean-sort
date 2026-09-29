---
title: Architecture Decision Records
hide:
- feedback
- toc
---

# Architecture Decision Records

This directory records significant design decisions in `csort`. Each ADR
captures the **context**, the **options considered**, the **decision**, and
the **consequences** of the choice.

ADRs are immutable once accepted. If a decision is reversed, a new ADR is
written that supersedes the old one (with a link). The history of the
project's design is preserved in the ADR sequence.

## Index

| # | Title | Status |
|---|---|---|
| [0001](0001-libcst-for-ast-manipulation.md) | libcst for AST manipulation | Accepted |
| [0002](0002-forward-reference-barriers.md) | Forward-reference barriers | Accepted |
| [0003](0003-stepdown-as-default-strategy.md) | stepdown as the default strategy | Accepted |

## Conventions

- Files are named `NNNN-short-kebab-title.md`. The number is a monotonically
  increasing counter; never re-use a number.
- Each ADR has frontmatter: `title` (required), `hide` (optional, used by
  zensical to suppress the page-level feedback widget).
- The status field is one of: **Proposed**, **Accepted**, **Superseded**.
- Decisions about *user-facing configuration* (option names, defaults,
  flag syntax) go in ADRs even though they look like docs — they are
  decisions, and we want them on record.

## Adding a new ADR

1. Copy the template below to a new file with the next available number.
2. Fill in **Status**, **Date**, and **Deciders** at the top.
3. Write **Context**, **Considered options**, **Decision outcome**,
   **Consequences**, and **References**.
4. Add a row to the index table above.
5. Open a PR. ADRs are merged by Jan Reimes.

```markdown
---
title: "ADR NNNN: <title>"
---

# ADR NNNN: <title>

- **Status:** Proposed | Accepted | Superseded (by ADR MMMM)
- **Date:** YYYY-MM-DD
- **Deciders:** <names>

## Context and problem statement

<What is the issue? What constraints are we under?>

## Considered options

1. **<option 1>** — <one-line description>.
2. **<option 2>** — <one-line description>.
3. **<option 3>** — <one-line description>.

## Decision outcome

Chosen option: **<option N>**. Reasons:

- <reason 1>
- <reason 2>

## Consequences

Positive:

- <benefit 1>

Negative:

- <cost 1>

Neutral:

- <fact 1>

## References

- <file path or URL>
```
