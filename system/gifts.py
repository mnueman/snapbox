#!/usr/bin/env python3
"""Which person's gift designs this booth has.

Shared designs (frames/) go on every booth. Designs made for one person live in gifts/<person>/,
named after them, one subfolder per collection (gifts/Nick & Maddy Atkinson/wedding/, .../army/, ...).
A booth set up
for a person has only gifts/<person>/: other people's gifts aren't on its disk at all (git sparse
checkout). Anything added to gifts/<person>/ later, including new collections, arrives with the
booth's next update. A booth set up as "master" (the creator's own) has every person's gifts.

Run as admin (not with sudo):
  system/gifts.py                      show who this booth is for and which gift folders there are
  system/gifts.py setup "Their Name"   this booth is theirs: only gifts/Their Name/ (it can be made
                                       later; capitals don't matter for a folder that's there)
  system/gifts.py setup master         every person's gifts, now and future
A booth that was never set up also has every person's gifts.
"""
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MASTER = "master"


def git(*args, stdin=None, check=True):
    result = subprocess.run(["git", "-C", str(REPO), *args], input=stdin, capture_output=True,
                            text=True)
    if check and result.returncode != 0:
        sys.exit(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def people():
    """The people with a gift folder in git here (committed or not, on disk or not)."""
    out = git("ls-files", "-z", "--", "gifts/")
    return sorted({Path(line).parts[1] for line in out.split("\0") if len(Path(line).parts) > 2})


def show():
    name = git("config", "--get", "snapbox.booth", check=False)
    sparse = git("config", "--bool", "--get", "core.sparseCheckout", check=False) == "true"
    if not name:
        print('This booth: not set up (it has every person\'s gifts). Run: system/gifts.py setup "Their Name"')
    elif name == MASTER:
        print("This booth: master (every person's gifts)")
    else:
        there = (REPO / "gifts" / name).is_dir()
        print(f"This booth: {name} (gets gifts/{name}/{'' if there else ', which has nothing in it yet'})")
    if name and name != MASTER and not sparse:
        print("  Warning: other people's gifts are on disk too; run setup again.")
    print(f"People with gifts: {', '.join(people()) or 'none'}")


def setup(name):
    name = " ".join(name.split())
    # Letters, numbers, spaces and & ' . , - ( ): nothing git's sparse-checkout patterns treat specially.
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9 &'.,()-]*[A-Za-z0-9.)])?", name):
        sys.exit("Use letters, numbers, spaces and & ' . , - ( ) in the name, e.g. \"Nick & Maddy Atkinson\".")
    if name.lower() == MASTER:
        name = MASTER
    name = next((p for p in people() if p.lower() == name.lower()), name)
    if name == MASTER:
        git("sparse-checkout", "disable")
    else:
        if name not in people():
            print(f"There's no gifts/{name}/ yet; this booth will get it once it's made.")
        patterns = ["/*", "!/gifts/*/", f"/gifts/{name}/"]
        git("sparse-checkout", "set", "--no-cone", "--stdin", stdin="\n".join(patterns) + "\n")
    git("config", "snapbox.booth", name)
    show()


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        show()
    elif len(args) == 2 and args[0] == "setup":
        setup(args[1])
    else:
        sys.exit(__doc__)
