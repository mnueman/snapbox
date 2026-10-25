"""Which pack each generated design goes in, and so which folder the generators write it to.

Shared designs (every booth) live in frames/; a pack's in packs/<pack>/. Each design folder is laid
out the same: strips at the top, landscape BIG SHEETs in sheets/, portrait ones in portrait/.
A booth only has the packs packs/booths.json gives it (system/packs.py), so don't move a design
between shared and a pack once it has shipped: booths without the pack would lose it.
"""
import os

# Strips by number (all_frames.py, realistic.py).
STRIP_PACKS = {**{n: "atkinsons" for n in range(12, 20)},
               **{n: "army" for n in range(32, 37)},
               **{n: "hawaii" for n in range(37, 41)}}


def sheet_pack(label):
    """A BIG SHEET design's pack, from its name in sheets_landscape.py / sheets_portrait.py."""
    if label.startswith("The Atkinsons"):
        return "atkinsons"
    if label.startswith("Army"):
        return "army"
    if "Hawaii" in label or label.startswith("Aloha"):
        return "hawaii"
    return None


SUBFOLDERS = {"strip": "", "sheet": "sheets", "portrait": "portrait"}


def design_folder(pack, kind):
    """frames/... for shared designs, packs/<pack>/... for a pack's; kind: strip, sheet or portrait."""
    base = "frames" if pack is None else os.path.join("packs", pack)
    return os.path.join(base, SUBFOLDERS[kind]) if SUBFOLDERS[kind] else base


def all_design_folders(kind):
    """Every folder designs of this kind can be in (for a full rebuild to clear)."""
    packs = sorted(os.listdir("packs")) if os.path.isdir("packs") else []
    return [design_folder(None, kind)] + [design_folder(p, kind) for p in packs
                                          if os.path.isdir(os.path.join("packs", p))]
