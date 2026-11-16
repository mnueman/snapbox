#!/usr/bin/env python3
"""Tries designs the way the booth uses them, without touching the camera, screen or printer.

For each design: builds a finished strip (or BIG SHEET) with a different plain colour as each
photo, using the booth's own code (photobooth.py), then lays it out for printing and fits it to
the paper exactly as a real print would be. It checks that
  - the booth accepts the design at all (right size, readable JSON)
  - the finished picture is the right size
  - every photo opening shows its own photo (the JSON's boxes match the see-through parts)
  - no see-through part is left outside the openings (it would print white)
  - the print is the right size for the printer, and nothing from outside the design shows on the
    part of the paper that's left after tearing off the tabs

    python3 system/test_designs.py              # every design this booth shows
    python3 system/test_designs.py --new        # only the ones not on booths yet (not on stable)
    python3 system/test_designs.py frame51 nm03 # designs whose path contains one of these
    python3 system/test_designs.py --sheet OUT.jpg ...   # also save a picture of the results

The app runs from a throwaway home folder (links to the real code and designs, its own empty
photo folders), so nothing on the booth is changed. system/print_fit_sim.py checks the paper fit
itself in depth; system/check_designs.py checks what ships. Exit code 1 if a design has a problem.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
MY_DESIGNS = Path.home() / "my-designs"
RUNTIME = {"captures", "strips", "settings.json", "current_preview.jpg", "__pycache__",
           "update-result.json", "update-pending.json"}
COLOURS = [(255, 0, 0), (0, 200, 0), (0, 0, 255), (255, 200, 0), (0, 220, 220), (220, 0, 220),
           (120, 60, 0), (90, 90, 90)]


def load_app(home):
    """photobooth.py up to the end of its start-up, with the hardware faked."""
    booth = home / "photobooth"
    booth.mkdir()
    for entry in REPO.iterdir():
        if entry.name not in RUNTIME:
            (booth / entry.name).symlink_to(entry)
    if MY_DESIGNS.is_dir():
        (home / "my-designs").symlink_to(MY_DESIGNS)
    os.environ.update(HOME=str(home), SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
    for name in ("gpiozero", "picamera2", "libcamera", "smbus2"):
        sys.modules[name] = mock.MagicMock()
    camera = mock.MagicMock()
    camera.camera_properties = {"ScalerCropMaximum": (0, 0, 4608, 2592), "PixelArraySize": (4608, 2592)}
    sys.modules["picamera2"].Picamera2.return_value = camera
    os.chdir(booth)
    sys.path.insert(0, str(booth))
    src = (booth / "photobooth.py").read_text()
    marker = "resize_live_photos(current_capacity())"
    app = {"__name__": "photobooth_test", "__file__": str(booth / "photobooth.py")}
    exec(compile(src[:src.rindex(marker) + len(marker)], "photobooth.py", "exec"), app)
    return app


def on_stable():
    """Repo paths that origin/stable has (so booths have them already)."""
    def names(*args):
        out = subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True)
        return set(out.stdout.splitlines()) if out.returncode == 0 else None
    shipped = names("ls-tree", "-r", "--name-only", "origin/stable")
    if shipped is None:
        sys.exit("Can't read origin/stable (git fetch origin first).")
    return shipped


def check(app, index, np, Image):
    """(problems, the finished picture, the fitted print) for the design at this index."""
    path = app["frames"][index]
    kind, slots, count = app["frame_kind"](index), app["frame_slots"](index), app["frame_slot_count"](index)
    photos = [Image.new("RGB", (1600, 1200), COLOURS[k]) for k in range(count)]
    done = app["compose_single_strip"](photos, index, fx=app["WEB_NEUTRAL_FX"]).convert("RGB")
    app["_forget_slot_cache"](photos)  # the app remembers fitted photos; these are gone now
    problems = []
    if done.size != app["frame_size"](index):
        problems.append(f"finished picture is {done.size}, not {app['frame_size'](index)}")
    seen = np.asarray(done).astype(int)
    clear = np.asarray(Image.open(path).convert("RGBA"))[..., 3] < 8
    if clear.shape != seen.shape[:2]:
        # A design saved at another size of the same shape: compare at the size it's used at.
        clear = np.asarray(Image.open(path).convert("RGBA").resize(done.size))[..., 3] < 8
    owner = np.full(clear.shape, -1)
    for k, (x, y, w, h) in enumerate(slots):
        owner[y:y + h, x:x + w] = k
    for k in range(count):
        opening = clear & (owner == k)
        if not opening.any():
            problems.append(f"photo {k + 1}: nothing see-through inside its box")
            continue
        right = (np.abs(seen[opening] - COLOURS[k]).max(axis=1) < 30).mean()
        if right < 0.995:
            problems.append(f"photo {k + 1}: only {right:.1%} of its opening shows it")
    stray = int((clear & (owner < 0)).sum())
    if stray > 200:
        problems.append(f"{stray} see-through pixels outside every photo box (they print white)")
    sheet = app["make_pair_print"](done, done) if kind == "strip" else app["make_sheet_print"](done)
    fitted = app["fit_print"](sheet)
    want = (app["PRINT_W"], app["PRINT_H"])
    if sheet.size != want or fitted.size != want:
        problems.append(f"print is {sheet.size} / {fitted.size}, not {want}")
    return problems, done, fitted


def paper_fit(app, np, Image):
    """Pixels from outside the design that land on the paper that's left: must be none."""
    w, h = app["PRINT_W"], app["PRINT_H"]
    fitted = np.asarray(app["fit_print"](Image.new("RGB", (w, h), (0, 0, 0)))).max(axis=2)
    trim, px = app["PRINT_TRIM_MM"], w / (4 * 25.4)
    y0, y1 = round(trim["top"] * px) + 3, h - round(trim["bottom"] * px) - 3
    x0, x1 = round(trim["left"] * px) + 3, w - round(trim["right"] * px) - 3
    return int((fitted[y0:y1, x0:x1] > 40).sum())


def main():
    args = sys.argv[1:]
    sheet_out = None
    if "--sheet" in args:
        at = args.index("--sheet")
        sheet_out = Path(args[at + 1]).resolve()
        del args[at:at + 2]
    only_new = "--new" in args
    wanted = [a for a in args if not a.startswith("--")]
    shipped = on_stable() if only_new else set()

    with tempfile.TemporaryDirectory(prefix="snapbox-designs-") as tmp:
        home = Path(tmp)
        app = load_app(home)
        import numpy as np
        from PIL import Image
        tested, failed, tiles = 0, 0, []
        for index, path in enumerate(app["frames"]):
            rel = Path(path).relative_to(home)
            in_repo = rel.parts[0] == "photobooth"
            name = str(Path(*rel.parts[1:])) if in_repo else f"~/{rel}"
            if wanted and not any(w in name for w in wanted):
                continue
            if only_new and in_repo and name in shipped:
                continue
            problems, done, fitted = check(app, index, np, Image)
            tested += 1
            failed += bool(problems)
            print(f"{'FAIL' if problems else 'ok  '} {name}  ({app['frame_kind'](index)}, "
                  f"{app['frame_slot_count'](index)} photos)" + "".join(f"\n       {p}" for p in problems))
            if sheet_out:
                tile = fitted.copy()
                tile.thumbnail((240, 360))
                tiles.append(tile)
        outside = paper_fit(app, np, Image)
        print(f"\nPaper fit: {outside} pixels from outside the design on the paper that's left "
              f"({'ok' if outside == 0 else 'FAIL'})")
        if sheet_out and tiles:
            cols = min(12, len(tiles))
            rows = -(-len(tiles) // cols)
            board = Image.new("RGB", (cols * 246, rows * 366), (40, 40, 40))
            for i, tile in enumerate(tiles):
                board.paste(tile, ((i % cols) * 246 + 3, (i // cols) * 366 + 3))
            board.save(sheet_out, quality=85)
            print(f"Pictures of the prints as sent to the printer: {sheet_out}")
        print(f"{tested} designs tried, {failed} with problems.")
        os.chdir("/")
    sys.exit(1 if failed or outside or not tested else 0)


if __name__ == "__main__":
    main()
