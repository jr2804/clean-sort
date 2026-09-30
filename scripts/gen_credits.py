#!/usr/bin/env python3
"""Generate the dependency list for the credits page from pyproject.toml."""

from __future__ import annotations

import tomllib
from pathlib import Path

try:
    ROOT = Path(__file__).resolve().parent.parent
except NameError:
    # Executed without ``__file__`` (e.g. embedded in docs via ``markdown_exec``).
    ROOT = Path.cwd()

GROUPS = (
    ("Runtime", ("project", "dependencies")),
    ("Documentation and development", ("dependency-groups", "dev")),
)


def _package_names(deps: list[str]) -> list[str]:
    """Extract distribution names from PEP 508 dependency strings, in declared order."""
    names = []
    for dep in deps:
        if isinstance(dep, str) and not dep.startswith(("-", "#")):
            names.append(dep.split("[")[0].split(">=")[0].split("==")[0].strip())
    return names


def load_credits() -> str:
    """Render every declared dependency as a Markdown list, grouped by role."""
    with (ROOT / "pyproject.toml").open("rb") as f:
        data = tomllib.load(f)

    blocks = []
    for label, path in GROUPS:
        section: object = data
        for key in path:
            section = section.get(key, {}) if isinstance(section, dict) else {}
        names = _package_names(section if isinstance(section, list) else [])
        if names:
            links = "\n".join(f"- [{name}](https://pypi.org/project/{name}/)" for name in names)
            blocks.append(f"**{label}**\n\n{links}")
    return "\n\n".join(blocks)


# markdown-exec runs this file with ``__name__`` set to a synthetic module
# name (never ``"__main__"``) and renders only what is printed, so the output
# has to be produced at module level. With no print, markdown-exec renders an
# empty block and docs/credits.md silently shows nothing.
print(load_credits())  # noqa: T201
