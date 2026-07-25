"""A tiny Typer CLI — realistic module for csort examples.

This file demonstrates the most important real-world gotcha: module-level
runtime setup (``app = typer.Typer()`` and the ``@app.command()`` decorators)
forms a *barrier*. csort recognises it cannot move the decorated functions away
from ``app``, so they stay grouped below it.

Run::

    csort diff tests/data/cli_app_unsorted.py
    csort run  tests/data/cli_app_unsorted.py
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

APP_NAME = "todo"
DB_PATH = Path.home() / ".todo.json"


app = typer.Typer(name=APP_NAME, help="A tiny to-do list CLI.", no_args_is_help=True)


@app.command()
def add(task: Annotated[str, typer.Argument(help="Task to add.")]) -> None:
    """Add a task."""
    items = _load()
    items.append(task)
    _save(items)
    typer.echo(f"added: {task}")


@app.command()
def list_tasks() -> None:
    """List all tasks."""
    for index, item in enumerate(_load(), start=1):
        typer.echo(f"{index}. {item}")


@app.command()
def done(index: Annotated[int, typer.Argument(help="1-based task index.")]) -> None:
    """Mark a task as done (removes it)."""
    items = _load()
    if not 1 <= index <= len(items):
        typer.echo("no such task", err=True)
        raise typer.Exit(1)
    removed = items.pop(index - 1)
    _save(items)
    typer.echo(f"done: {removed}")


def _load() -> list[str]:
    """Load tasks from disk (empty list if missing)."""
    if not DB_PATH.exists():
        return []
    import json

    return json.loads(DB_PATH.read_text(encoding="utf-8"))


def _save(items: list[str]) -> None:
    """Persist *items* to disk."""
    import json

    DB_PATH.write_text(json.dumps(items), encoding="utf-8")


if __name__ == "__main__":
    app()
