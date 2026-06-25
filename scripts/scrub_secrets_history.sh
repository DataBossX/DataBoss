#!/usr/bin/env bash
#
# scrub_secrets_history.sh — purge leaked files from ALL git history.
#
# ⚠️  DESTRUCTIVE & IRREVERSIBLE. Rewrites every commit and requires a
#     force-push that invalidates all existing clones/forks. Run ONLY after:
#       1. You have ROTATED every leaked key (see SECURITY.md) — scrubbing
#          history does NOT un-leak keys already pushed; rotation is the fix.
#       2. You have told every collaborator to stop pushing and re-clone after.
#
# Safe by default: does nothing unless you pass CONFIRM=PURGE.
#
# Usage:
#   CONFIRM=PURGE ./scripts/scrub_secrets_history.sh
#
set -euo pipefail

PATHS=("backend/.env" "frontend/.env" "databossx.db")

if [[ "${CONFIRM:-}" != "PURGE" ]]; then
  cat <<EOF
This will permanently rewrite git history to remove:
  ${PATHS[*]}

Refusing to run without explicit confirmation.
Re-run with:  CONFIRM=PURGE $0

Pre-flight checklist (do these FIRST):
  [ ] All 7 API keys rotated/revoked in provider consoles
  [ ] Collaborators notified; no in-flight pushes
  [ ] A backup mirror exists:  git clone --mirror <url> backup.git
EOF
  exit 1
fi

if ! command -v git-filter-repo >/dev/null 2>&1 && ! python3 -c "import git_filter_repo" 2>/dev/null; then
  cat <<EOF
git-filter-repo is required but not found.

Install:        pip install git-filter-repo
Or via brew:    brew install git-filter-repo

Alternative (BFG):
  bfg --delete-files .env
  bfg --delete-files databossx.db
  git reflog expire --expire=now --all && git gc --prune=now --aggressive
EOF
  exit 2
fi

echo ">> Backing up current refs to .git/refs-backup-pre-scrub ..."
git for-each-ref --format='%(refname) %(objectname)' > .git/refs-backup-pre-scrub.txt || true

echo ">> Purging files from all history ..."
ARGS=()
for p in "${PATHS[@]}"; do ARGS+=(--path "$p"); done
git filter-repo --invert-paths "${ARGS[@]}" --force

cat <<EOF

>> History rewrite complete.

Next (you do these manually — review first):
  1. Re-add the remote (filter-repo drops it):
       git remote add origin <repo-url>
  2. Force-push every branch and tag:
       git push --force --all origin
       git push --force --tags origin
  3. Tell all collaborators to re-clone (old clones still contain the secrets).
  4. Confirm the 'Secret Scan' CI workflow now passes.
EOF
