#!/usr/bin/env python3
"""Which design packs this booth has.

Shared designs (frames/) go on every booth. A pack (packs/<name>/) is only on the booths given it;
the others don't have its files at all (git sparse checkout). packs/booths.json lists each booth's
packs, so a reflashed booth gets them back with `setup`, and a pack added to a booth's list there
arrives with its next update. Updates only ever add packs, never take one away.

Run as admin (not with sudo):
  system/packs.py                show this booth's name, its packs and every pack there is
  system/packs.py setup NAME     this booth is NAME in packs/booths.json: install exactly its packs
  system/packs.py add PACK...    install more packs now (put them in packs/booths.json too, or a
                                 reflashed booth won't get them back)
  system/packs.py sync           install any packs booths.json lists for this booth that it doesn't
                                 have yet (the updater runs this after every update)
A booth that was never set up has every pack.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BOOTHS_FILE = REPO / "packs" / "booths.json"


def git(*args, stdin=None, check=True):
    result = subprocess.run(["git", "-C", str(REPO), *args], input=stdin, capture_output=True,
                            text=True)
    if check and result.returncode != 0:
        sys.exit(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def booth_name():
    return git("config", "--get", "snapbox.booth", check=False) or None


def installed():
    """The packs this booth has, or None if it has them all (never set up)."""
    if git("config", "--bool", "--get", "core.sparseCheckout", check=False) != "true":
        return None
    return sorted(m.group(1) for line in git("sparse-checkout", "list").splitlines()
                  if (m := re.fullmatch(r"/packs/([^/]+)/", line)))


def available():
    """The packs in the version of the app this booth is on."""
    out = git("ls-tree", "-d", "--name-only", "HEAD", "packs/")
    return sorted(Path(line).name for line in out.splitlines())


def booths():
    try:
        data = json.loads(BOOTHS_FILE.read_text())
    except (OSError, ValueError) as e:
        sys.exit(f"Can't read {BOOTHS_FILE}: {e}")
    return {name: packs for name, packs in data.items() if not name.startswith("_")}


def install(packs):
    """Exactly these packs on disk; shared designs and everything else always."""
    patterns = ["/*", "!/packs/*/"] + [f"/packs/{p}/" for p in sorted(set(packs))]
    git("sparse-checkout", "set", "--no-cone", "--stdin", stdin="\n".join(patterns) + "\n")


def show():
    have = installed()
    print(f"This booth: {booth_name() or '(not set up: run setup NAME)'}")
    print(f"Packs on it: {'all of them' if have is None else ', '.join(have) or 'none'}")
    print(f"Packs there are: {', '.join(available()) or 'none'}")
    print(f"Booths in {BOOTHS_FILE.relative_to(REPO)}: {', '.join(booths()) or 'none'}")


def main(args):
    if not args:
        show()
    elif args[0] == "setup" and len(args) == 2:
        name, known = args[1], booths()
        if name not in known:
            sys.exit(f"No booth called {name!r} in {BOOTHS_FILE.relative_to(REPO)}. "
                     f"Booths: {', '.join(known) or 'none'}. Add it there first.")
        git("config", "snapbox.booth", name)
        install(known[name])
        show()
    elif args[0] == "add" and len(args) > 1:
        missing = [p for p in args[1:] if p not in available()]
        if missing:
            print(f"Not in this version (yet): {', '.join(missing)}; installing anyway.")
        install((installed() or []) + args[1:])
        show()
    elif args == ["sync"]:
        name, have = booth_name(), installed()
        if name is None or have is None:
            print("Not set up; this booth has every pack.")
            return
        new = [p for p in booths().get(name, []) if p not in have]
        if new:
            install(have + new)
            print(f"Added packs: {', '.join(new)}")
        else:
            print("No new packs.")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
