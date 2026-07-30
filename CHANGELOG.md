# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

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
