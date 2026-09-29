"""pyreorder — AST-based structural sorter for Python source code.

Public API:

* :func:`sort_source` — sort a source string in memory.
* :func:`would_change` — check whether sorting would change a source string.
* :class:`Config` / :func:`load_config` / :func:`discover` — configuration.
"""

from __future__ import annotations

import importlib.metadata

from .cache import Cache, hash_text
from .config import VALID_STRATEGIES, Config, discover
from .config import load as load_config
from .pipeline import SectionSorter, sort_source, would_change

__all__ = [
    "VALID_STRATEGIES",
    "Cache",
    "Config",
    "SectionSorter",
    "__version__",
    "discover",
    "hash_text",
    "load_config",
    "sort_source",
    "would_change",
]

try:
    __version__ = importlib.metadata.version(__name__)
except importlib.metadata.PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0"
