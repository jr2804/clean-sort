"""``pyreorder`` command-line interface.

Commands
--------
run     sort files in place (or stdin -> stdout with ``-``)
check   exit non-zero if any file would change (for CI / pre-commit)
diff    print unified diffs of the changes pyreorder would make
config  show resolved config or write a ``pyreorder.toml`` template
"""

from __future__ import annotations

import difflib
import fnmatch
import sys
import time
import warnings
from hashlib import sha256
from pathlib import Path
from typing import Annotated, cast

import typer

from pyreorder import VALID_STRATEGIES, Config, __version__, load_config, sort_source
from pyreorder.cache import Cache, CacheEntry, hash_text
from pyreorder.config import _VALID_MTYPES, _VALID_VIS, SectionStrategy, generate_config, validate_config_keys

# `app`/`config_app` are runtime setup used by the decorators below; pyreorder treats
# such unrecognised top-level statements as barriers and will not move them.
app = typer.Typer(
    name="pyreorder",
    help="AST-based structural sorter for Python source code.",
    no_args_is_help=True,
    add_completion=True,
)
config_app = typer.Typer(help="Manage pyreorder configuration.", no_args_is_help=True)
app.add_typer(config_app, name="config")

_EXCLUDE_DIRS = frozenset(
    {
        "venv",
        ".venv",
        "env",
        ".env",
        "__pycache__",
        "node_modules",
        ".git",
        "build",
        "dist",
        ".tox",
        ".mypy_cache",
        ".pytest_cache",
        "site-packages",
    }
)

ConfigOpt = Annotated[
    Path | None,
    typer.Option("--config", help="Path to pyreorder.toml or pyproject.toml."),
]
ExcludeOpt = Annotated[
    list[str] | None,
    typer.Option("--exclude", "-x", help="Glob pattern to exclude (repeatable)."),
]
NoRecursiveOpt = Annotated[
    bool,
    typer.Option("--no-recursive", help="Do not descend into subdirectories."),
]
NoClassMethodsOpt = Annotated[
    bool,
    typer.Option("--no-class-methods", help="Disable in-class method sorting."),
]
SectionOnlyOpt = Annotated[
    str | None,
    typer.Option(
        "--section-only",
        help="Restrict reordering to these comma-separated sections (others stay in place).",
    ),
]
StrategyOverridesOpt = Annotated[
    str | None,
    typer.Option(
        "--strategy-overrides",
        help="Override per-section strategies, e.g. 'functions=alpha,classes=keep'.",
    ),
]
ClassMethodsOrderOpt = Annotated[
    str | None,
    typer.Option(
        "--class-methods-order",
        help="Override method visibility order, e.g. 'public,protected,private'.",
    ),
]
MethodTypeOrderOpt = Annotated[
    str | None,
    typer.Option(
        "--method-type-order",
        help="Override method-type order, e.g. 'instance,class,static'.",
    ),
]
HoistInlineImportsOpt = Annotated[
    bool,
    typer.Option(
        "--hoist-inline-imports",
        help="Move imports nested inside function bodies to the top of the module.",
    ),
]
HoistMainImportsOpt = Annotated[
    bool | None,
    typer.Option(
        "--hoist-main-imports/--no-hoist-main-imports",
        help="Move imports from inside if __name__ == '__main__': to the top (default: on).",
    ),
]
RemoveTypeCheckingOpt = Annotated[
    bool,
    typer.Option(
        "--remove-type-checking",
        help="Delete if TYPE_CHECKING: guards and hoist their imports to module level.",
    ),
]
NoFailOpt = Annotated[
    bool | None,
    typer.Option(
        "--fail/--no-fail",
        help="Exit non-zero when files were changed (default: from config, or on; --no-fail exits 0).",
    ),
]
NoCacheOpt = Annotated[
    bool,
    typer.Option(
        "--no-cache",
        help="Disable the content-hash skip cache (forces full sort on every file).",
    ),
]
CacheTtlDaysOpt = Annotated[
    int | None,
    typer.Option(
        "--cache-ttl",
        help="Days before an unseen cache entry is pruned (0 = never; default from config).",
    ),
]
JobsOpt = Annotated[
    int | None,
    typer.Option(
        "--jobs",
        "-j",
        help="Number of parallel workers (0=serial, negative=auto).",
    ),
]
ParallelBackendOpt = Annotated[
    str | None,
    typer.Option(
        "--parallel-backend",
        help="Parallel backend: 'process' (default) or 'thread'.",
    ),
]
PathsArg = Annotated[
    list[Path] | None,
    typer.Argument(help="Python files or directories to sort. Use '-' for stdin."),
]


# ------------------------------------------------------------------------ config
@app.callback(invoke_without_command=True)
def _main(
    ctx: typer.Context,
    version: Annotated[
        bool,
        typer.Option("--version", "-V", is_eager=True, help="Show version and exit."),
    ] = False,
) -> None:
    """AST-based structural sorter for Python source code."""
    if version:
        typer.echo(__version__)
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        typer.echo(__version__)


@app.command()
def version() -> None:
    """Show the pyreorder version."""
    typer.echo(__version__)


# ----------------------------------------------------------------- file helpers
def _parse_permutation(value: str, *, valid: frozenset[str], flag: str) -> list[str]:
    """Parse and validate a comma-separated permutation of ``valid`` values."""
    items = [item.strip() for item in value.split(",") if item.strip()]
    if set(items) != set(valid):
        warnings.warn(
            f"pyreorder: {flag}={value!r} must be a permutation of {sorted(valid)}; ignoring",
            stacklevel=2,
        )
        return []
    return items


def _build_config(
    explicit: Path | None,
    no_class_methods: bool,
    section_only: str | None = None,
    strategy_overrides: str | None = None,
    hoist_inline_imports: bool = False,
    hoist_main_imports: bool | None = None,
    remove_type_checking: bool = False,
    class_methods_order: str | None = None,
    method_type_order: str | None = None,
    fail: bool | None = None,
    cache_ttl_days: int | None = None,
) -> Config:
    cfg = load_config(explicit=explicit, start=Path.cwd())
    if no_class_methods:
        cfg.class_methods_enabled = False
    if hoist_inline_imports:
        cfg.hoist_inline_imports = True
    if hoist_main_imports is not None:
        cfg.hoist_main_imports = hoist_main_imports
    if remove_type_checking:
        cfg.remove_type_checking = True
    if cache_ttl_days is not None:
        cfg.cache_ttl_days = cache_ttl_days
    if section_only:
        cfg.sections = [s.strip() for s in section_only.split(",") if s.strip()]
    if strategy_overrides:
        for raw in strategy_overrides.split(","):
            item = raw.strip()
            if not item or "=" not in item:
                warnings.warn(f"pyreorder: ignoring malformed strategy override {item!r}", stacklevel=2)
                continue
            name, value = item.split("=", 1)
            name, value = name.strip(), value.strip()
            if value in VALID_STRATEGIES:
                cfg.strategies[name] = cast(SectionStrategy, value)
            else:
                warnings.warn(
                    f"pyreorder: unknown strategy {value!r} for section {name!r}; ignoring",
                    stacklevel=2,
                )
    if class_methods_order:
        parsed = _parse_permutation(class_methods_order, valid=_VALID_VIS, flag="--class-methods-order")
        if parsed:
            cfg.class_methods_order = parsed
    if method_type_order:
        parsed = _parse_permutation(method_type_order, valid=_VALID_MTYPES, flag="--method-type-order")
        if parsed:
            cfg.class_methods_type_order = parsed
    if fail is not None:
        cfg.fail_on_changed = fail
    return cfg


def _collect(paths: list[Path], recursive: bool, excludes: list[str] | None) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.name == "-":
            continue
        if path.is_file():
            if path.suffix == ".py":
                files.append(path)
        elif path.is_dir():
            pattern = "**/*.py" if recursive else "*.py"
            files.extend(sorted(path.glob(pattern)))
    result: list[Path] = []
    seen: set[str] = set()
    for file in files:
        if any(part in _EXCLUDE_DIRS for part in file.parts):
            continue
        if excludes and any(fnmatch.fnmatch(str(file), pat) or fnmatch.fnmatch(file.name, pat) for pat in excludes):
            continue
        key = str(file.resolve())
        if key not in seen:
            seen.add(key)
            result.append(file)
    return result


def _diff(original: str, result: str, name: str) -> str:
    return "".join(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            result.splitlines(keepends=True),
            fromfile=name,
            tofile=name,
        )
    )


def _process_stdin(cfg: Config, mode: str) -> int:
    source = sys.stdin.read()
    try:
        result = sort_source(source, cfg, filename="<stdin>")
    except Exception as exc:  # noqa: BLE001 - surface as CLI error
        typer.echo(f"pyreorder: error: {exc}", err=True)
        return 2
    if mode == "run":
        sys.stdout.write(result)
        return 0
    if mode == "check":
        return 1 if result != source else 0
    if mode == "diff" and result != source:
        sys.stdout.write(_diff(source, result, "<stdin>"))
    return 0


def _resolve_cache_dir(cfg: Config, *, use_cache: bool) -> Path | None:
    """Resolve the cache directory, or ``None`` when caching is disabled.

    Priority:
    1. Explicitly disabled (``use_cache=False`` or ``cfg.cache_enabled=False``) → None.
    2. ``cfg.cache_dir`` if set (config or CLI override).
    3. ``~/.cache/pyreorder/<slug>`` where slug is derived from the config file's
       absolute parent directory (stable across runs, collision-resistant).
    """
    if not use_cache or not cfg.cache_enabled:
        return None
    if cfg.cache_dir is not None:
        return cfg.cache_dir
    # Derive a stable project slug from the config's location.
    base = cfg.config_path.resolve().parent if cfg.config_path else Path.cwd()
    slug = sha256(str(base.resolve()).encode("utf-8")).hexdigest()[:12]
    return Path.home() / ".cache" / "pyreorder" / slug


def _process_files(
    files: list[Path],
    cfg: Config,
    mode: str,
    *,
    cache: Cache | None = None,
) -> tuple[int, list[Path]]:
    config_sig = cfg.config_signature() if cache is not None else None
    changed: list[Path] = []
    errored = False
    for file in files:
        try:
            original = file.read_text(encoding="utf-8")
        except OSError as exc:
            typer.echo(f"pyreorder: cannot read {file}: {exc}", err=True)
            errored = True
            continue
        # Cache lookup: skip the file if its current content matches the
        # cached sorted-output hash. Only applies to run/check; diff always
        # computes to show the delta.
        if cache is not None and config_sig is not None and mode in ("run", "check"):
            source_hash = hash_text(original)
            if cache.lookup(config_sig, source_hash, source_hash):
                continue
        try:
            result = sort_source(original, cfg, filename=str(file))
        except Exception as exc:  # noqa: BLE001
            typer.echo(f"pyreorder: error in {file}: {exc}", err=True)
            errored = True
            continue
        if cache is not None and config_sig is not None and mode in ("run", "check"):
            source_hash = hash_text(original)
            cache.record(config_sig, source_hash, hash_text(result if result != original else original))
        if result == original:
            continue
        changed.append(file)
        if mode == "run":
            file.write_text(result, encoding="utf-8")
            typer.echo(f"sorted: {file}")
        elif mode == "check":
            typer.echo(f"would sort: {file}")
        elif mode == "diff":
            typer.echo(_diff(original, result, str(file)), nl=False)
    code = 0
    if (mode == "check" and changed) or (mode == "run" and changed and cfg.fail_on_changed):
        code = 1
    if errored:
        code = max(code, 2)
    return code, changed


# ---------------------------------------------------------------- parallel


def _sort_one(args: tuple) -> tuple:  # noqa: ANN401
    """Worker: sort a single file. Module-level for Windows spawn.

    Returns ``(path_str, changed, error_msg, diff_text, cache_entries)``.
    ``cache_entries`` is a ``{key: CacheEntry}`` dict, or ``None`` when caching
    is disabled. The main process merges and writes these centrally.
    """
    path_str, cfg_dict, mode, cache_path_str, config_sig = args
    from pathlib import Path  # noqa: PLC0415

    from pyreorder import Config, sort_source  # noqa: PLC0415
    from pyreorder.cache import Cache, hash_text  # noqa: PLC0415

    cfg = Config(**cfg_dict)
    path = Path(path_str)
    try:
        original = path.read_text(encoding="utf-8")
    except OSError as exc:
        return (path_str, False, f"pyreorder: cannot read {path}: {exc}", "", None)
    # Cache lookup (read-only — no save)
    cache_entries: dict[str, CacheEntry] | None = None
    if cache_path_str and config_sig and mode in ("run", "check"):
        cache = Cache(Path(cache_path_str), ttl_days=cfg.cache_ttl_days)
        cache.load()
        source_hash = hash_text(original)
        if cache.lookup(config_sig, source_hash, source_hash):
            return (path_str, False, None, "", None)
    try:
        result = sort_source(original, cfg, filename=str(path))
    except Exception as exc:  # noqa: BLE001
        return (path_str, False, f"pyreorder: error in {path}: {exc}", "", None)
    # Collect cache entries (returned to main process for centralised write)
    if cache_path_str and config_sig and mode in ("run", "check"):
        source_hash = hash_text(original)
        sorted_hash = hash_text(result if result != original else original)
        cache_entries = {f"{config_sig}:{source_hash}": {"hash": sorted_hash, "seen": time.time()}}
    if result == original:
        return (path_str, False, None, "", cache_entries)
    changed = True
    diff_text = ""
    if mode == "run":
        path.write_text(result, encoding="utf-8")
    elif mode == "diff":
        import difflib  # noqa: PLC0415

        diff_text = "".join(
            difflib.unified_diff(
                original.splitlines(keepends=True),
                result.splitlines(keepends=True),
                fromfile=str(path),
                tofile=str(path),
            )
        )
    return (path_str, changed, None, diff_text, cache_entries)


def _process_files_parallel(
    files: list[Path],
    cfg: Config,
    mode: str,
    *,
    cache: Cache | None = None,
    jobs: int,
    backend: str,
) -> tuple[int, list[Path]]:
    """Sort files in parallel using a process or thread pool."""
    import multiprocessing  # noqa: PLC0415
    from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor  # noqa: PLC0415

    if jobs < 0:
        jobs = max(1, int(0.75 * multiprocessing.cpu_count()))
    jobs = min(jobs, len(files))
    if jobs < 2:
        return _process_files(files, cfg, mode, cache=cache)

    config_sig = cfg.config_signature() if cache is not None else None
    cache_path = str(cache.path) if cache is not None and cache.path is not None else ""
    cfg_dict = {
        "sections": cfg.sections,
        "strategies": cfg.strategies,
        "class_methods_enabled": cfg.class_methods_enabled,
        "class_methods_order": cfg.class_methods_order,
        "class_methods_type_order": cfg.class_methods_type_order,
        "constants_pattern": cfg.constants_pattern,
        "hoist_inline_imports": cfg.hoist_inline_imports,
        "hoist_main_imports": cfg.hoist_main_imports,
        "remove_type_checking": cfg.remove_type_checking,
        "cache_ttl_days": cfg.cache_ttl_days,
        "fail_on_changed": cfg.fail_on_changed,
        "exclude": cfg.exclude,
        "recursive": cfg.recursive,
        "cache_enabled": cfg.cache_enabled,
        "cache_dir": cfg.cache_dir,
        "jobs": cfg.jobs,
        "parallel_backend": cfg.parallel_backend,
    }
    args_list = [(str(f), cfg_dict, mode, cache_path, config_sig) for f in files]

    Executor = ProcessPoolExecutor if backend == "process" else ThreadPoolExecutor
    changed: list[Path] = []
    errored = False
    with Executor(max_workers=jobs) as ex:
        results = list(ex.map(_sort_one, args_list))
    # Collect results in original file order; merge cache entries centrally
    all_cache_entries: dict[str, CacheEntry] = {}
    for path_str, changed_flag, error_msg, diff_text, cache_entries in results:
        if error_msg:
            typer.echo(error_msg, err=True)
            errored = True
        if changed_flag:
            changed.append(Path(path_str))
            if mode == "run":
                typer.echo(f"sorted: {path_str}")
            elif mode == "check":
                typer.echo(f"would sort: {path_str}")
            elif mode == "diff" and diff_text:
                typer.echo(diff_text, nl=False)
        if cache_entries:
            all_cache_entries.update(cache_entries)
    # Write cache centrally (single process, no race)
    if cache is not None and all_cache_entries:
        cache.merge(all_cache_entries)
        cache.save()
    code = 0
    if (mode == "check" and changed) or (mode == "run" and changed and cfg.fail_on_changed):
        code = 1
    if errored:
        code = max(code, 2)
    return code, changed


def _run(
    paths: list[Path] | None,
    mode: str,
    config: Path | None,
    exclude: list[str] | None,
    no_recursive: bool,
    no_class_methods: bool,
    section_only: str | None = None,
    strategy_overrides: str | None = None,
    hoist_inline_imports: bool = False,
    hoist_main_imports: bool | None = None,
    remove_type_checking: bool = False,
    class_methods_order: str | None = None,
    method_type_order: str | None = None,
    fail: bool | None = None,
    no_cache: bool = False,
    cache_ttl_days: int | None = None,
    jobs: int | None = None,
    parallel_backend: str | None = None,
) -> None:
    cfg = _build_config(
        config,
        no_class_methods,
        section_only,
        strategy_overrides,
        hoist_inline_imports=hoist_inline_imports,
        hoist_main_imports=hoist_main_imports,
        remove_type_checking=remove_type_checking,
        class_methods_order=class_methods_order,
        method_type_order=method_type_order,
        fail=fail,
        cache_ttl_days=cache_ttl_days,
    )
    paths = paths or [Path.cwd()]
    if any(p.name == "-" for p in paths):
        raise typer.Exit(_process_stdin(cfg, mode))
    effective_excludes = [*cfg.exclude, *(exclude or [])]
    effective_recursive = cfg.recursive and not no_recursive
    files = _collect(paths, recursive=effective_recursive, excludes=effective_excludes)
    if not files:
        typer.echo("pyreorder: no Python files found")
        raise typer.Exit(0)
    cache_dir = _resolve_cache_dir(cfg, use_cache=not no_cache)
    cache = Cache(cache_dir / "cache.json" if cache_dir is not None else None, ttl_days=cfg.cache_ttl_days)
    if cache.path is not None:
        cache.load()
    # Resolve parallelism
    effective_jobs = jobs if jobs is not None else cfg.jobs
    effective_backend = parallel_backend if parallel_backend is not None else cfg.parallel_backend
    if effective_jobs != 0:
        code, changed = _process_files_parallel(
            files,
            cfg,
            mode,
            cache=cache,
            jobs=effective_jobs,
            backend=effective_backend,
        )
    else:
        code, changed = _process_files(files, cfg, mode, cache=cache)
    cache.save()
    if mode == "run":
        typer.echo(f"done: {len(changed)} file(s) sorted of {len(files)} scanned")
    elif mode == "check" and not changed:
        typer.echo(f"ok: {len(files)} file(s) already sorted")
    raise typer.Exit(code)


# ---------------------------------------------------------------------- commands
@app.command()
def run(
    paths: PathsArg = None,
    config: ConfigOpt = None,
    exclude: ExcludeOpt = None,
    no_recursive: NoRecursiveOpt = False,
    no_class_methods: NoClassMethodsOpt = False,
    section_only: SectionOnlyOpt = None,
    strategy_overrides: StrategyOverridesOpt = None,
    hoist_inline_imports: HoistInlineImportsOpt = False,
    hoist_main_imports: HoistMainImportsOpt = None,
    remove_type_checking: RemoveTypeCheckingOpt = False,
    class_methods_order: ClassMethodsOrderOpt = None,
    method_type_order: MethodTypeOrderOpt = None,
    fail: NoFailOpt = None,
    no_cache: NoCacheOpt = False,
    cache_ttl_days: CacheTtlDaysOpt = None,
    jobs: JobsOpt = None,
    parallel_backend: ParallelBackendOpt = None,
) -> None:
    """Sort Python files in place (or stdin -> stdout with ``-``).

    Exits with code 1 if any file was changed (pre-commit / CI friendly),
    2 on errors. stdin mode always exits 0. Use ``--no-fail`` to exit 0
    even when files changed (e.g. from a formatter task that always writes).
    """
    _run(
        paths,
        "run",
        config,
        exclude,
        no_recursive,
        no_class_methods,
        section_only,
        strategy_overrides,
        hoist_inline_imports=hoist_inline_imports,
        hoist_main_imports=hoist_main_imports,
        remove_type_checking=remove_type_checking,
        class_methods_order=class_methods_order,
        method_type_order=method_type_order,
        fail=fail,
        no_cache=no_cache,
        cache_ttl_days=cache_ttl_days,
        jobs=jobs,
        parallel_backend=parallel_backend,
    )


@app.command()
def check(
    paths: PathsArg = None,
    config: ConfigOpt = None,
    exclude: ExcludeOpt = None,
    no_recursive: NoRecursiveOpt = False,
    no_class_methods: NoClassMethodsOpt = False,
    section_only: SectionOnlyOpt = None,
    strategy_overrides: StrategyOverridesOpt = None,
    hoist_inline_imports: HoistInlineImportsOpt = False,
    hoist_main_imports: HoistMainImportsOpt = None,
    remove_type_checking: RemoveTypeCheckingOpt = False,
    class_methods_order: ClassMethodsOrderOpt = None,
    method_type_order: MethodTypeOrderOpt = None,
    no_cache: NoCacheOpt = False,
    cache_ttl_days: CacheTtlDaysOpt = None,
    jobs: JobsOpt = None,
    parallel_backend: ParallelBackendOpt = None,
) -> None:
    """Exit non-zero if any file would be changed by sorting."""
    _run(
        paths,
        "check",
        config,
        exclude,
        no_recursive,
        no_class_methods,
        section_only,
        strategy_overrides,
        hoist_inline_imports=hoist_inline_imports,
        hoist_main_imports=hoist_main_imports,
        remove_type_checking=remove_type_checking,
        class_methods_order=class_methods_order,
        method_type_order=method_type_order,
        no_cache=no_cache,
        cache_ttl_days=cache_ttl_days,
        jobs=jobs,
        parallel_backend=parallel_backend,
    )


@app.command()
def diff(
    paths: PathsArg = None,
    config: ConfigOpt = None,
    exclude: ExcludeOpt = None,
    no_recursive: NoRecursiveOpt = False,
    no_class_methods: NoClassMethodsOpt = False,
    section_only: SectionOnlyOpt = None,
    strategy_overrides: StrategyOverridesOpt = None,
    hoist_inline_imports: HoistInlineImportsOpt = False,
    hoist_main_imports: HoistMainImportsOpt = None,
    remove_type_checking: RemoveTypeCheckingOpt = False,
    class_methods_order: ClassMethodsOrderOpt = None,
    method_type_order: MethodTypeOrderOpt = None,
    no_cache: NoCacheOpt = False,
    cache_ttl_days: CacheTtlDaysOpt = None,
    jobs: JobsOpt = None,
    parallel_backend: ParallelBackendOpt = None,
) -> None:
    """Print unified diffs of the changes pyreorder would make."""
    _run(
        paths,
        "diff",
        config,
        exclude,
        no_recursive,
        no_class_methods,
        section_only,
        strategy_overrides,
        hoist_inline_imports=hoist_inline_imports,
        hoist_main_imports=hoist_main_imports,
        remove_type_checking=remove_type_checking,
        class_methods_order=class_methods_order,
        method_type_order=method_type_order,
        no_cache=no_cache,
        cache_ttl_days=cache_ttl_days,
        jobs=jobs,
        parallel_backend=parallel_backend,
    )


@config_app.command("generate")
def config_generate(
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Write to this file (must end in .toml)."),
    ] = None,
    with_comments: Annotated[
        bool,
        typer.Option("--with-comments", help="Emit explanatory comments for each setting."),
    ] = False,
    with_config: Annotated[
        Path | None,
        typer.Option(
            "--with-config",
            help="Merge values from an existing config; invalid entries are dropped with warnings.",
        ),
    ] = None,
    force: Annotated[bool, typer.Option("--force", help="Overwrite an existing output file.")] = False,
) -> None:
    """Generate a pyreorder.toml config (default template, or merged from an existing one).

    Without options, prints the default template. With ``--output`` writes it to
    a file (must end in ``.toml``). With ``--with-config``, carries recognized
    values from an existing config and drops invalid/deprecated keys (with
    warnings). With ``--with-comments``, emits explanatory comments for each
    setting.
    """
    overrides: dict[str, dict] | None = None
    if with_config is not None:
        import tomllib  # noqa: PLC0415

        try:
            with with_config.open("rb") as fh:
                data = tomllib.load(fh)
        except (OSError, tomllib.TOMLDecodeError) as exc:
            typer.echo(f"pyreorder: could not read {with_config}: {exc}", err=True)
            raise typer.Exit(2) from exc
        # If the input is a pyproject.toml, unwrap [tool.pyreorder]
        if with_config.name == "pyproject.toml":
            data = data.get("tool", {}).get("pyreorder", {}) or {}
        overrides, invalid = validate_config_keys(data)
        for path in invalid:
            typer.echo(f"pyreorder: warning: {path} is not a recognized config option; dropping", err=True)
    content = generate_config(overrides=overrides, with_comments=with_comments)
    if output is None:
        typer.echo(content, nl=False)
        return
    if output.suffix != ".toml":
        typer.echo(f"pyreorder: --output must end in .toml (got {output.name})", err=True)
        raise typer.Exit(2)
    if output.exists() and not force:
        typer.echo(f"pyreorder: {output} already exists (use --force to overwrite)", err=True)
        raise typer.Exit(1)
    output.write_text(content, encoding="utf-8")
    typer.echo(f"wrote {output}")


@config_app.command("show")
def config_show(config: ConfigOpt = None) -> None:
    """Print the resolved configuration for the current directory."""
    cfg = load_config(explicit=config, start=Path.cwd())
    typer.echo(f"# source: {cfg.config_path or '<defaults>'}")
    typer.echo(f"sections = {cfg.sections}")
    typer.echo(f"strategies = {cfg.strategies}")
    typer.echo(f"class_methods.enabled = {cfg.class_methods_enabled}")
    typer.echo(f"class_methods.order = {cfg.class_methods_order}")
    typer.echo(f"class_methods.method_type_order = {cfg.class_methods_type_order}")
    typer.echo(f"classification.constants_pattern = {cfg.constants_pattern!r}")
    typer.echo(f"transforms.hoist_inline_imports = {cfg.hoist_inline_imports}")
    typer.echo(f"transforms.hoist_main_imports = {cfg.hoist_main_imports}")
    typer.echo(f"transforms.remove_type_checking = {cfg.remove_type_checking}")
    typer.echo(f"cli.fail_on_changed = {cfg.fail_on_changed}")
    typer.echo(f"discovery.exclude = {cfg.exclude}")
    typer.echo(f"discovery.recursive = {cfg.recursive}")
    typer.echo(f"cli.cache = {cfg.cache_enabled}")
    typer.echo(f"cli.cache_dir = {cfg.cache_dir or '<default: ~/.cache/pyreorder/<slug>>'}")
    typer.echo(f"cli.cache_ttl_days = {cfg.cache_ttl_days}")
    typer.echo(f"cli.jobs = {cfg.jobs}")
    typer.echo(f"cli.parallel_backend = {cfg.parallel_backend!r}")


def main() -> None:
    """Entry point for the ``pyreorder`` console script."""
    app()
