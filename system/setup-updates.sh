#!/bin/sh
# Gives this booth its own read-only key for downloading updates from the private repo.
# Run once per booth as admin (not with sudo), then add the printed key on GitHub:
#   repo Settings > Deploy keys > Add deploy key (leave "Allow write access" unticked).
set -e
REPO_SSH="git@github.com:mnueman/snapbox.git"
KEY="$HOME/.ssh/snapbox_deploy"
cd "$(dirname "$0")/.."

mkdir -p "$HOME/.ssh"
chmod 700 "$HOME/.ssh"
if [ ! -f "$KEY" ]; then
    ssh-keygen -q -t ed25519 -N "" -C "snapbox booth $(hostname) $(date +%Y-%m-%d)" -f "$KEY"
fi

# Trust github.com by the host keys GitHub publishes over HTTPS, not whatever answers first.
curl -fsS https://api.github.com/meta | python3 -c '
import json, sys
for key in json.load(sys.stdin)["ssh_keys"]:
    print("github.com", key)' > "$HOME/.ssh/known_hosts_github"

git config core.sshCommand \
    "ssh -i $KEY -o IdentitiesOnly=yes -o UserKnownHostsFile=$HOME/.ssh/known_hosts_github -o StrictHostKeyChecking=yes"
git remote remove updates 2>/dev/null || true
git remote add updates "$REPO_SSH"

echo
echo "Add this key on GitHub (repo Settings > Deploy keys, read-only):"
echo
cat "$KEY.pub"
echo
echo "Then check it works with:  git -C $(pwd) ls-remote updates stable"
