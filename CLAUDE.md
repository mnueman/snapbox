# Photobooth (snapbox)

A portable photo booth on a Raspberry Pi 5: camera, small touchscreen, one shutter button, a printer.
`photobooth.py` is the whole app. README.md explains every feature; read it before changing one.

## Who are you helping?

The repo's owner (GitHub `mnueman`) builds the booths and gives them away as gifts. Each booth installs
updates from this public repo. Work out which situation you're in:

- **On a gifted booth, for its owner** (they can't push to this repo): see "Making your own designs".
  Don't edit, commit or delete anything in `~/photobooth`. The updater refuses to update a booth whose
  app files were edited, so the booth would stop getting updates.
- **For the repo owner** (they can push to `origin`): everything below applies.

## Making your own designs (any booth)

Put them in `~/my-designs/`, never in `~/photobooth/`. Updates never touch `~/my-designs`, and it's not in
git.

- Strips go in `~/my-designs/`, landscape sheets in `~/my-designs/sheets/`, portrait sheets in
  `~/my-designs/portrait/`. Sizes: strip 1200x3600, landscape sheet 1800x1200, portrait sheet 1200x1800
  (300 dpi; a 4x6 print holds two strips side by side, or one sheet).
- Each design is a PNG, transparent where the photos show through, plus a JSON with the same name:
  `{"slots": [[x, y, w, h], ...]}`, one box per photo in pixels, in the order they're taken (3 or 4 for
  a strip). Optional: `"stamp": "bl"` (or `"tl"`, `"tr"`) moves the date stamp out of the bottom right.
- Draw them with Python and Pillow (installed). The fonts in `~/photobooth/frames/fonts/` can be used.
  `~/photobooth/all_frames.py` and `sheet_kit.py` show how the built-in designs are drawn; use them as
  examples, but keep your own scripts and files in `~/my-designs` too.
- Name them anything; a number in the name sets the order (`party1.png` before `party2.png`). Folders
  inside `~/my-designs` are fine (`~/my-designs/halloween/`, with its own `sheets/` and `portrait/`).
  They show after the built-in designs of the same shape, within 15 seconds while the booth is idle;
  no restart needed. If one doesn't show, `journalctl -u photobooth.service | grep Skipping` says why.
  Look at the result before saying it's done.

## Running the app

- It runs as `photobooth.service` (systemd, user admin), with a watchdog and `photobooth-guard.timer`.
  Logs: `journalctl -u photobooth.service -f`.
- Designs are picked up without a restart. Restart after changing the code (no sudo needed):
  `kill -INT $(systemctl show photobooth.service -p MainPID --value)`. systemd starts it again within
  seconds; check the log for "Vintage photobooth app started."
  Use SIGINT: it's the service's stop signal and saves a half-finished strip. SIGTERM is swallowed by
  pygame/SDL and does nothing. A sandboxed shell may not be allowed to signal the service.
- Before restarting after a code change, run the startup offscreen: exec `photobooth.py` up to its last
  `resize_live_photos(current_capacity())` with `gpiozero`, `picamera2`, `libcamera` and `smbus2` mocked,
  `SDL_VIDEODRIVER=dummy` and `HOME` pointing at a scratch copy of `~/photobooth` (with its `.git`).
  Never point `HOME` at the real one: startup deletes leftover captures there. A startup error takes
  the booth down until it's fixed.

## Designs: shared, gifts and the owner's own

| Folder | On which booths |
| --- | --- |
| `frames/` (+ `sheets/`, `portrait/`) | Every booth; new ones arrive with updates |
| `gifts/<person>/<collection>/` (same layout) | That person's booth, and the master booth |
| `~/my-designs/` (and folders in it) | Only that booth; never in git |

- `gifts/<person>/` is named after the person, spaces and all (`gifts/Nick & Maddy Atkinson/`), with a
  subfolder per collection (`wedding/`, `army/`, `hawaii/`). The repo owner names these folders: ask
  them, don't invent one.
- `system/gifts.py setup "Their Name"` sets who a booth is for (git config `snapbox.booth`) and uses git
  sparse checkout so only `gifts/<that person>/` is on its disk. Everything added there later, new
  collections included, arrives with the next update. `setup master` = every person's gifts (the repo
  owner's own booth). A booth never set up also gets everyone's.
- To gift someone more: add a collection folder to theirs and ship an update. Do it on a master booth:
  on a booth set up for one person, git can't see other people's folders (`setup master` first, then
  set it back).
- The app re-reads designs every 15 s while idle (`refresh_designs`, `tick_designs`), skips designs it
  can't use (`design_problem`: wrong size, missing/bad JSON, openings outside the picture, damaged) and
  swaps a design that disappears mid-use for one of the same layout with room for the photos taken.
  A saved strip remembers its design by path ("design" in the JPEG comment), else by file name.
- Never delete, rename or renumber a shipped design, and never move one between `frames/` and `gifts/`:
  booths would lose it on their next update. New designs get the next free number.
- Before every push to `stable`: commit, then `python3 system/check_designs.py`. It reads the commit
  (every person's gifts, whatever is on disk), fails on designs that would vanish from booths or can't
  be used, warns on repeated numbers and prints the next free ones. `--allow-gone` only when the owner
  agrees designs should leave booths.
- Built-in designs are generated: `all_frames.py` (strips 11-40), `realistic.py` (41-44),
  `sheet_frames.py` (sheets, from `sheets_landscape.py` / `sheets_portrait.py`). `design_folders.py` says
  which folder each one goes in.

## Branches, updates and publishing (repo owner)

- Work on `pi5-photobooth`; commit and push every working change to `origin` (github.com/mnueman/snapbox).
  Commit author: `mnueman <182584212+mnueman@users.noreply.github.com>`.
- Booths install `stable`. `git push origin pi5-photobooth:stable` ships to every booth: only do it when
  the owner has tried the change or asks for it.
- `upstream` is the original project; never push there, and don't name its author anywhere user-facing.
- The repo is public: never commit passwords, keys, WiFi details, photos, `settings.json` or other
  runtime files (see `.gitignore`).
- Updater: the app's BOOTH > UPDATES starts `system/photobooth-update.py` (root, via polkit). It refuses
  if tracked files changed, checks the new version compiles, checks it out (detached; sparse, so only
  this booth's gifts), runs `install.sh`, and rolls back unless the app starts and stays up for 20 s.
  After an update the booth is on a detached commit; `git switch pi5-photobooth` before dev work.
- Setting up a booth from scratch: README.md, "Set up a booth".

## Hardware notes

Pi 5; IMX708 camera on CAM/DISP 0; 2.8" DSI touchscreen (native portrait 480x640, mounted landscape) on
CAM/DISP 1; shutter button GPIO 26. GPIO 16 must stay unused (Geekworm X1200 UPS: fuel gauge I2C 0x36,
power-loss detect GPIO 6). Printer: Canon SELPHY CP1500, 4x6. Before a booth is given away, log out of
any GitHub account on it (`gh auth logout`).
