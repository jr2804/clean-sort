"""Tests for the csort CLI."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from clean_sort.cli.app import app

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


def test_config_init(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.chdir(tmp_path)
    res = runner.invoke(app, ["config", "init"])
    assert res.exit_code == 0
    assert (tmp_path / "csort.toml").exists()

    res2 = runner.invoke(app, ["config", "init"])
    assert res2.exit_code == 1  # already exists


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
