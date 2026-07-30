"""Configuration discovery and parsing for clean-sort.

Config is read from (first match wins, walking up from the target file):

* ``--config PATH`` (explicit)
* ``csort.toml`` in the current or any parent directory
* ``.config/csort.toml`` in the current or any parent directory
* ``[tool.csort]`` in ``pyproject.toml``

"""

from __future__ import annotations

import tomllib
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

#: Section buckets recognised by the classifier in their canonical order.
RECOGNIZED_SECTIONS: tuple[str, ...] = (
    "imports",
    "typing_imports",
    "module_constants",
    "enums",
    "dataclasses",
    "classes",
    "functions",
    "main_block",
)

DEFAULT_SECTIONS: list[str] = list(RECOGNIZED_SECTIONS)

VALID_STRATEGIES: frozenset[str] = frozenset({"keep", "alpha", "stepdown", "abstraction"})
_VALID_VIS = frozenset({"public", "protected", "private"})
_VALID_MTYPES = frozenset({"instance", "class", "static"})

CSORT_FILES: tuple[str, ...] = ("csort.toml", ".config/csort.toml")


@dataclass
class Config:
    """Resolved clean-sort configuration.

    Attributes:
        sections: Ordered list of section buckets; top-level statements are
            grouped into these in the order given.
        strategies: Per-section in-section strategy. Sections missing from this
            mapping default to ``"keep"``.
        class_methods_enabled: Reorder methods *within* each class (undersort).
        class_methods_order: Method visibility ordering.
        class_methods_type_order: Method-type ordering within each visibility.
        constants_pattern: Regex for the ``module_constants`` classification.
        unknown_section: Bucket name for unrecognised top-level nodes. Nodes in a
            bucket that is absent from ``sections`` are appended at the end,
            preserving their original relative order.
        hoist_inline_imports: Move imports nested inside function/class bodies to
            the top of the module (pre-pass before section sorting).
        remove_type_checking: Delete ``if TYPE_CHECKING:`` guards and hoist the
            imports they contained to the top of the module (pre-pass).
        fail_on_changed: When ``True`` (default), ``csort run`` exits with code 1
            when any file was modified. Pre-commit/CI friendly. Set to ``False``
            via ``[cli] fail_on_changed = false`` or ``--no-fail``.
        config_path: Where the config was loaded from (``None`` = pure defaults).
    """

    sections: list[str] = field(default_factory=lambda: list(DEFAULT_SECTIONS))
    strategies: dict[str, SectionStrategy] = field(default_factory=dict)
    class_methods_enabled: bool = True
    class_methods_order: list[str] = field(default_factory=lambda: ["public", "protected", "private"])
    class_methods_type_order: list[str] = field(default_factory=lambda: ["instance", "class", "static"])
    constants_pattern: str = r"^[A-Z_][A-Z0-9_]*$"
    unknown_section: str = "other"
    hoist_inline_imports: bool = False
    remove_type_checking: bool = False
    fail_on_changed: bool = True
    config_path: Path | None = None

    def strategy(self, section: str) -> SectionStrategy:
        """In-section strategy for ``section`` (``"keep"`` if unset)."""
        return self.strategies.get(section, "keep")

    # ------------------------------------------------------------------ build
    @classmethod
    def from_table(
        cls,
        data: dict[str, Any],
        *,
        path: Path | None = None,
        raw: dict[str, Any] | None = None,
        is_pyproject: bool = False,
    ) -> Config:
        """Build a :class:`Config` from a parsed ``csort`` table."""
        cfg = cls(config_path=path)

        module = data.get("module", {}) or {}
        if isinstance(module, dict) and "sections" in module:
            sections = module["sections"]
            if isinstance(sections, list) and all(isinstance(s, str) for s in sections):
                cfg.sections = [s for s in sections if isinstance(s, str)]

        strategy = data.get("strategy", {}) or {}
        if isinstance(strategy, dict):
            for name, value in strategy.items():
                if not isinstance(name, str):
                    continue
                if value in VALID_STRATEGIES:
                    cfg.strategies[name] = value
                else:
                    warnings.warn(
                        f"csort: unknown strategy {value!r} for section {name!r}; ignoring",
                        stacklevel=2,
                    )

        cm = data.get("class_methods", {}) or {}
        if isinstance(cm, dict) and cm:
            cfg._apply_class_methods(cm)
        elif raw is not None:
            cfg._apply_class_methods(_legacy_undersort_overrides(raw, is_pyproject=is_pyproject))

        classification = data.get("classification", {}) or {}
        if isinstance(classification, dict) and "constants_pattern" in classification:
            pattern = classification["constants_pattern"]
            if isinstance(pattern, str):
                cfg.constants_pattern = pattern

        transforms = data.get("transforms", {}) or {}
        if isinstance(transforms, dict):
            if "hoist_inline_imports" in transforms:
                cfg.hoist_inline_imports = bool(transforms["hoist_inline_imports"])
            if "remove_type_checking" in transforms:
                cfg.remove_type_checking = bool(transforms["remove_type_checking"])

        cli = data.get("cli", {}) or {}
        if isinstance(cli, dict) and "fail_on_changed" in cli:
            cfg.fail_on_changed = bool(cli["fail_on_changed"])

        return cfg

    def _set_order(self, value: Any, *, attr: str) -> None:
        valid = _VALID_VIS if attr == "class_methods_order" else _VALID_MTYPES
        getattr(self, attr)
        if isinstance(value, list) and value and all(v in valid for v in value):
            setattr(self, attr, list(value))
        elif value is not None:
            warnings.warn(f"csort: invalid {attr}={value!r}; using default", stacklevel=2)
            # keep default

    def _apply_class_methods(self, cm: dict[str, Any]) -> None:
        """Apply a ``class_methods`` table (either csort or legacy undersort).

        ``enabled`` is csort-only; the legacy schema predates that key, so it
        defaults to the current value when absent.
        """
        if "enabled" in cm:
            self.class_methods_enabled = bool(cm["enabled"])
        self._set_order(cm.get("order"), attr="class_methods_order")
        self._set_order(cm.get("method_type_order"), attr="class_methods_type_order")


def _legacy_undersort_overrides(data: dict[str, Any], *, is_pyproject: bool) -> dict[str, Any]:
    """Pull ``class_methods`` overrides from a legacy ``[undersort]`` table.

    Two spellings are honored:

    * ``[tool.undersort]`` in ``pyproject.toml``;
    * ``[undersort]`` (or ``[tool.undersort]``) inside a standalone config.

    Only ``order`` and ``method_type_order`` are part of the legacy schema; an
    empty result falls through to the csort defaults.
    """
    candidates: list[dict[str, Any]] = []
    if is_pyproject:
        candidates.append(data.get("tool", {}).get("undersort") or {})
    else:
        candidates.append(data.get("undersort") or {})
        candidates.append(data.get("tool", {}).get("undersort") or {})
    for table in candidates:
        if isinstance(table, dict) and table:
            return table
    return {}


def _read_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as fh:
        return tomllib.load(fh)


def _csort_table_from_data(data: dict[str, Any], *, is_pyproject: bool) -> dict[str, Any]:
    """Extract the csort config table from parsed TOML data."""
    if is_pyproject:
        return data.get("tool", {}).get("csort", {}) or {}
    # standalone csort.toml: top-level is the csort config, but tolerate a
    # [tool.csort] table too.
    if "csort" in data.get("tool", {}):
        return data["tool"]["csort"] or {}
    return data


def discover(start: Path | None = None) -> Path | None:
    """Walk up from ``start`` (cwd by default) to find a clean-sort config file."""
    base = (start or Path.cwd()).resolve()
    for directory in [base, *base.parents]:
        for rel in CSORT_FILES:
            candidate = directory / rel
            if candidate.is_file():
                return candidate
        pyproject = directory / "pyproject.toml"
        if pyproject.is_file():
            try:
                data = _read_toml(pyproject)
            except (tomllib.TOMLDecodeError, OSError):
                continue
            tool = data.get("tool", {})
            if tool.get("csort"):
                return pyproject
    return None


def load(
    *,
    explicit: Path | None = None,
    start: Path | None = None,
) -> Config:
    """Load a resolved :class:`Config`.

    ``explicit`` overrides discovery. ``start`` is the directory to search from
    (defaults to cwd) and is ignored when ``explicit`` is given.
    """
    path = explicit or discover(start)
    if path is None:
        return Config()
    try:
        data = _read_toml(path)
    except tomllib.TOMLDecodeError as exc:
        warnings.warn(f"csort: could not parse {path}: {exc}; using defaults", stacklevel=2)
        return Config(config_path=path)

    is_pyproject = path.name == "pyproject.toml"
    table = _csort_table_from_data(data, is_pyproject=is_pyproject)
    cfg = Config.from_table(table, path=path, raw=data, is_pyproject=is_pyproject)

    return cfg


SectionStrategy = Literal["keep", "alpha", "stepdown", "abstraction"]
