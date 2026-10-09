"""BIG SHEET designs: landscape 6x4 sheets (1800x1200) in frames/sheets/ and portrait 4x6
sheets (1200x1800) in frames/portrait/, each a PNG with transparent photo openings plus a JSON
with the slots (and optionally "stamp": the corner the date stamp goes in).
The designs live in sheets_landscape.py and sheets_portrait.py; the shared drawing kit in sheet_kit.py.
Usage (from the photobooth folder):
    python3 sheet_frames.py              # everything
    python3 sheet_frames.py L            # landscape only (L3 L7: just those)
    python3 sheet_frames.py P            # portrait only (P1 P12: just those)
"""
import json, os, sys

import sheets_landscape
import sheets_portrait

SETS = {"L": (os.path.join("frames", "sheets"), "sheet", sheets_landscape.DESIGNS),
        "P": (os.path.join("frames", "portrait"), "portrait", sheets_portrait.DESIGNS)}


def build(kind, numbers=None):
    folder, prefix, designs = SETS[kind]
    os.makedirs(folder, exist_ok=True)
    if numbers is None:
        # A full rebuild: clear old designs so removed or renumbered ones don't linger.
        for f in os.listdir(folder):
            if f.startswith(prefix) and f.endswith((".png", ".json")):
                os.remove(os.path.join(folder, f))
    for n, (label, fn) in enumerate(designs, 1):
        if numbers and n not in numbers:
            continue
        img, slots, extra = fn()
        img.save(os.path.join(folder, f"{prefix}{n}.png"))
        with open(os.path.join(folder, f"{prefix}{n}.json"), "w") as f:
            json.dump({"slots": slots, "name": label, **extra}, f, indent=2)
        print(f"{prefix}{n}: {label} ({len(slots)} photos)")


if __name__ == "__main__":
    args = sys.argv[1:] or ["L", "P"]
    picks = {}
    for a in args:
        kind, num = a[0].upper(), a[1:]
        picks.setdefault(kind, set())
        if num:
            picks[kind].add(int(num))
    for kind, nums in picks.items():
        build(kind, nums or None)
