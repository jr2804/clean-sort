"""Regression guards for the documentation build inputs.

Both cases fail silently: no test, lint, or type error, just a visibly broken
site. Kept small and targeted rather than mirroring ``src/pyreorder``.
"""

from __future__ import annotations

import runpy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def test_zensical_declares_the_mermaid_fence() -> None:
    """Declaring any ``custom_fences`` replaces Zensical's default list.

    The default list ships the ``mermaid`` fence, so dropping it turns every
    diagram in the docs into a raw code block.
    """
    config = (ROOT / "zensical.toml").read_text(encoding="utf-8")
    assert 'name = "mermaid"' in config
    assert 'class = "mermaid"' in config


def test_gen_credits_prints_when_not_run_as_main(capsys: pytest.CaptureFixture[str]) -> None:
    """``markdown-exec`` sets a synthetic ``__name__`` and renders only printed output.

    The script is pulled into ``docs/credits.md`` through a ``python exec="yes"``
    fence; a ``__main__``-guarded print produces nothing there.
    """
    runpy.run_path(str(ROOT / "scripts" / "gen_credits.py"), run_name="docs_code_block")
    out = capsys.readouterr().out
    assert out.strip(), "gen_credits.py printed nothing; the credits page would render empty"
    assert "https://pypi.org/project/" in out
    assert not out.startswith("# "), "the generated text must not add its own top-level heading"
