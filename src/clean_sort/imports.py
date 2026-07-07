"""Optional import-block sorting.

Only the ``isort`` engine is wired in v1 (clean in-memory API via
:func:`isort.code`). The ``ruff`` import-engine is intentionally not wired:
use the ``csort ruff`` proxy or run ``ruff`` separately instead.
"""

from __future__ import annotations

from .config import Config

__all__ = ["sort_imports"]


def sort_imports(source: str, cfg: Config) -> str:
    """Run the configured import engine on ``source`` and return the result."""
    if cfg.import_engine == "isort":
        try:
            import isort  # noqa: PLC0415 - lazy optional dependency
        except ImportError as exc:  # pragma: no cover - exercised via tests
            msg = "csort: import engine 'isort' requested but isort is not installed; install with `uv tool install clean-sort[isort]`"
            raise RuntimeError(msg) from exc
        return isort.code(source)
    # "ruff" engine: not wired in v1; return unchanged.
    return source
