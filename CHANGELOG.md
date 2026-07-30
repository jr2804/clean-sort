# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- **`[discovery]` config table**: Persistent file-discovery options previously
  only available as CLI flags. `exclude` (glob list, merged with `--exclude`
  flags) and `recursive` (bool, default `true`; `--no-recursive` overrides).

- **`--fail` / `--no-fail` CLI flag and `[cli] fail_on_changed` config**: Control whether
  `csort run` exits non-zero when files are modified. Default remains exit 1 on change
  (pre-commit/CI friendly); `--no-fail` (or `[cli] fail_on_changed = false`) exits 0, useful
  when running csort from a formatter task that always writes. `csort check` is unaffected.

### Fixed

- **Forward-reference barrier for module-level constants** (issue #1): A
  module-level constant whose RHS references a name defined in a later section
  (e.g. ``_DEFAULT_COLOR = Color.RED`` where ``Color`` is an enum) is now
  treated as a barrier — it stays in place rather than being hoisted to
  ``module_constants``. This prevents ``NameError`` at import time.

### Added

- **``from __future__ import annotations`` awareness**: When the module has
  ``from __future__ import annotations``, annotation-only names in
  ``AnnAssign`` are excluded from the forward-reference check, since
  annotations are not evaluated at runtime.

- Initial project structure from [copier-uv-plus](<https://github.com/Jan> Reimes/copier-uv-plus).
