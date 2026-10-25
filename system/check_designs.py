#!/usr/bin/env python3
"""Checks every design in the repo before it ships to the booths. Commit, then run:

    python3 system/check_designs.py                 # HEAD, compared with origin/stable
    python3 system/check_designs.py --allow-gone    # when designs leaving booths is on purpose

Fails (exit 1) when
  - a design that's on stable is gone or moved: booths would lose it with the update
  - a design can't be used: the picture won't open, it's the wrong size, its JSON is missing or
    bad, or a photo opening isn't inside the picture (the booth would skip it)
Warns when designs a booth shows together share a number (they'd sit side by side), and says
which numbers are free. It reads committed files from git, so it sees every person's gifts even on
a booth that only has one person's on disk.
"""
import io
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path, PurePosixPath

from PIL import Image

REPO = Path(__file__).resolve().parent.parent
SIZES = {"strip": (1200, 3600), "sheet": (1800, 1200), "psheet": (1200, 1800)}  # as photobooth.py
MAX_PHOTOS = 8


def git(*args, binary=False):
    result = subprocess.run(["git", "-C", str(REPO), *args], capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode().strip())
    return result.stdout if binary else result.stdout.decode()


def designs(ref):
    """{path: (kind, who)} for every design PNG the booths would use; who is None for shared
    designs, else the person whose gift it is. Plus PNGs the booths would never show."""
    found, unused = {}, []
    for line in git("ls-tree", "-r", "--name-only", ref, "--", "frames", "gifts").splitlines():
        path = PurePosixPath(line)
        if path.suffix != ".png":
            continue
        kind = {"sheets": "sheet", "portrait": "psheet"}.get(path.parent.name, "strip")
        if path.parts[0] == "frames":
            # The app only looks in frames/, frames/sheets/ and frames/portrait/.
            ok = len(path.parts) == 2 or (len(path.parts) == 3 and kind != "strip")
            who = None
        else:
            ok = len(path.parts) >= 3 and not any(p.startswith((".", "__")) for p in path.parts)
            who = path.parts[1]
        if ok:
            found[str(path)] = (kind, who)
        else:
            unused.append(str(path))
    return found, unused


def problem(ref, path, kind):
    w, h = SIZES[kind]
    try:
        with Image.open(io.BytesIO(git("cat-file", "blob", f"{ref}:{path}", binary=True))) as im:
            size = im.size
    except Exception as e:
        return f"the picture can't be opened ({e})"
    if size != (w, h):
        return f"it's {size[0]}x{size[1]}; it should be {w}x{h}"
    sidecar = str(PurePosixPath(path).with_suffix(".json"))
    try:
        data = json.loads(git("cat-file", "blob", f"{ref}:{sidecar}"))
    except RuntimeError:
        return None if kind == "strip" and path.startswith("frames/") else "no .json with its photo openings"
    except ValueError as e:
        return f"its .json can't be read ({e})"
    try:
        raw = data.get("slots") if isinstance(data, dict) else data
        slots = [tuple(int(v) for v in slot) for slot in raw]
        assert all(len(s) == 4 for s in slots)
    except Exception:
        return "its .json needs \"slots\": [[x, y, width, height], ...]"
    if not 1 <= len(slots) <= MAX_PHOTOS:
        return f"it has {len(slots)} photo openings (1 to {MAX_PHOTOS} work)"
    for x, y, sw, sh in slots:
        if sw < 20 or sh < 20 or x < 0 or y < 0 or x + sw > w or y + sh > h:
            return f"opening {[x, y, sw, sh]} isn't inside {w}x{h}"
    if isinstance(data, dict) and data.get("stamp", "br") not in ("br", "bl", "tr", "tl"):
        return f"\"stamp\" is {data['stamp']!r}; use br, bl, tr or tl"
    return None


def number(path):
    digits = "".join(ch for ch in PurePosixPath(path).stem if ch.isdigit())
    return int(digits) if digits else None


def main(args):
    allow_gone = "--allow-gone" in args
    refs = [a for a in args if not a.startswith("--")]
    ref = refs[0] if refs else "HEAD"
    against = refs[1] if len(refs) > 1 else "origin/stable"
    errors, warnings = [], []

    found, unused = designs(ref)
    for path, (kind, _) in sorted(found.items()):
        why = problem(ref, path, kind)
        if why:
            errors.append(f"{path}: {why}")
    for path in unused:
        warnings.append(f"{path}: not in a folder the booths look in, so never shown")

    try:
        before, _ = designs(against)
    except RuntimeError:
        before = None
        warnings.append(f"no {against} to compare with; skipped the check for designs that are gone")
    if before is not None:
        for path in sorted(set(before) - set(found)):
            (warnings if allow_gone else errors).append(
                f"{path}: on {against} but gone here; booths would lose it")

    # What each booth shows together: shared + its person's gifts; the master booth: everything.
    people = sorted({who for _, who in found.values() if who})
    views = {"every booth": [p for p, (_, who) in found.items() if who is None]}
    views.update({f"{person}'s booth": [p for p, (_, who) in found.items() if who in (None, person)]
                  for person in people})
    views["the master booth"] = list(found)
    reported = set()
    for view, paths in views.items():
        groups = defaultdict(list)
        for path in paths:
            if number(path) is not None:
                groups[(found[path][0], number(path))].append(path)
        for (kind, n), same in sorted(groups.items()):
            if len(same) > 1 and tuple(sorted(same)) not in reported:
                reported.add(tuple(sorted(same)))
                warnings.append(f"{kind} number {n} is used more than once on {view}: "
                                f"{', '.join(sorted(same))}")
    used = defaultdict(set)
    for path, (kind, _) in found.items():
        if number(path) is not None:
            used[kind].add(number(path))
    counts = defaultdict(int)
    for kind, who in found.values():
        counts[who] += 1

    print(f"{len(found)} designs in {ref}: {counts[None]} shared"
          + "".join(f", {counts[p]} for {p}" for p in people))
    for kind, label in (("strip", "strips"), ("sheet", "landscape sheets"), ("psheet", "portrait sheets")):
        if used[kind]:
            print(f"Next free number for {label}: {max(used[kind]) + 1}")
    for w in sorted(set(warnings)):
        print(f"WARNING {w}")
    for e in errors:
        print(f"ERROR {e}")
    print("OK" if not errors else f"{len(errors)} problem(s): fix them before shipping to stable")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
