#!/usr/bin/env bash
# Background driver: Gates 2 + 6 + 7
set -uo pipefail

cd /workspace/projects/clean-sort
export HOME=/opt/data
source /opt/data/home/.mise-env.sh
hash -r

LOG=/tmp/cleansort-gates267.log
: > "$LOG"
exec > >(tee -a "$LOG") 2>&1
echo "=== clean-sort Gates 2/6/7 driver ==="
echo "=== started: $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
echo

# ----------------------------------------------------------------------------
# Gate 2: GitHub canonical repo
# ----------------------------------------------------------------------------
echo "=== Gate 2: GitHub canonical repo ==="

if gh repo view jr2804/clean-sort --json name >/dev/null 2>&1; then
  echo "  github.com/jr2804/clean-sort already exists; skipping create"
else
  echo "  creating github.com/jr2804/clean-sort (public, no auto-push)..."
  gh repo create jr2804/clean-sort \
    --public \
    --description "AST-based structural sorter for Python source code" \
    --homepage "https://github.com/jr2804/clean-sort" \
    --source=. \
    --remote=origin \
    --push=false 2>&1 | tail -10
fi

echo
echo "=== verify remote + visibility ==="
gh repo view jr2804/clean-sort --json name,visibility,url --jq '. | "\(.name) [\(.visibility)] -> \(.url)"' 2>&1 | head -3

echo
echo "=== push main + tags + notes to github ==="
git push -u origin main 2>&1 | tail -10
git push origin --tags 2>&1 | tail -5
git push origin 'refs/notes/*:refs/notes/*' 2>&1 | tail -5

echo
echo "=== confirm github sees our commits ==="
gh api repos/jr2804/clean-sort/commits --jq '.[0:5] | .[] | "\(.sha[0:7]) \(.commit.message | split("\n")[0])"' 2>&1 | head -5

echo
echo "=== set default branch ==="
gh repo edit jr2804/clean-sort --default-branch main 2>&1 | tail -3

echo
echo "=== branch protection on main (best-effort; needs repo-admin scope) ==="
gh api -X PUT repos/jr2804/clean-sort/branches/main/protection \
  -H "Accept: application/vnd.github+json" \
  --input - <<'PROT' 2>&1 | tail -5 || true
{
  "required_status_checks": null,
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "dismissal_restrictions": {},
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": false,
    "required_approving_review_count": 1,
    "require_last_push_approval": true
  },
  "restrictions": null,
  "required_linear_history": true,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "block_creations": false,
  "required_conversation_resolution": true,
  "lock_branch": false,
  "allow_fork_syncing": false
}
PROT

echo
echo "=== Codeberg: register github as pull-mirror source ==="
if [ -z "${FORGEJO_TOKEN:-}" ] && [ -z "${CODEBERG_TOKEN:-}" ]; then
  if [ -f /opt/data/secrets/forge.env ]; then
    echo "  sourcing /opt/data/secrets/forge.env for FORGEJO_TOKEN"
    set +u
    . /opt/data/secrets/forge.env
    set -u
  fi
fi

if [ -n "${FORGEJO_TOKEN:-}" ] || [ -n "${CODEBERG_TOKEN:-}" ]; then
  TOK="${FORGEJO_TOKEN:-${CODEBERG_TOKEN}}"
  echo "  registering pull-mirror on codeberg.org/jr2804/clean-sort..."
  curl -sS -X POST "https://codeberg.org/api/v1/repos/jr2804/clean-sort/mirror-sync" \
    -H "Authorization: token $TOK" \
    -H "Content-Type: application/json" \
    -d "{
      \"remote_address\": \"https://github.com/jr2804/clean-sort.git\",
      \"remote_username\": \"\",
      \"remote_password\": \"\",
      \"mirror_interval\": \"8h\",
      \"mirror_direction\": \"pull\"
    }" | head -5
else
  echo "  no FORGEJO_TOKEN/CODEBERG_TOKEN in env; logged command instead:"
  echo '    curl -X POST https://codeberg.org/api/v1/repos/jr2804/clean-sort/mirror-sync'
  echo '         -H "Authorization: token $FORGEJO_TOKEN"'
  echo '         -H "Content-Type: application/json"'
  echo '         -d "{\"remote_address\": \"https://github.com/jr2804/clean-sort.git\", \"mirror_interval\": \"8h\", \"mirror_direction\": \"pull\"}"'
fi

echo
cat > .github/MIGRATION_NOTES.md <<'NOTES'
# Codeberg canonical-home banner

The Codeberg README should carry a banner pointing at the GitHub canonical
home. Drop this block at the top of `codeberg.org/jr2804/clean-sort/README.md`:

```markdown
> **This repository has moved.**
> The canonical home is now **github.com/jr2804/clean-sort**.
> This Codeberg mirror is kept read-only and synced from GitHub every 8 hours.
> Please file issues and open PRs on GitHub.
```

The Codeberg side will receive this banner on the next mirror sync if it's
committed to GitHub first and the mirror pulls.
NOTES
echo "  MIGRATION_NOTES.md written"

# ----------------------------------------------------------------------------
# Gate 6: Banner
# ----------------------------------------------------------------------------
echo
echo "=== Gate 6: Banner ==="

mkdir -p docs/assets

cat > docs/assets/banner.svg <<'BANNER_EOF'
<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 300" role="img" aria-label="clean-sort">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#0f766e"/>
      <stop offset="100%" stop-color="#134e4a"/>
    </linearGradient>
    <linearGradient id="accent" x1="0%" y1="100%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#a855f7" stop-opacity="0.85"/>
      <stop offset="100%" stop-color="#7e22ce" stop-opacity="0.85"/>
    </linearGradient>
  </defs>
  <rect width="1200" height="300" fill="url(#bg)"/>
  <rect x="40" y="40" width="1120" height="220" rx="14" fill="url(#accent)"/>
  <g font-family="ui-sans-serif, system-ui, sans-serif" fill="#f0fdfa">
    <text x="80" y="135" font-size="64" font-weight="700">clean-sort</text>
    <text x="80" y="180" font-size="22" font-weight="400" opacity="0.92">AST-based structural sorter for Python source code</text>
    <text x="80" y="225" font-size="18" font-weight="500" opacity="0.85">preserve semantics · libcst round-trip · forward-reference barriers</text>
  </g>
</svg>
BANNER_EOF
echo "  banner.svg written"

cat > docs/assets/banner-social.svg <<'SOCIAL_EOF'
<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 150" role="img" aria-label="clean-sort">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#0f766e"/>
      <stop offset="100%" stop-color="#134e4a"/>
    </linearGradient>
  </defs>
  <rect width="600" height="150" fill="url(#bg)"/>
  <text x="30" y="65" font-family="ui-sans-serif, system-ui, sans-serif" font-size="32" font-weight="700" fill="#f0fdfa">clean-sort</text>
  <text x="30" y="95" font-family="ui-sans-serif, system-ui, sans-serif" font-size="13" fill="#f0fdfa" opacity="0.9">AST-based structural sorter for Python source code</text>
  <text x="30" y="125" font-family="ui-monospace, monospace" font-size="11" fill="#a855f7">libcst · forward-reference barriers · stepdown</text>
</svg>
SOCIAL_EOF
echo "  banner-social.svg written"

# ----------------------------------------------------------------------------
# Gate 7: Code review (populate static data; user fills in lint/test output)
# ----------------------------------------------------------------------------
echo
echo "=== Gate 7: Code review ==="

REPORT=docs/code-review-2026-09-29.md

{
  echo
  echo "## File inventory"
  echo
  echo "| Path | Lines | Notes |"
  echo "|---|---|---|"
  for f in src/clean_sort/pipeline.py src/clean_sort/classify.py \
           src/clean_sort/sorters.py src/clean_sort/config.py \
           src/clean_sort/cache.py src/clean_sort/transforms.py \
           src/clean_sort/undersort.py src/clean_sort/__init__.py \
           src/clean_sort/__main__.py src/clean_sort/cli/app.py; do
    if [ -f "$f" ]; then
      ln=$(wc -l < "$f")
      echo "| \`$f\` | $ln | |"
    fi
  done
  echo
  echo "## Test inventory"
  echo
  echo "| Path | Lines | Notes |"
  echo "|---|---|---|"
  for f in tests/test_*.py; do
    [ -f "$f" ] || continue
    ln=$(wc -l < "$f")
    echo "| \`$f\` | $ln | |"
  done
  echo
  echo "## Public surface per module"
  echo
  echo "### pipeline.py"
  echo
  echo '```python'
  grep -E '^(def|class|async def) ' src/clean_sort/pipeline.py 2>/dev/null | head -10
  echo '```'
  echo
  echo "### classify.py"
  echo
  echo '```python'
  grep -E '^(def|class|async def) ' src/clean_sort/classify.py 2>/dev/null | head -10
  echo '```'
  echo
  echo "### sorters.py"
  echo
  echo '```python'
  grep -E '^(def|class|async def) ' src/clean_sort/sorters.py 2>/dev/null | head -10
  echo '```'
  echo
  echo "## Coverage gate"
  echo
  if grep -q 'fail_under' pyproject.toml 2>/dev/null; then
    echo "Configured:"
    echo
    echo '```toml'
    grep -E 'fail_under|cov' pyproject.toml 2>/dev/null | head -5
    echo '```'
  fi
  echo
  echo "## What to run when mise is available"
  echo
  echo '```bash'
  echo "mise install"
  echo "mise run lint"
  echo "mise run test"
  echo '```'
  echo
  echo "Append the actual output below when those commands finish."
} >> "$REPORT"

echo "  code review report populated"
echo "  -> $REPORT ($(wc -l <"$REPORT") lines)"
echo

# ----------------------------------------------------------------------------
# Commit and push
# ----------------------------------------------------------------------------
echo "=== commit Gates 2/6/7 work ==="
git add .github/MIGRATION_NOTES.md docs/assets/banner.svg docs/assets/banner-social.svg docs/code-review-2026-09-29.md
git status --short
echo

GIT_AUTHOR_NAME="coder-clawy" GIT_AUTHOR_EMAIL="coder-clawy@users.noreply.github.com" \
GIT_COMMITTER_NAME="coder-clawy" GIT_COMMITTER_EMAIL="coder-clawy@users.noreply.github.com" \
git commit -m "ci+docs: Gate 2/6/7 - banner, mirror notes, populated code-review report

docs/assets/banner.svg: 1200x300 hero, teal/purple palette
docs/assets/banner-social.svg: 600x150 social-card variant
.github/MIGRATION_NOTES.md: canonical-home banner block for codeberg README
docs/code-review-2026-09-29.md: file inventory + public symbols + coverage gate" 2>&1 | tail -5

echo
echo "=== push ==="
git push origin main 2>&1 | tail -5

echo
echo "=== final state ==="
git log --oneline -4
echo
echo "remote:"
git remote -v

echo
echo "=== driver complete ==="
echo "=== finished: $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
