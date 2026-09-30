"""Regression guards for the documentation build inputs.

Both cases fail silently: no test, lint, or type error, just a visibly broken
site. Kept small and targeted rather than mirroring ``src/pyreorder``.
"""

from __future__ import annotations

import re
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
    assert "libcst" in out, "runtime dependencies must be listed, not just the docs toolchain"


def test_readme_local_images_exist_and_are_labelled() -> None:
    """GitHub renders the README as written, so a bad path or unlabelled SVG degrades it silently."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    srcs = re.findall(r'<img[^>]+src="([^"]+)"', readme)
    srcs += re.findall(r"!\[[^\]]*\]\(([^)]+)\)", readme)
    local = [s for s in srcs if not s.startswith(("http://", "https://"))]
    assert local, "expected at least one local README image (the banner)"
    for src in local:
        path = ROOT / src
        assert path.exists(), f"README references a missing image: {src}"
        if path.suffix == ".svg":
            assert "<title>" in path.read_text(encoding="utf-8"), f"{src} has no <title>"
