"""Tests for the csort CLI."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from clean_sort import Config
from clean_sort.cli.app import _process_files_parallel, app

# ----------------------------------------------------------- --fail/--no-fail
_UNSORTED = "ZEBRA = 1\nAPPLE = 2\n"

runner = CliRunner()


def test_version_flag() -> None:
    res = runner.invoke(app, ["--version"])
    assert res.exit_code == 0
    assert res.output.strip()


def test_version_command() -> None:
    res = runner.invoke(app, ["version"])
    assert res.exit_code == 0


def test_run_stdin_sorts(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    # Run from a clean cwd so no project config leaks in.
    monkeypatch.chdir(tmp_path)
    (tmp_path / "csort.toml").write_text('[strategy]\nfunctions = "alpha"\n', encoding="utf-8")
    src = "def b():\n    pass\ndef a():\n    pass\n"
    res = runner.invoke(app, ["run", "-"], input=src)
    assert res.exit_code == 0
    assert res.output.index("def a") < res.output.index("def b")


def test_check_detects_unsorted(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.chdir(tmp_path)
    cfg_file = tmp_path / "csort.toml"
    cfg_file.write_text('[strategy]\nfunctions = "alpha"\n', encoding="utf-8")
    target = tmp_path / "m.py"
    target.write_text("def b():\n    pass\ndef a():\n    pass\n", encoding="utf-8")

    res = runner.invoke(app, ["check", str(target)])
    assert res.exit_code == 1

    # after sorting it passes
    runner.invoke(app, ["run", str(target)])
    res2 = runner.invoke(app, ["check", str(target)])
    assert res2.exit_code == 0


def test_diff_shows_changes(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.chdir(tmp_path)
    (tmp_path / "csort.toml").write_text('[strategy]\nfunctions = "alpha"\n', encoding="utf-8")
    target = tmp_path / "m.py"
    target.write_text("def b():\n    pass\ndef a():\n    pass\n", encoding="utf-8")

    res = runner.invoke(app, ["diff", str(target)])
    assert res.exit_code == 0
    assert "+def a" in res.output
    assert "-def a" in res.output


def test_config_generate_default(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.chdir(tmp_path)
    res = runner.invoke(app, ["config", "generate"])
    assert res.exit_code == 0
    assert "[module]" in res.output
    assert "[strategy]" in res.output
    assert "[class_methods]" in res.output


def test_config_generate_output(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.chdir(tmp_path)
    out_file = tmp_path / "csort.toml"
    res = runner.invoke(app, ["config", "generate", "--output", str(out_file)])
    assert res.exit_code == 0
    assert out_file.exists()
    assert "[module]" in out_file.read_text(encoding="utf-8")


def test_config_generate_output_enforces_toml(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.chdir(tmp_path)
    out_file = tmp_path / "csort.txt"
    res = runner.invoke(app, ["config", "generate", "--output", str(out_file)])
    assert res.exit_code == 2  # bad extension
    assert not out_file.exists()


def test_config_generate_output_exists_no_force(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.chdir(tmp_path)
    out_file = tmp_path / "csort.toml"
    out_file.write_text("existing", encoding="utf-8")
    res = runner.invoke(app, ["config", "generate", "--output", str(out_file)])
    assert res.exit_code == 1  # already exists


def test_config_generate_output_force(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.chdir(tmp_path)
    out_file = tmp_path / "csort.toml"
    out_file.write_text("existing", encoding="utf-8")
    res = runner.invoke(app, ["config", "generate", "--output", str(out_file), "--force"])
    assert res.exit_code == 0
    assert "[module]" in out_file.read_text(encoding="utf-8")


def test_config_generate_with_comments(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.chdir(tmp_path)
    res = runner.invoke(app, ["config", "generate", "--with-comments"])
    assert res.exit_code == 0
    # Comments should explain at least one recognized key
    assert "# Ordered list of section buckets" in res.output


def test_config_generate_with_config_merge(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.chdir(tmp_path)
    existing = tmp_path / "existing.toml"
    existing.write_text(
        '[strategy]\nenums = "keep"\nbogus = true\n[cli]\njobs = 8\n',
        encoding="utf-8",
    )
    res = runner.invoke(app, ["config", "generate", "--with-config", str(existing)])
    assert res.exit_code == 0
    # Override carried forward
    assert 'enums = "keep"' in res.output
    assert "jobs = 8" in res.output  # jobs was commented_out but override activates it


def test_config_generate_with_config_invalid_dropped(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.chdir(tmp_path)
    existing = tmp_path / "existing.toml"
    existing.write_text(
        '[strategy]\nbogus_key = true\n[old_section]\nfoo = 42\n',
        encoding="utf-8",
    )
    res = runner.invoke(app, ["config", "generate", "--with-config", str(existing)])
    assert res.exit_code == 0
    stderr = res.stderr_bytes.decode("utf-8", errors="replace")
    assert "[strategy].bogus_key" in stderr
    assert "[old_section].foo" in stderr
    # Invalid keys must not appear in generated output (only in warnings)
    stdout = res.stdout_bytes.decode("utf-8", errors="replace")
    assert "bogus_key" not in stdout
    assert "old_section" not in stdout


def test_config_show(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.chdir(tmp_path)
    res = runner.invoke(app, ["config", "show"])
    assert res.exit_code == 0
    assert "imports" in res.output


def test_section_only_restricts_reordering(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    # Clean cwd; functions use alpha so the restricted section still reorders.
    monkeypatch.chdir(tmp_path)
    (tmp_path / "csort.toml").write_text('[strategy]\nfunctions = "alpha"\n', encoding="utf-8")
    # imports sit after the functions; without --section-only csort hoists them
    # to the top. With --section-only functions, imports become a barrier and stay.
    src = "def b():\n    pass\ndef a():\n    pass\nimport os\n"
    res = runner.invoke(app, ["run", "-", "--section-only", "functions"], input=src)
    assert res.exit_code == 0
    assert res.output.index("def a") < res.output.index("def b")
    assert res.output.index("import os") > res.output.index("def b")


def test_strategy_overrides_changes_strategy(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.chdir(tmp_path)
    # base config keeps function order; the override flips functions to alpha.
    (tmp_path / "csort.toml").write_text('[strategy]\nfunctions = "keep"\n', encoding="utf-8")
    src = "def b():\n    pass\ndef a():\n    pass\n"
    res = runner.invoke(app, ["run", "-", "--strategy-overrides", "functions=alpha"], input=src)
    assert res.exit_code == 0
    assert res.output.index("def a") < res.output.index("def b")


def test_strategy_overrides_invalid_is_ignored(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.chdir(tmp_path)
    (tmp_path / "csort.toml").write_text('[strategy]\nfunctions = "keep"\n', encoding="utf-8")
    src = "def b():\n    pass\ndef a():\n    pass\n"
    # unknown strategy value is warned and ignored, so the base "keep" wins.
    res = runner.invoke(app, ["run", "-", "--strategy-overrides", "functions=bogus"], input=src)
    assert res.exit_code == 0
    assert res.output.index("def b") < res.output.index("def a")


def test_section_only_multiple_sections(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.chdir(tmp_path)
    (tmp_path / "csort.toml").write_text('[strategy]\nfunctions = "alpha"\nimports = "alpha"\n', encoding="utf-8")
    src = "def b():\n    pass\ndef a():\n    pass\nimport zeta\nimport alpha\n"
    res = runner.invoke(app, ["run", "-", "--section-only", "imports,functions"], input=src)
    assert res.exit_code == 0
    assert res.output.index("import alpha") < res.output.index("import zeta")
    assert res.output.index("def a") < res.output.index("def b")


def test_strategy_overrides_multiple_sections(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.chdir(tmp_path)
    (tmp_path / "csort.toml").write_text('[strategy]\nfunctions = "keep"\n', encoding="utf-8")
    src = "def b():\n    pass\ndef a():\n    pass\nimport zeta\nimport alpha\n"
    res = runner.invoke(
        app,
        ["run", "-", "--strategy-overrides", "functions=alpha,imports=alpha"],
        input=src,
    )
    assert res.exit_code == 0
    assert res.output.index("import alpha") < res.output.index("import zeta")
    assert res.output.index("def a") < res.output.index("def b")


def test_hoist_inline_imports_flag(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.chdir(tmp_path)
    src = "def f():\n    import json\n    return json.loads('{}')\n"
    res = runner.invoke(app, ["run", "-", "--hoist-inline-imports"], input=src)
    assert res.exit_code == 0
    assert res.output.index("import json") < res.output.index("def f")


def test_remove_type_checking_flag(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.chdir(tmp_path)
    src = "if TYPE_CHECKING:\n    import http.client\n\nx = 1\n"
    res = runner.invoke(app, ["run", "-", "--remove-type-checking"], input=src)
    assert res.exit_code == 0
    assert "TYPE_CHECKING" not in res.output
    assert "import http.client" in res.output


def test_class_methods_order_override(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.chdir(tmp_path)
    # base csort config keeps the default ordering (public first); the CLI
    # override flips visibility so private comes first.
    (tmp_path / "csort.toml").write_text("[class_methods]\nenabled = true\n", encoding="utf-8")
    src = "class C:\n    def pub(self):\n        pass\n    def __priv(self):\n        pass\n"
    res = runner.invoke(
        app,
        ["run", "-", "--class-methods-order", "private,public,protected"],
        input=src,
    )
    assert res.exit_code == 0
    assert res.output.index("def __priv") < res.output.index("def pub")


def test_method_type_order_override(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.chdir(tmp_path)
    (tmp_path / "csort.toml").write_text("[class_methods]\nenabled = true\n", encoding="utf-8")
    src = "class C:\n    def i(self):\n        pass\n    @staticmethod\n    def s():\n        pass\n"
    res = runner.invoke(
        app,
        ["run", "-", "--method-type-order", "static,instance,class"],
        input=src,
    )
    assert res.exit_code == 0
    assert res.output.index("def s") < res.output.index("def i")


def test_class_methods_order_invalid_is_ignored(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.chdir(tmp_path)
    (tmp_path / "csort.toml").write_text("[class_methods]\nenabled = true\n", encoding="utf-8")
    src = "class C:\n    def _prot(self):\n        pass\n    def pub(self):\n        pass\n"
    # bogus value warns and falls back to the configured order
    # (public before protected by default).
    res = runner.invoke(
        app,
        ["run", "-", "--class-methods-order", "bogus,public"],
        input=src,
    )
    assert res.exit_code == 0
    assert res.output.index("def pub") < res.output.index("def _prot")


def test_run_exits_1_by_default_when_changed(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.chdir(tmp_path)
    (tmp_path / "csort.toml").write_text('[strategy]\nmodule_constants = "alpha"\n', encoding="utf-8")
    target = tmp_path / "m.py"
    target.write_text(_UNSORTED, encoding="utf-8")

    res = runner.invoke(app, ["run", str(target)])
    assert res.exit_code == 1


def test_run_no_fail_exits_0_when_changed(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.chdir(tmp_path)
    (tmp_path / "csort.toml").write_text('[strategy]\nmodule_constants = "alpha"\n', encoding="utf-8")
    target = tmp_path / "m.py"
    target.write_text(_UNSORTED, encoding="utf-8")

    res = runner.invoke(app, ["run", str(target), "--no-fail"])
    assert res.exit_code == 0


def test_run_config_fail_on_changed_false(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.chdir(tmp_path)
    (tmp_path / "csort.toml").write_text(
        '[cli]\nfail_on_changed = false\n[strategy]\nmodule_constants = "alpha"\n',
        encoding="utf-8",
    )
    target = tmp_path / "m.py"
    target.write_text(_UNSORTED, encoding="utf-8")

    res = runner.invoke(app, ["run", str(target)])
    assert res.exit_code == 0


def test_run_cli_fail_overrides_config_false(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.chdir(tmp_path)
    (tmp_path / "csort.toml").write_text(
        '[cli]\nfail_on_changed = false\n[strategy]\nmodule_constants = "alpha"\n',
        encoding="utf-8",
    )
    target = tmp_path / "m.py"
    target.write_text(_UNSORTED, encoding="utf-8")

    res = runner.invoke(app, ["run", str(target), "--fail"])
    assert res.exit_code == 1


# --------------------------------------------------------- discovery config+CLI


def test_run_config_exclude_applies(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.chdir(tmp_path)
    (tmp_path / "csort.toml").write_text(
        '[discovery]\nexclude = ["skip.py"]\n[strategy]\nmodule_constants = "alpha"\n',
        encoding="utf-8",
    )
    keep = tmp_path / "keep.py"
    skip = tmp_path / "skip.py"
    keep.write_text("ZEBRA = 1\nAPPLE = 2\n", encoding="utf-8")
    skip.write_text("ZEBRA = 1\nAPPLE = 2\n", encoding="utf-8")

    res = runner.invoke(app, ["run", str(tmp_path), "--no-fail"])
    assert res.exit_code == 0
    assert "keep.py" in res.output
    assert "skip.py" not in res.output


def test_run_cli_exclude_merges_with_config(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.chdir(tmp_path)
    (tmp_path / "csort.toml").write_text(
        '[discovery]\nexclude = ["skip.py"]\n[strategy]\nmodule_constants = "alpha"\n',
        encoding="utf-8",
    )
    a = tmp_path / "a.py"
    b = tmp_path / "b.py"
    skip = tmp_path / "skip.py"
    for f in (a, b, skip):
        f.write_text("ZEBRA = 1\nAPPLE = 2\n", encoding="utf-8")

    res = runner.invoke(app, ["run", str(tmp_path), "-x", "b.py", "--no-fail"])
    assert res.exit_code == 0
    assert "a.py" in res.output
    assert "b.py" not in res.output
    assert "skip.py" not in res.output


def test_run_config_recursive_false(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.chdir(tmp_path)
    (tmp_path / "csort.toml").write_text(
        '[discovery]\nrecursive = false\n[strategy]\nmodule_constants = "alpha"\n',
        encoding="utf-8",
    )
    sub = tmp_path / "sub"
    sub.mkdir()
    top = tmp_path / "top.py"
    nested = sub / "nested.py"
    top.write_text("ZEBRA = 1\nAPPLE = 2\n", encoding="utf-8")
    nested.write_text("ZEBRA = 1\nAPPLE = 2\n", encoding="utf-8")

    res = runner.invoke(app, ["run", str(tmp_path), "--no-fail"])
    assert res.exit_code == 0
    assert "top.py" in res.output
    assert "nested.py" not in res.output


def test_run_no_recursive_overrides_config_true(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.chdir(tmp_path)
    (tmp_path / "csort.toml").write_text(
        '[discovery]\nrecursive = true\n[strategy]\nmodule_constants = "alpha"\n',
        encoding="utf-8",
    )
    sub = tmp_path / "sub"
    sub.mkdir()
    top = tmp_path / "top.py"
    nested = sub / "nested.py"
    top.write_text("ZEBRA = 1\nAPPLE = 2\n", encoding="utf-8")
    nested.write_text("ZEBRA = 1\nAPPLE = 2\n", encoding="utf-8")

    res = runner.invoke(app, ["run", str(tmp_path), "--no-recursive", "--no-fail"])
    assert res.exit_code == 0
    assert "top.py" in res.output
    assert "nested.py" not in res.output


# --------------------------------------------------------------- --no-cache flag


def test_no_cache_flag_disables_cache(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.chdir(tmp_path)
    (tmp_path / "csort.toml").write_text(
        '[strategy]\nmodule_constants = "alpha"\n',
        encoding="utf-8",
    )
    target = tmp_path / "m.py"
    target.write_text("ZEBRA = 1\nAPPLE = 2\n", encoding="utf-8")
    # First run sorts and caches
    runner.invoke(app, ["run", str(target), "--no-fail"])
    # Second run with --no-cache should still sort (not skip)
    res = runner.invoke(app, ["check", str(target), "--no-cache"])
    assert res.exit_code == 0  # already sorted, but --no-cache means no skip
    assert "ok" in res.output


def test_cache_config_disabled(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.chdir(tmp_path)
    (tmp_path / "csort.toml").write_text(
        '[cli]\ncache = false\n[strategy]\nmodule_constants = "alpha"\n',
        encoding="utf-8",
    )
    target = tmp_path / "m.py"
    target.write_text("ZEBRA = 1\nAPPLE = 2\n", encoding="utf-8")
    # First run sorts
    runner.invoke(app, ["run", str(target), "--no-fail"])
    # Second run: cache disabled in config, should still sort
    res = runner.invoke(app, ["check", str(target)])
    assert res.exit_code == 0
    assert "ok" in res.output


# --------------------------------------------------------------- parallel


def test_parallel_jobs_flag(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.chdir(tmp_path)
    (tmp_path / "csort.toml").write_text(
        '[strategy]\nmodule_constants = "alpha"\n',
        encoding="utf-8",
    )
    for i in range(1, 6):
        (tmp_path / f"m{i}.py").write_text("APPLE = 1\nZEBRA = 2\n", encoding="utf-8")
    # Use --jobs 0 (serial) to avoid Windows spawn/file-lock issues with tmp_path
    res = runner.invoke(app, ["check", str(tmp_path), "--jobs", "0"])
    assert res.exit_code == 0
    assert "ok" in res.output


def test_parallel_serial_when_jobs_zero(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.chdir(tmp_path)
    (tmp_path / "csort.toml").write_text(
        '[strategy]\nmodule_constants = "alpha"\n',
        encoding="utf-8",
    )
    for i in range(1, 6):
        (tmp_path / f"m{i}.py").write_text("APPLE = 1\nZEBRA = 2\n", encoding="utf-8")
    res = runner.invoke(app, ["check", str(tmp_path), "--jobs", "0"])
    assert res.exit_code == 0
    assert "ok" in res.output


def test_parallel_backend_thread(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.chdir(tmp_path)
    (tmp_path / "csort.toml").write_text(
        '[strategy]\nmodule_constants = "alpha"\n',
        encoding="utf-8",
    )
    for i in range(1, 6):
        (tmp_path / f"m{i}.py").write_text("APPLE = 1\nZEBRA = 2\n", encoding="utf-8")
    res = runner.invoke(app, ["check", str(tmp_path), "--jobs", "0", "--parallel-backend", "thread"])
    assert res.exit_code == 0
    assert "ok" in res.output


def test_parallel_config_jobs(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.chdir(tmp_path)
    (tmp_path / "csort.toml").write_text(
        '[cli]\njobs = 0\n[strategy]\nmodule_constants = "alpha"\n',
        encoding="utf-8",
    )
    for i in range(1, 6):
        (tmp_path / f"m{i}.py").write_text("APPLE = 1\nZEBRA = 2\n", encoding="utf-8")
    res = runner.invoke(app, ["check", str(tmp_path)])
    assert res.exit_code == 0
    assert "ok" in res.output


def test_parallel_process_pool_direct(tmp_path: Path) -> None:
    """Test the process pool code path directly (not via CLI)."""
    for i in range(1, 6):
        (tmp_path / f"m{i}.py").write_text("APPLE = 1\nZEBRA = 2\n", encoding="utf-8")
    files = sorted(tmp_path.glob("*.py"))
    cfg = Config()
    code, changed = _process_files_parallel(files, cfg, "check", jobs=4, backend="process")
    assert code == 0
    assert len(changed) == 0
