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
from hashlib import sha256
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from json import dumps as _json_dumps
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
        exclude: Glob patterns to exclude during file discovery (merged with
            ``--exclude`` flags).
        recursive: Whether file discovery descends into subdirectories
            (default ``True``). ``--no-recursive`` overrides per-invocation.
        cache_enabled: When ``True`` (default), skip parsing/sorting for files
            whose content hash matches a cached sorted-output hash. Disable
            via ``[cli] cache = false`` or ``--no-cache``.
        cache_dir: Directory storing the content-hash cache. Defaults to
            ``~/.cache/csort/<project-slug>`` (or ``./.csort-cache/`` when
            configured). Overrides via ``[cli] cache_dir``.
        jobs: Number of parallel workers (0 = serial, negative = auto-detect
            ``int(0.75 * cpu_count())``). Configurable via ``[cli] jobs`` or
            ``--jobs``/``-j``.
        parallel_backend: Parallel execution backend — ``"process"``
            (multiprocessing, default) or ``"thread"`` (threading).
            Configurable via ``[cli] parallel_backend`` or ``--parallel-backend``.
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
    exclude: list[str] = field(default_factory=list)
    recursive: bool = True
    cache_enabled: bool = True
    cache_dir: Path | None = None
    jobs: int = 0
    parallel_backend: str = "process"
    config_path: Path | None = None

    def strategy(self, section: str) -> SectionStrategy:
        """In-section strategy for ``section`` (``"keep"`` if unset)."""
        return self.strategies.get(section, "keep")

    def config_signature(self) -> str:
        """Stable hash of the output-affecting fields + csort version.

        Used as part of the content-hash cache key. Changes to any field that
        affects sorted output, or to the csort version, invalidate the cache.
        Non-output fields (``fail_on_changed``, ``exclude``, ``recursive``,
        ``unknown_section``, ``cache_*``, ``config_path``) are excluded.
        """
        try:
            ver = _pkg_version("clean-sort")
        except PackageNotFoundError:
            ver = "0.0.0"
        relevant = {
            "sections": self.sections,
            "strategies": self.strategies,
            "class_methods_enabled": self.class_methods_enabled,
            "class_methods_order": self.class_methods_order,
            "class_methods_type_order": self.class_methods_type_order,
            "constants_pattern": self.constants_pattern,
            "hoist_inline_imports": self.hoist_inline_imports,
            "remove_type_checking": self.remove_type_checking,
            "version": ver,
        }
        payload = _json_dumps(relevant, sort_keys=True).encode()
        return sha256(payload).hexdigest()[:16]

    # ------------------------------------------------------------------ build
    @classmethod
    def from_table(  # noqa: PLR0915
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
        if isinstance(cli, dict):
            if "fail_on_changed" in cli:
                cfg.fail_on_changed = bool(cli["fail_on_changed"])
            if "cache" in cli:
                cfg.cache_enabled = bool(cli["cache"])
            if "cache_dir" in cli:
                cache_dir = cli["cache_dir"]
                if isinstance(cache_dir, str):
                    cfg.cache_dir = Path(cache_dir)
                else:
                    warnings.warn(
                        "csort: cli.cache_dir must be a string; ignoring",
                        stacklevel=2,
                    )
            if "jobs" in cli:
                jobs = cli["jobs"]
                if isinstance(jobs, int):
                    cfg.jobs = jobs
                else:
                    warnings.warn(
                        "csort: cli.jobs must be an integer; ignoring",
                        stacklevel=2,
                    )
            if "parallel_backend" in cli:
                backend = cli["parallel_backend"]
                if isinstance(backend, str) and backend in ("process", "thread"):
                    cfg.parallel_backend = backend
                else:
                    warnings.warn(
                        "csort: cli.parallel_backend must be 'process' or 'thread'; ignoring",
                        stacklevel=2,
                    )

        discovery = data.get("discovery", {}) or {}
        if isinstance(discovery, dict):
            if "exclude" in discovery:
                exclude = discovery["exclude"]
                if isinstance(exclude, list) and all(isinstance(p, str) for p in exclude):
                    cfg.exclude = [str(p) for p in exclude]
                else:
                    warnings.warn(
                        "csort: discovery.exclude must be a list of strings; ignoring",
                        stacklevel=2,
                    )
            if "recursive" in discovery:
                cfg.recursive = bool(discovery["recursive"])

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
