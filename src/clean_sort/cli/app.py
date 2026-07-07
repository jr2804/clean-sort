"""Typer CLI app for Clean Sort."""

from __future__ import annotations

from importlib.metadata import version

import typer

# Version management
def _get_version() -> str:
    """Get application version from package metadata."""
    try:
        return version("clean_sort")
    except Exception:
        return "0.0.0"  # Fallback for development mode

app = typer.Typer(
    name="clean_sort",
    help="AST-based structural sorter for Python source code",
    add_completion=True,
    no_args_is_help=True,
)

@app.callback(invoke_without_command=True)
def _callback(
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        help="Show version and exit",
        is_eager=True,
    ),
) -> None:
    """AST-based structural sorter for Python source code"""
    if version:
        typer.echo(_get_version())
        raise typer.Exit()


def main() -> None:
    """Entry point for the CLI application."""
    app()


# Import commands to register them with app
from clean_sort.cli import commands  # noqa: E402, F401
