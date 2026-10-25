#!/bin/sh
# Points this booth at the public repo for updates (the "stable" branch, over HTTPS: no key or
# login needed). Run once per booth as admin (not with sudo). Older booths used a per-booth SSH
# deploy key; running this switches them over.
set -e
REPO_URL="https://github.com/mnueman/snapbox.git"
cd "$(dirname "$0")/.."

git config --unset core.sshCommand 2>/dev/null || true
git remote remove updates 2>/dev/null || true
git remote add updates "$REPO_URL"
GIT_TERMINAL_PROMPT=0 git ls-remote updates stable >/dev/null
echo "Updates come from $REPO_URL (branch stable)."
