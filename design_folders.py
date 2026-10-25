"""Which folder each generated design goes in: shared (frames/) or a person's gifts.

Shared designs (every booth) live in frames/. Designs made for one person live in
gifts/<person>/<collection>/, e.g. gifts/Nick & Maddy Atkinson/wedding/; a booth set up as <person>
(system/gifts.py) gets everything in gifts/<person>/, including collections added later.
Every design folder is laid out the same: strips at the top, landscape BIG SHEETs in sheets/,
portrait ones in portrait/. Don't move or delete a design once it has shipped: booths would lose it
(system/check_designs.py catches this).
"""
import os

# Strips by number (all_frames.py; realistic.py's 41-44 are shared).
ATKINSONS = "Nick & Maddy Atkinson"
STRIP_GIFTS = {**{n: f"{ATKINSONS}/wedding" for n in range(12, 20)},
               **{n: f"{ATKINSONS}/army" for n in range(32, 37)},
               **{n: f"{ATKINSONS}/hawaii" for n in range(37, 41)}}


def sheet_gift(label):
    """A BIG SHEET design's gift folder, from its name in sheets_landscape.py / sheets_portrait.py."""
    if label.startswith("The Atkinsons"):
        return f"{ATKINSONS}/wedding"
    if label.startswith("Army"):
        return f"{ATKINSONS}/army"
    if "Hawaii" in label or label.startswith("Aloha"):
        return f"{ATKINSONS}/hawaii"
    return None


SUBFOLDERS = {"strip": "", "sheet": "sheets", "portrait": "portrait"}


def design_folder(gift, kind):
    """frames/... for shared designs, gifts/<gift>/... for a person's; kind: strip, sheet or portrait."""
    base = "frames" if gift is None else os.path.join("gifts", *gift.split("/"))
    return os.path.join(base, SUBFOLDERS[kind]) if SUBFOLDERS[kind] else base
