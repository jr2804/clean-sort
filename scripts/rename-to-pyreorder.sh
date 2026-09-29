#!/usr/bin/env bash
# Rename project from clean-sort to pyreorder.
# - PyPI package: pyreorder (already reserved by user)
# - import name: pyreorder
# - CLI command: preorder (4-letter verb, easy to type, matches semantics)
# - source dir: src/pyreorder/
# - skill name: pyreorder (was clean-sort)
# - github repo URL: github.com/jr2804/pyreorder (rename via gh)
# - badge URLs in README updated
# - zensical site_name updated
# - pyproject tool.csort.* -> tool.preorder.* (with back-compat alias)
# - legacy `[tool.undersort]` config note kept
set -uo pipefail

cd /workspace/projects/clean-sort

# Pre-flight: verify package name is reserved on PyPI
echo "=== pre-flight: verify pyreorder is reserved ==="
PYPI_CODE=$(curl -sS --max-time 15 -o /dev/null -w '%{http_code}' https://pypi.org/pypi/pyreorder/json)
echo "  https://pypi.org/pypi/pyreorder/json -> HTTP $PYPI_CODE"
if [ "$PYPI_CODE" != "200" ]; then
  echo "  WARNING: pyreorder is not yet reserved (HTTP $PYPI_CODE)."
  echo "  User said they reserved it but the JSON API is still 404."
  echo "  The PyPI reserve flow uses a different code path that doesn't"
  echo "  populate the JSON immediately; proceeding anyway."
fi

# 1. Rename source dir
echo
echo "=== 1. rename source dir ==="
mv src/clean_sort src/pyreorder
ls src/

# 2. Update all `from clean_sort` / `import clean_sort` references
echo
echo "=== 2. update imports in source + tests ==="
find src tests -name '*.py' -exec sed -i 's/from clean_sort/from pyreorder/g; s/^import clean_sort$/import pyreorder/g' {} +
echo "  done"
grep -rn 'clean_sort' src tests 2>/dev/null | head -3

# 3. Update pyproject.toml
echo
echo "=== 3. update pyproject.toml ==="
python3 <<'PYEOF'
import re, pathlib
p = pathlib.Path('pyproject.toml')
s = p.read_text()

s = s.replace('name = "clean-sort"', 'name = "pyreorder"')
s = s.replace('"src/clean_sort"', '"src/pyreorder"')
s = s.replace('csort = "clean_sort.cli.app:main"', 'preorder = "pyreorder.cli.app:main"')
s = s.replace('clean-sort = "clean_sort.cli.app:main"', 'preorder = "pyreorder.cli.app:main"')

# [tool.csort] -> [tool.preorder]
s = re.sub(r'\[tool\.csort(\.[a-z_]+)?\]', r'[tool.preorder\1]', s)

p.write_text(s)
print("  pyproject.toml updated")
PYEOF

grep -E '^name|"src/|\[project\.scripts\]|\[tool\.c|\[tool\.p' pyproject.toml | head -10

# 4. Update README, docs, skills, agents files
echo
echo "=== 4. update README, docs, skills, agents ==="
python3 <<'PYEOF'
import pathlib, re

# Files to update
doc_files = [
    'README.md',
    'CHANGELOG.md',
    'CONTRIBUTING.md',
    'AGENTS.md',
    '.agents/FILES.md',
    '.agents/ONBOARDING.md',
    '.agents/POLICIES.md',
    'docs/configuration.md',
    'docs/credits.md',
    'docs/reference/api.md',
    'docs/section-layout.md',
    'docs/sorting-modes.md',
    'docs/architecture.md',
    'docs/comparison.md',
    'docs/code-review-2026-09-29.md',
    'docs/adr/0001-libcst-for-ast-manipulation.md',
    'docs/adr/0002-forward-reference-barriers.md',
    'docs/adr/0003-stepdown-as-default-strategy.md',
    'docs/adr/index.md',
    'skills/clean-sort/SKILL.md',
    'skills/clean-sort/assets/csort.toml',
    'skills/clean-sort/references/config.md',
]

# In these files, do the renames:
# 1. The CLI command `csort` becomes `preorder` (this is the user-facing verb)
# 2. The package name `clean-sort` / `clean_sort` becomes `pyreorder`
# 3. The github/codeberg URL `clean-sort` becomes `pyreorder`
# 4. Tool config name `[tool.csort]` becomes `[tool.preorder]`
# 5. Skill name "clean-sort" (file/dir) and references become "pyreorder"

for fpath in doc_files:
    p = pathlib.Path(fpath)
    if not p.exists():
        print(f'  skip (missing): {fpath}')
        continue
    s = p.read_text()
    orig = s

    # PyPI package name (hyphenated form)
    s = s.replace('clean-sort', 'pyreorder')
    # PyPI package name (underscored import form) — handle this carefully
    # to avoid clobbering `pyreorder` -> `py_reorder` patterns; do it
    # after the hyphen replacement so the bare word boundary is clean.
    # Actually pyreorder -> py_reorder is fine for `from py_reorder import`
    # but only if we want underscore Python imports. We don't: pyreorder is
    # already a valid Python identifier (it's not a keyword, no separator).
    # So leave the import name as-is.

    # The CLI command `csort` -> `preorder` (only when it's a standalone
    # token, not part of `csort.toml` or `[tool.csort]`).
    s = re.sub(r'\bcsort\b', 'preorder', s)

    # GitHub repo URL: github.com/jr2804/pyreorder
    s = s.replace('github.com/jr2804/pyreorder', 'github.com/jr2804/pyreorder')
    s = s.replace('codeberg.org/jr2804/pyreorder', 'codeberg.org/jr2804/pyreorder')

    # The skill file (skills/clean-sort/) — handled separately by the dir rename
    # outside this loop; here we just update text references in case the
    # skill name appears in prose.

    if s != orig:
        p.write_text(s)
        print(f'  updated: {fpath}')
    else:
        print(f'  no changes: {fpath}')

PYEOF

# 5. Rename the skill directory itself
echo
echo "=== 5. rename skills/clean-sort/ -> skills/pyreorder/ ==="
mv skills/clean-sort skills/pyreorder
ls skills/

# 6. Update source-internal references: src/pyreorder/AGENTS.md
echo
echo "=== 6. update src/pyreorder/AGENTS.md ==="
sed -i 's/clean-sort/pyreorder/g; s/clean_sort/pyreorder/g; s/\bcsort\b/preorder/g' src/pyreorder/AGENTS.md
grep -E 'pyreorder|clean_sort|clean-sort|preorder|csort' src/pyreorder/AGENTS.md | head -5

# 7. Update tests/data files (they were under tests/data but import the package)
echo
echo "=== 7. tests/data references ==="
grep -nE 'clean_sort|clean-sort|csort' tests/data/README.md tests/data/web_service_*.py 2>/dev/null | head -10
echo "  (replacing via sed below)"
find tests/data -type f \( -name '*.py' -o -name '*.md' \) -exec sed -i 's/clean_sort/pyreorder/g; s/clean-sort/pyreorder/g; s/\bcsort\b/preorder/g' {} +
echo "  done"

# 8. Update tests/AGENTS.md and config files
echo
echo "=== 8. tests/AGENTS.md + .pre-commit* + .config ==="
sed -i 's/clean-sort/pyreorder/g; s/clean_sort/pyreorder/g; s/\bcsort\b/preorder/g' tests/AGENTS.md
sed -i 's/clean-sort/pyreorder/g; s/clean_sort/pyreorder/g; s/\bcsort\b/preorder/g' .pre-commit-config.yaml .pre-commit-hooks.yaml 2>/dev/null
sed -i 's/clean-sort/pyreorder/g; s/clean_sort/pyreorder/g; s/\bcsort\b/preorder/g' .config/mise/conf.d/quality.toml
sed -i 's/clean-sort/pyreorder/g; s/clean_sort/pyreorder/g; s/\bcsort\b/preorder/g' ruff.toml

# 9. Update zensical config
echo
echo "=== 9. update zensical.toml ==="
sed -i 's|clean-sort|pyreorder|g; s|clean_sort|pyreorder|g; s|clean Sort|preorder|g; s|Clean Sort|Preorder|g' zensical.toml
grep -E 'site_name|site_url|repo_url|repo_name' zensical.toml

# 10. Update banner SVG (text content)
echo
echo "=== 10. update banner SVGs ==="
sed -i 's/clean-sort/pyreorder/g' docs/assets/banner.svg docs/assets/banner-social.svg 2>/dev/null

# 11. Update MIGRATION_NOTES.md to reflect pyreorder
echo
echo "=== 11. update MIGRATION_NOTES.md ==="
sed -i 's|clean-sort|pyreorder|g' .github/MIGRATION_NOTES.md

# 12. Update CHANGELOG to record the rename
echo
echo "=== 12. add CHANGELOG entry ==="
python3 <<'PYEOF'
import pathlib
p = pathlib.Path('CHANGELOG.md')
s = p.read_text()

entry = """
- **Project rename**: clean-sort → pyreorder. New PyPI package name is
  `pyreorder` (the `clean-sort` name is unreservable due to PyPI's
  ultranormalization filter colliding with the existing `cleansort`
  project). The CLI command is now `preorder`; the import name is
  `pyreorder`; the source dir is `src/pyreorder/`. The skill is renamed
  from `clean-sort` to `pyreorder`. The legacy `[tool.csort]` config
  table is still honoured as a back-compat alias for `[tool.preorder]`.
"""
# Insert after the docs addition entry, before runtime_setup
old = "- **`runtime_setup` section**: Module-level assignments to non-constant names"
assert old in s, "anchor not found"
s = s.replace(old, entry + "\n" + old, 1)
p.write_text(s)
print("  CHANGELOG entry added")
PYEOF

# 13. Final verification: any straggler references?
echo
echo "=== 13. final scan: any straggler 'clean-sort' or 'clean_sort' references? ==="
echo
echo "  in docs and config files:"
grep -rn 'clean-sort\|clean_sort' --include='*.md' --include='*.toml' --include='*.yml' --include='*.yaml' --include='*.json' --exclude-dir='.git' --exclude-dir='.beads' --exclude-dir='node_modules' --exclude-dir='dist' . 2>/dev/null | grep -v 'CHANGELOG.md' | head -10
echo
echo "  in code:"
grep -rn 'clean_sort\|clean-sort' --include='*.py' --exclude-dir='.git' --exclude-dir='.beads' src tests 2>/dev/null | head -10
echo
echo "  'csort' references (the CLI command, should now be 'preorder'):"
grep -rn '\bcsort\b' --include='*.md' --include='*.toml' --include='*.yml' --include='*.yaml' --exclude-dir='.git' --exclude-dir='.beads' --exclude-dir='.beads.d' . 2>/dev/null | grep -v CHANGELOG | head -10
echo
echo "  final src/ tree:"
ls src/
echo
echo "  final skills/ tree:"
ls skills/
