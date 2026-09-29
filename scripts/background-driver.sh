#!/usr/bin/env bash
# Background implementation driver for clean-sort migration.
# Each task is independent; failures in one don't block the others.
# All work lands on disk; no pushes, no PyPI publishes, no public side effects.
set -uo pipefail

cd /workspace/projects/clean-sort

LOG=/tmp/cleansort-impl.log
: > "$LOG"
exec > >(tee -a "$LOG") 2>&1
echo "=== clean-sort implementation driver ==="
echo "=== started: $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
echo

# ----------------------------------------------------------------------------
# Task D: Dev features (Gate 5) — add curated tools to mise config
# ----------------------------------------------------------------------------
echo "=== Task D: Gate 5 dev features (curated) ==="
D_BEFORE=$(md5sum .config/mise/config.toml | awk '{print $1}')
echo "  config.toml md5 BEFORE: $D_BEFORE"

python3 <<'PYEOF'
import pathlib
p = pathlib.Path('.config/mise/config.toml')
src = p.read_text()

new_block = '''
# Codebase search trio (Jev Gate 5 — curated)
"github:yoanbernabeu/grepai"  = "latest"
"npm:@colbymchenry/codegraph" = "latest"
"pypi:repowise"               = "latest"

# LLM-slop detectors (aligned with migration reason)
"github:ChuprinaDaria/Vibecode-Cleaner-Fartrun" = "latest"
"pypi:ai-slop-detector" = { version = "latest", extras = ["all"] }
'''

anchor = '"codespell" = "latest"\n'
assert anchor in src, "anchor line not found"
src = src.replace(anchor, anchor + new_block)
p.write_text(src)
print("  config.toml updated with curated toolset")
PYEOF

D_AFTER=$(md5sum .config/mise/config.toml | awk '{print $1}')
echo "  config.toml md5 AFTER:  $D_AFTER"
python3 -c "import tomllib; tomllib.load(open('.config/mise/config.toml','rb')); print('  config.toml: TOML parse OK')"
echo

# ----------------------------------------------------------------------------
# Task F: Code review (Gate 7) — scaffold report
# ----------------------------------------------------------------------------
echo "=== Task F: Gate 7 code review scaffold ==="
mkdir -p docs/adr
F_REPORT=docs/code-review-2026-09-29.md

cat > "$F_REPORT" <<'EOF_REVIEW'
---
title: Code review — 2026-09-29
hide:
- feedback
- toc
---

# Code review — 2026-09-29

Automated review of the current `clean-sort` working tree at commit
`72c33b3` (the docs-additions commit on `main`). This report captures
the state of the code at that commit, not a proposed change set.

## Tool availability

| Tool | Status | Notes |
|---|---|---|
| `ruff` | (run `mise run lint` to populate) | Linter / formatter |
| `ty` | (run `mise run lint` to populate) | Type checker |
| `pytest` | (run `mise run test` to populate) | Test runner |
| `codespell` | (run `mise run spell` to populate) | Spell checker |

## Findings (placeholder)

Run the following locally to populate:

```bash
mise install
mise run lint   # ruff + ty + rumdl + codespell
mise run test   # pytest --cov
```

The results will be appended below.

## Static observations (read of the code, no execution)

- `src/clean_sort/pipeline.py` orchestrates the parse → classify → reorder →
  in-section-sort → render pipeline. Single entry point `sort_source`.
- `src/clean_sort/classify.py` owns section assignment and forward-reference
  barrier detection. The barrier rule is the load-bearing safety invariant
  (see ADR 0002).
- `src/clean_sort/sorters.py` exposes `alpha` and `dependency` (stepdown /
  abstraction). The dependency sort uses a topological pass on name
  references.
- `src/clean_sort/cache.py` owns the content-hash skip cache (see the
  Architecture page).
- `src/clean_sort/transforms.py` is the only stage that mutates code beyond
  reordering (`hoist_inline_imports`, `remove_type_checking`). Both default
  off.
- `src/clean_sort/config.py` is the single source of truth for recognized
  config keys; the `csort config generate` subcommand reads it.
- `src/clean_sort/undersort.py` (`MethodSorter`) provides in-class method
  ordering; the legacy `[tool.undersort]` table is honoured as a fallback.
EOF_REVIEW

echo "  scaffold written: $F_REPORT ($(wc -l <"$F_REPORT") lines)"
echo

# ----------------------------------------------------------------------------
# Task B: GitHub Actions workflows
# ----------------------------------------------------------------------------
echo "=== Task B: GitHub Actions workflow files ==="

mkdir -p .github/workflows

cat > .github/workflows/ci.yml <<'EOF_CI'
name: ci

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}

defaults:
  run:
    shell: bash

env:
  LANG: en_US.utf-8
  LC_ALL: en_US.utf-8
  PYTHONIOENCODING: UTF-8

jobs:

  quality:
    runs-on: ubuntu-latest
    steps:
    - name: Checkout
      uses: actions/checkout@v4
      with:
        fetch-depth: 0
        fetch-tags: true
    - name: Setup Python
      uses: actions/setup-python@v5
      with:
        python-version: "3.11"
    - name: Setup uv
      uses: astral-sh/setup-uv@v4
      with:
        enable-cache: true
        cache-dependency-glob: pyproject.toml
    - name: Setup mise
      uses: jdx/mise-action@v2
      with:
        install: true
    - name: Install dependencies
      run: mise dev || uv sync --dev
    - name: Run linter
      run: mise lint || ruff check src/ tests/
    - name: Check spelling
      run: mise spell || codespell src/ tests/

  tests:
    needs: [quality]
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        python-version: ["3.11", "3.12", "3.13"]
      fail-fast: false
    runs-on: ${{ matrix.os }}
    steps:
    - name: Checkout
      uses: actions/checkout@v4
      with:
        fetch-depth: 0
        fetch-tags: true
    - name: Setup Python
      uses: actions/setup-python@v5
      with:
        python-version: ${{ matrix.python-version }}
    - name: Setup uv
      uses: astral-sh/setup-uv@v4
      with:
        enable-cache: true
        cache-dependency-glob: pyproject.toml
    - name: Setup mise
      uses: jdx/mise-action@v2
      with:
        install: true
    - name: Install dependencies
      run: mise dev || uv sync --dev
    - name: Run tests with coverage
      run: mise test || pytest --cov=clean_sort --cov-report=term-missing --cov-report=xml
    - name: Upload coverage artifact
      if: matrix.os == 'ubuntu-latest' && matrix.python-version == '3.12'
      uses: actions/upload-artifact@v4
      with:
        name: coverage-xml
        path: coverage.xml

  docs:
    needs: [quality]
    runs-on: ubuntu-latest
    steps:
    - name: Checkout
      uses: actions/checkout@v4
      with:
        fetch-depth: 0
    - name: Setup Python
      uses: actions/setup-python@v5
      with:
        python-version: "3.11"
    - name: Setup uv
      uses: astral-sh/setup-uv@v4
      with:
        enable-cache: true
        cache-dependency-glob: pyproject.toml
    - name: Install dependencies
      run: mise dev || uv sync --dev
    - name: Build documentation
      run: mise docs || zensical build --clean
    - name: Upload docs artifact
      uses: actions/upload-artifact@v4
      with:
        name: docs-site
        path: site/
EOF_CI

cat > .github/workflows/release.yml <<'EOF_RELEASE'
# Release workflow (calendar versioning).
# Push to main -> compute next YYYY.M.N tag -> tag -> build -> publish PyPI
# (trusted publishing, OIDC) -> create GitHub Release with wheel+sdist.
#
# PyPI trusted-publisher setup (one-time, manual):
#   https://pypi.org/manage/project/clean-sort/publishing/
#   Owner: jr2804  Repository: jr2804/clean-sort
#   Workflow filename: release.yml  Workflow name: release
name: release

on:
  push:
    branches: [main]
  workflow_dispatch:

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: false

defaults:
  run:
    shell: bash

jobs:

  release:
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    permissions:
      contents: write
      id-token: write   # required for PyPI trusted publishing (OIDC)

    steps:
    - name: Checkout
      uses: actions/checkout@v4
      with:
        fetch-depth: 0
        fetch-tags: true
    - name: Setup Python
      uses: actions/setup-python@v5
      with:
        python-version: "3.11"
    - name: Setup uv
      uses: astral-sh/setup-uv@v4
      with:
        enable-cache: true
        cache-dependency-glob: pyproject.toml

    - name: Compute next calendar version
      id: version
      run: |
        set -euo pipefail
        existing_head_tag="$(git tag --points-at HEAD | grep -E '^[0-9]{4}\.[0-9]{2}\.[0-9]+$' | head -n 1 || true)"
        if [ -n "$existing_head_tag" ]; then
          echo "version=$existing_head_tag" >> "$GITHUB_OUTPUT"
          echo "needs_tag=false" >> "$GITHUB_OUTPUT"
          exit 0
        fi
        year="$(date -u +%Y)"
        month="$(date -u +%m)"
        git fetch --tags --force
        prefix="${year}.${month}."
        highest="$(git tag --list "${prefix}*" | sed -n "s/^${year}\\.${month}\\.\\([0-9][0-9]*\\)$/\\1/p" | sort -n | tail -n 1)"
        counter="${highest:-0}"
        next="$((counter + 1))"
        version="${year}.${month}.${next}"
        while git rev-parse -q --verify "refs/tags/${version}" >/dev/null; do
          next="$((next + 1))"
          version="${year}.${month}.${next}"
        done
        echo "version=$version" >> "$GITHUB_OUTPUT"
        echo "needs_tag=true" >> "$GITHUB_OUTPUT"

    - name: Create and push tag
      if: steps.version.outputs.needs_tag == 'true'
      run: |
        set -euo pipefail
        version="${{ steps.version.outputs.version }}"
        git tag -a "$version" -m "Release $version"
        git push origin "$version"

    - name: Build package
      run: uv build

    - name: Publish to PyPI (trusted publishing, OIDC)
      uses: pypa/gh-action-pypi-publish@release/v1
      with:
        packages-dir: dist/

    - name: Create GitHub Release
      uses: softprops/action-gh-release@v2
      with:
        tag_name: ${{ steps.version.outputs.version }}
        name: ${{ steps.version.outputs.version }}
        files: dist/*
        generate_release_notes: true
EOF_RELEASE

# Sanity-check the YAML
python3 <<'PYEOF'
import sys
try:
    import yaml
    for f in ['.github/workflows/ci.yml', '.github/workflows/release.yml']:
        try:
            data = yaml.safe_load(open(f))
            name = data.get('name', '<no-name>') if isinstance(data, dict) else '<not-dict>'
            print(f"  {f}: YAML parse OK, name={name!r}")
        except Exception as e:
            print(f"  {f}: YAML parse FAILED: {e}")
            sys.exit(1)
except ImportError:
    for f in ['.github/workflows/ci.yml', '.github/workflows/release.yml']:
        src = open(f).read()
        ok = any(line.startswith('name:') for line in src.splitlines()[:10])
        print(f"  {f}: {'OK' if ok else 'MISSING name:'} (yaml lib not available)")
PYEOF
echo

# ----------------------------------------------------------------------------
# Task G: Beads issues for clean-sort
# ----------------------------------------------------------------------------
echo "=== Task G: Beads issues for clean-sort tracking ==="
export HOME=/opt/data
source /opt/data/home/.mise-env.sh 2>/dev/null

if [ ! -d .beads ]; then
  echo "  bootstrapping .beads (prefix csrt)..."
  bd init --quiet --skip-agents --prefix csrt --non-interactive --force 2>&1 | tail -3 || true
  git config beads.role maintainer 2>/dev/null || true
fi

ISSUES=(
  "Gate 1: Confirm clean-sort name on PyPI (already auto-followed; verify after first publish)"
  "Gate 2: Set up github.com/jr2804/clean-sort as canonical; configure Codeberg as pull mirror"
  "Gate 3: Configure PyPI trusted publishing (one-time setup at pypi.org/manage/project/clean-sort/publishing/)"
  "Gate 5: Verify dev-features install via mise install"
  "Gate 6: Add banner/logo (teal+purple, adapted from copier-uv-plus hero)"
  "Gate 7: Populate code-review-2026-09-29.md with lint + test output"
)

for title in "${ISSUES[@]}"; do
  result=$(bd create --title "$title" --priority P2 --type task 2>&1 | tail -1)
  echo "  filed: $result"
done

echo
echo "=== driver complete ==="
echo "=== finished: $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
echo
echo "=== Summary of disk changes (uncommitted) ==="
git status --short
echo
echo "=== Next actions needing your input ==="
echo "  1. Push main to github.com/jr2804/clean-sort (or say 'create and push')"
echo "  2. One-time PyPI trusted-publisher setup:"
echo "       https://pypi.org/manage/project/clean-sort/publishing/"
echo "       Owner: jr2804  Repo: jr2804/clean-sort  Workflow: release.yml"
echo "  3. Confirm banner palette (default teal+purple) or override"
echo "  4. Run 'mise install && mise run lint && mise run test' to populate code-review report"
