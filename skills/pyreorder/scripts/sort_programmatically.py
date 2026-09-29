#!/usr/bin/env python3
"""Example: sort Python source programmatically with pyreorder.

Run:  uvx pyreorder --version   # ensure installed
      python sort_programmatically.py
"""

from __future__ import annotations

from pyreorder import Config, sort_source

UNSORTED = '''\
import sys
from typing import TYPE_CHECKING

def main():
    greet()

def greet():
    print("hi")

class Service:
    def _close(self):
        ...
    def start(self):
        ...
    def __init__(self):
        ...

MAX_CONN = 10

if __name__ == "__main__":
    main()
'''


def main() -> None:
    # stepdown = caller before callee (top-down); default class-method sort on.
    cfg = Config(strategies={"functions": "stepdown"})
    print(sort_source(UNSORTED, cfg))


if __name__ == "__main__":
    main()
