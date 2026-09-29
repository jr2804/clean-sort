r"""Plugin registry — realistic module for preorder examples.

This file demonstrates the **abstraction** strategy (callee before caller).
Unlike ``stepdown`` (top-down narrative), ``abstraction`` puts low-level
building blocks *first* and high-level orchestration *last* — which reads
naturally for plugin/middleware systems where you want to see the primitives
before the pipeline that wires them together.

Run with::

    preorder run  tests/data/plugin_registry_unsorted.py \\
        --strategy-overrides functions=abstraction,classes=abstraction

The authoritative sorted output (``plugin_registry_sorted.py``) was generated
with ``Config(strategies={"functions": "abstraction"})``.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from collections.abc import Callable  # noqa: F401


class Hook(enum.Enum):
    """Lifecycle hooks that plugins can subscribe to."""

    BEFORE_RUN = "before_run"
    AFTER_RUN = "after_run"
    ON_ERROR = "on_error"


@dataclass
class PluginContext:
    """Context passed to every plugin hook invocation."""

    name: str
    config: dict[str, str] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


class PluginError(Exception):
    """Raised when a plugin fails unrecoverably."""

    def __init__(self, hook: Hook, cause: str) -> None:
        super().__init__(f"plugin error in {hook.value}: {cause}")
        self.hook = hook
        self.cause = cause


def _resolve_handler(target: object, hook: Hook) -> object:
    """Look up the method on *target* that matches *hook* (leaf utility)."""
    attr = hook.value
    return getattr(target, attr, None)


def _invoke_hook(target: object, hook: Hook, ctx: PluginContext) -> None:
    """Dispatch a single *hook* on *target*, collecting errors.

    Sits between the orchestrator and the leaf utilities.
    """
    handler = _resolve_handler(target, hook)
    if handler is None:
        return
    try:
        handler(ctx)
    except Exception as exc:  # noqa: BLE001
        ctx.errors.append(str(exc))
        if hook == Hook.ON_ERROR:
            raise PluginError(hook, str(exc)) from exc


def run_pipeline(ctx: PluginContext, plugins: list) -> PluginContext:
    """Top-level orchestrator: execute every plugin's hooks in sequence.

    This is the highest-level caller — with ``abstraction`` it sinks to the
    bottom so readers see the building blocks first.
    """
    for plugin in plugins:
        _invoke_hook(plugin, Hook.BEFORE_RUN, ctx)
    _invoke_hook(ctx, Hook.AFTER_RUN, ctx)
    return ctx


def build_default_plugins() -> list:
    """Return the default plugin stack (factory / leaf utility)."""
    return []


if __name__ == "__main__":
    context = PluginContext(name="demo")
    result = run_pipeline(context, build_default_plugins())
    print(f"errors={len(result.errors)}")
