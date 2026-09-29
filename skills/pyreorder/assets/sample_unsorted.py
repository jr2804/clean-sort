"""Sample unsorted module for `preorder` demonstrations.

Try:   preorder diff assets/sample_unsorted.py
       preorder run assets/sample_unsorted.py
"""

import sys
from typing import TYPE_CHECKING


def main() -> None:
    """Entry point."""
    helper()
    print(greet())


def helper() -> int:
    return 42


def greet() -> str:
    return "hello"


class Repository:
    def __init__(self) -> None:
        self._cache: dict[str, int] = {}

    def all(self) -> list:
        return list(self._cache.values())

    def _flush(self) -> None:
        self._cache.clear()

    @classmethod
    def in_memory(cls) -> "Repository":
        return cls()


MAX_RETRIES = 3


if TYPE_CHECKING:
    import pathlib


if __name__ == "__main__":
    main()
