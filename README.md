# photobooth

## Hardware (Raspberry Pi 5 build)

- Camera: IMX708 on CAM/DISP 0
- Screen: 800x480 DSI touchscreen on CAM/DISP 1, mounted portrait
- Shutter button: GPIO 26 to GND (GPIO 16 is reserved for the X1200)
- Optional Geekworm X1200 UPS: MAX17040 fuel gauge at I2C 0x36, power-loss detect on GPIO 6.
  Battery % shows top-right; warns at 20%, saves and shuts down at 5% / 3.20 V while on battery.
  If the X1200 isn't detected, the battery display is hidden.

## Set up a booth (new SD card, or starting fresh)

1. Flash Raspberry Pi OS Lite (64-bit) with Raspberry Pi Imager: username `admin`, hostname `photobooth`,
   the WiFi network, and SSH on.
2. Add to the end of `/boot/firmware/config.txt` (and set `camera_auto_detect=0` higher up):

   ```
   dtparam=i2c_arm=on
   dtoverlay=imx708,cam0
   dtoverlay=vc4-kms-dsi-waveshare-panel,2_8_inch
   ```

3. Load `i2c-dev` at boot (`echo i2c-dev | sudo tee /etc/modules-load.d/i2c-dev.conf`) and install:

   `sudo apt install --no-install-recommends git python3-picamera2 python3-pygame python3-pil python3-numpy python3-gpiozero python3-lgpio python3-smbus2 libegl-mesa0 libegl1 libgles2 i2c-tools`

4. Get the app and say who the booth is for: the name of their folder in `gifts/` (see "Designs" below),
   in quotes, or `master` for your own booth with everyone's gifts:

   ```
   git clone -b stable https://github.com/mnueman/snapbox.git ~/photobooth
   ~/photobooth/system/gifts.py setup "Nick & Maddy Atkinson"
   ~/photobooth/system/setup-updates.sh
   sudo ~/photobooth/system/install.sh
   sudo reboot
   ```

The repo is public, so this needs no GitHub login or key. Photos, settings and `~/my-designs` live only on
the SD card: copy them off first if you're replacing a card that still works.

Raw captures in `captures/` are deleted once their strip is saved to `strips/archive/`.

## Button interface:

| Presses | Create Mode | Browse Mode |
| --- | --- | --- |
| 1 short | Take a photo | Next older strip |
| 2 short | Next frame design | Next newer strip |
| 3 short | Switch between 3-photo and 4-photo | Print two copies side by side |
| Long press (1s+) | Switch to browse | Switch to create |
| 5 short | Rotate screen: portrait / flipped / landscape (strip cut in half, side by side) / flipped — saved | Same |
| Super long press (6s+) | Shut down | Shut down |

On the touchscreen, swipe left/right on the main screen to change the frame design (create mode) or the
strip shown (browse mode).

The round buttons down the left of the main screen: settings (gear), REVIEW (photos), quick effects (sparkle,
gold while any effect is on) and the layout (a skinny strip, a wide sheet and a tall sheet; the one in use is
filled). Tapping the layout button goes PHOTO STRIPS -> BIG SHEET landscape -> BIG SHEET portrait -> back;
strips always come back as four photos, and each layout remembers the design last used.

- PHOTO STRIPS: 2x6 strips, printed two to a 4x6 sheet. `all_frames.py` and `realistic.py`.
- BIG SHEET landscape: one 6x4 sheet with landscape photos.
- BIG SHEET portrait: one 4x6 sheet with portrait photos.

Until the first photo, swiping goes through every design of the current layout, whatever its number of
photos; after it, only designs with the same number.

## Designs

Designs come from three places, each laid out the same way: strips (1200x3600) at the top, landscape sheets
(1800x1200) in `sheets/`, portrait sheets (1200x1800) in `portrait/`. Each design is a PNG with transparent
photo openings plus a JSON with the same name giving the openings (`{"slots": [[x, y, w, h], ...]}`, and
optionally `"stamp": "bl"`, `"tl"` or `"tr"` to move the date stamp to another corner).

| Folder | What | On which booths |
| --- | --- | --- |
| `frames/` | Shared designs | Every booth. New ones arrive with updates. |
| `gifts/<person>/<collection>/` | Made for one person, e.g. `gifts/Nick & Maddy Atkinson/wedding/`, `.../army/`, `.../hawaii/` | That person's booth, and the master booth |
| `~/my-designs/` (and any folders in it) | The booth owner's own designs | Only that booth. Not in git; updates never touch it. |

Shared and gift designs are shown together in number order; the owner's own come last. The booth looks
for new, changed or removed designs every 15 seconds while it's idle, so nothing needs a restart. A design
that goes missing while it's in use is swapped for another of the same layout (with room for the photos
already taken); a design that can't be used (wrong size, no or bad JSON, an opening outside the picture,
a damaged picture) is skipped and the reason logged.

- Who a booth is for: `system/gifts.py setup "Their Name"` (shows the current setup with no arguments).
  The booth then has `gifts/Their Name/` and nothing else from `gifts/`: other people's gifts aren't on
  it at all (git sparse checkout). `setup master` is for your own booth: every person's gifts. A booth
  never set up also has everyone's.
- To gift someone more designs, add a folder to theirs (`gifts/Their Name/nyc/`) and publish an update.
  It arrives on their booth with nothing else to change. Their folder can be made before or after their
  booth is set up.
- Make designs for other people on the master booth: on a booth set up for one person, git can't see
  the other people's folders.
- Never delete, rename or move a design that has shipped, including between `frames/` and `gifts/`:
  booths would lose it with their next update. Give new designs new numbers.
- Before publishing an update, commit and run `python3 system/check_designs.py`. It fails if a design
  that's on `stable` would be gone or a design can't be used, warns about repeated numbers, and says
  which numbers are free. (`--allow-gone` when designs leaving booths is intended.)
- Generators: `python3 all_frames.py [numbers]` (strips 11-40), `python3 realistic.py` (strips 41-44) and
  `python3 sheet_frames.py` (sheets; designs in `sheets_landscape.py` / `sheets_portrait.py`, drawing kit
  in `sheet_kit.py`). `design_folders.py` decides which folder each generated design goes in.
- Fonts in `frames/fonts/` are Google Fonts; see `frames/fonts/FONTS.txt`.

## Settings menu

Tap the gear in the top-left corner of the screen. Use the ◀ ▶ arrows to change a setting (they go round: ▶ on the last choice goes back to the
first, usually OFF); changes save automatically (`settings.json`) and the camera and effects tabs show a live preview, cropped like the next
photo. Tap the preview (or FULL SCREEN PREVIEW) to make it as big as the screen allows, with one setting
underneath: tap a setting's name (or swipe) to pick which. Tap DONE or press the button to close.

- Camera tab: brightness, colour look, movement (sharper vs brighter), focus, lighting type, zoom, mirror preview.
  Each lighting type locks the white balance to one colour temperature (warm bulbs 2900 K, indoor 3600 K,
  office 4300 K, sunny 5600 K, cloudy/shade 7000 K); AUTO lets the camera decide.
  Colour looks: normal, vivid, warm, cool, soft & dreamy, black & white, noir, sepia, film (warm), film (B&W),
  film: portrait, film: golden, film: cool green, instant photo, 70s faded, cross-processed. The live preview
  shows the look; film looks add grain and a vignette.
- Effects tab: vintage add-ons that go on every photo with any frame, and stack: DATE STAMP (the date in
  orange seven-segment digits, like a 90s film camera), and LIGHT LEAKS, RED LIGHT SPOTS and LIGHT STREAKS &
  DUST, each OFF or one of ten named styles that look the same every time. The sparkle button on the main
  screen opens them over a big live preview (it's gold while any effect is on).
  - DATE STAMP: ON: TODAY uses the Pi's clock, which is only set while it's on WiFi (the row shows the date
    it will print). ON: MY DATE opens a number pad: type MM DD YY and SAVE. Tap the row to change the date.
    MY DATE stays until it's changed or switched back to TODAY, so it also works for stamping a special day.
  - RANDOM EFFECT EACH PHOTO (OFF / ON) picks the leaks / spots / streaks for every photo on its own,
    instead of those three settings, so one strip can mix kinds. Each photo: 35% nothing, otherwise half
    the time one style at full strength (the four heaviest are left out) and half the time two gentle
    styles of different kinds, toned down. A photo never gets the same effect as the one before it. The
    three rows show the next photo's pick; tap RANDOM to shuffle it. Changing any of the three by hand
    turns RANDOM off.
- Booth tab: screen orientation, screen-off time, countdown before each photo (off / 3 / 5 / 10 s), review auto-keep
  time, auto shut down when idle (off / 15 / 30 min / 1 / 2 / 4 h), UPDATES, Shut down (tap twice), and a reminder
  of the button presses.
- Auto shut down works on battery and on mains or a power bank. A minute before, the screen wakes and counts down;
  any tap or press keeps the booth on. A half-finished strip is saved first.
- WiFi tab: TURN WIFI OFF (tap twice; it also stops SSH and updates) and TURN WIFI ON; the booth remembers
  which across restarts. It also shows the connected network and IP, scans for nearby networks (one entry per name, strongest
  access point), and joins one. Tap a network, type the password on the on-screen keyboard and tap CONNECT
  (or USE SAVED PASSWORD for a network the Pi already knows). The old network stays saved until the new one
  connects, so a wrong password can't leave the booth offline. Open and WPA/WPA2/WPA3 networks work;
  enterprise (802.1X) and hidden networks don't. Needs `system/photobooth-wifi.rules` (installed by `install.sh`).
- The WiFi tab also shows the command to reach the Pi from a computer on the same network, e.g.
  `ssh admin@192.168.4.62` (the IP changes with each network) or `ssh admin@photobooth.local`
  (works on any network that lets devices see each other).

## Reviewing saved strips (photo button)

Tap the photo button under the gear to open REVIEW. Swipe left/right (or use ◀ ▶) through saved strips,
newest first. Every print is one 4x6 sheet (Canon SELPHY CP1500) holding two strips side by side.
PRINT 2 COPIES prints the strip on screen twice. MIX 2 STRIPS picks the strip on screen for the left half:
swipe to another and tap PRINT THESE 2; the screen shows the sheet as it will print. CHANGE FRAME rebuilds
the strip with another frame (swipe to try them, SAVE THIS FRAME to keep one): each strip's photos are kept
in `strips/archive/photos/` for this (about 1 MB a strip; strips saved before this feature can't be
re-framed). DELETE asks for a second tap within 4 seconds before it
deletes, so a stray tap can't remove a photo. The top shows free storage and roughly how many more strips
fit. BACK, any button press, or a minute untouched returns to the camera.

Storage: after saving a strip with under 1 GB free the screen warns "STORAGE LOW". Under 200 MB the booth
won't take a photo and says "STORAGE FULL – delete old strips in REVIEW"; if a strip can't be saved, its
photos are kept so it can be saved once there's room.

## Review screen

When the last photo is taken, the finished strip stays on screen:

| Presses | Review |
| --- | --- |
| 1 short | Keep: save the strip and start a new one |
| 2 short | Retake the last photo |
| 3 short | Try the next frame design |

With no press for 20 seconds (changeable in the settings menu) the strip is kept automatically.

## Screen sleep

After 2 minutes with no presses or touches (changeable in the settings menu) the backlight turns off
and the live preview pauses. Any press or a tap wakes it; that press is only a wake-up and doesn't take a photo.
The 6-second shutdown still works while the screen is off. The screen stays on while printing or on the review screen.

## Start on boot

`sudo system/install.sh` installs `photobooth.service` (starts the app on boot, restarts it if it crashes)
and a sudoers rule that lets the app run `shutdown now` for the 6-second press and empty battery.

Layers that keep it running:

- `photobooth.service` restarts the app on any exit and never gives up (`Restart=always`, no start limit).
- systemd watchdog: the app pings systemd from its main loop; if it freezes for 60s it is restarted.
- `photobooth-guard.timer` starts the service every minute if it isn't running for any other reason.
- If the screen isn't ready at boot, the app exits so systemd retries instead of running without a screen.
- Raspberry Pi OS's hardware watchdog reboots the Pi if the whole system hangs.
- Settings and strips are written with fsync + rename, so a power cut can't leave them empty.
- An unexpected error in the main loop is logged and the booth carries on; 5 within a minute restarts the app.
- If the camera isn't detected the screen says "CAMERA NOT FOUND - check the cable" and keeps retrying.
- A damaged frame file is skipped instead of crashing; only the 4 most recent frames are kept in memory.
- Raw captures left by an interrupted strip are cleared at startup.
- Logs survive reboots (capped at 50 MB): `journalctl -u photobooth -b -1` shows the previous boot.

## Updates

Booths install the `stable` branch from the public GitHub repo (github.com/mnueman/snapbox) over HTTPS,
so they need no key or login. Day-to-day work goes on `pi5-photobooth`; booths only see a change once
`stable` moves.

Publish an update (after trying it on your own booth):

`git push origin pi5-photobooth:stable`

Each booth checks 90 s after starting and every 6 hours. When it finds something new and is idle it shows
"Your creator has gifted you with an update!"; BOOTH tab > UPDATES > INSTALL UPDATE installs it. The
updater (`system/photobooth-update.py`, runs as root) refuses if the code was edited on the booth, checks
the new version compiles, switches to it (with only this booth's gifts; new ones in its person's
folder come with it), reinstalls the system files, and requires the app to start and stay up for 20 s; otherwise it switches
back to the old version. If power is cut mid-update, the next boot restores the old version. Photos,
settings and `~/my-designs` aren't touched.

`system/setup-updates.sh` points a booth at the repo (part of setting up a booth, above). Anyone can read
the repo but only its owner can change it, and the updater runs as root, so whoever controls the GitHub
account controls the booths: keep two-factor authentication on it. Never commit passwords or keys.

## Useful commands

shutdown Pi safely:

`sudo shutdown -h now`

copy photobooth.py to Pi:

`scp photobooth.py username@photobooth.local:~/photobooth/`

copy your own designs to a booth (strips; sheets go in `sheets/` or `portrait/`):

`scp mydesign.png mydesign.json admin@photobooth.local:~/my-designs/`

debug photobooth service (it runs on boot):

`journalctl -u photobooth.service -f`

stop the photobooth service (stop the guard timer too, or it restarts the app within a minute):

`sudo systemctl stop photobooth-guard.timer photobooth.service`

start it again:

`sudo systemctl start photobooth.service photobooth-guard.timer`

restart the photobooth service:

`sudo systemctl restart photobooth.service`
