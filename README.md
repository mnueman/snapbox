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
strip shown (browse mode). Tap the strip itself to open DESIGNS (below) and see them all at once.

Tap a photo you've already taken (on the main screen, in its place on the strip) to take just that one
again: the booth shows it and asks first (KEEP IT / YES, RETAKE). The other photos stay; the next
press of the button fills that place, then the strip carries on where it was.

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
optionally `"stamp": "bl"`, `"tl"` or `"tr"` to move the date stamp to another corner, and
`"name": "Golf: On the Green"` and `"group": "ACTIVITIES"`: see DESIGNS below).

### DESIGNS: picking one on the booth

Tap the strip on the main screen. Every design is shown as a small picture, a page at a time (NEXT /
PREV, or swipe). Tap one to see it close up: drag the picture to see the rest of it, ZOOM IN for more
detail, ◀ ▶ (or a swipe on the keys) for the designs either side, the star to keep it in FAVOURITES, and
USE THIS to use it (BACK returns to the pictures). Photos already taken are kept, and only designs with
room for them are offered.

- ◀ ▶ at the top steps through the groups: ★ FAVOURITES, ALL DESIGNS, then BLANK, FUN, ACTIVITIES
  (golf, yoga, beach, hiking), HAWAII, WEDDING, COUPLE, COLLAGE, ARMY. Designs are in that order
  everywhere (swiping too), by number inside a group, so designs drawn as a set (the four neon
  ones, the four with party props) sit side by side.
- `frames/groups.json` sets the groups: their order, which name or gift folder goes in which
  (`"GOLF": "ACTIVITIES"`), and single shared designs by file (`"frame1": "BLANK"`); shared designs
  it doesn't mention are FUN. A design's own JSON can say `"group": "COLLAGE"`, which wins. A folder
  in `~/my-designs` (`~/my-designs/party/`) is its own group (PARTY) unless its designs say otherwise.
- Tap the star on a design to add it to (or take it out of) FAVOURITES. Favourites are kept in
  `settings.json`, so they stay through restarts and updates.
- The key at the bottom left switches between STRIPS, WIDE SHEETS and TALL SHEETS.
- After picking from a group, swiping on the main screen stays inside that group (so pick from
  FAVOURITES and swiping only goes through your favourites). Pick from ALL DESIGNS to swipe through
  everything again; a restart also goes back to everything.
- The small pictures are made once, in the background, and kept in `~/.cache/snapbox/thumbs/`.

| Folder | What | On which booths |
| --- | --- | --- |
| `frames/` | Shared designs | Every booth. New ones arrive with updates. |
| `gifts/<person>/<collection>/` | Made for one person, e.g. `gifts/Nick & Maddy Atkinson/wedding/`, `.../army/`, `.../hawaii/` | That person's booth, and the master booth |
| `~/my-designs/` (and any folders in it) | The booth owner's own designs | Only that booth. Not in git; updates never touch it. |

Designs are shown group by group (BLANK first; see DESIGNS below), in number order inside a group. The booth looks
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
- To try designs before they ship: `python3 system/test_designs.py --new` builds a finished strip or
  sheet from every design that isn't on `stable` yet, with the booth's own code and a plain colour for
  each photo, lays it out for the printer and fits it to the paper. It fails if a photo doesn't show
  through its opening, a see-through part is left outside the openings (it would print white), or
  the print is the wrong size. No arguments: every design on this booth, `~/my-designs` included.
  `--sheet out.jpg` saves a picture of all the prints.
- Generators: `python3 all_frames.py [numbers]` (strips 11-40), `python3 realistic.py` (strips 41-44) and
  `python3 sheet_frames.py` (sheets; designs in `sheets_landscape.py` / `sheets_portrait.py`, drawing kit
  in `sheet_kit.py`). `design_folders.py` decides which folder each generated design goes in.
- Fonts in `frames/fonts/` are Google Fonts; see `frames/fonts/FONTS.txt`.

## Settings menu

Tap the gear in the top-left corner of the screen. Use the ◀ ▶ arrows to change a setting (they go round: ▶ on the last choice goes back to the
first, usually OFF); changes save automatically (`settings.json`) and the camera and effects tabs show a live preview, cropped like the next
photo. Tap the preview (or FULL SCREEN PREVIEW) to make it as big as the screen allows, with one setting
underneath: tap a setting's name (or swipe) to pick which. Tap DONE or press the button to close.

- Camera tab: brightness, movement (sharper vs brighter), focus, lighting type, zoom, mirror preview.
  (The colour look is in the Effects tab.)
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
  time, LOOK (ORIGINAL, CLASSIC CAMERA: the whole main screen and countdown redrawn, with its own
  colours and type in the menus and review screen; landscape only, see `looks.py`), MENU COLOURS for the ORIGINAL look
  (CLASSIC, SUNSHINE, BUBBLEGUM, OCEAN, MINT, PARTY, MIDNIGHT), auto shut down when idle (off / 15 / 30 min / 1 / 2 / 4 h), UPDATES, Shut down (asks first; the red power key at the top of every menu tab does the same), and a reminder
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
the strip with another frame (swipe to try them, SAVE THIS FRAME to keep one). It offers every design
with room for the same number of photos, in any layout: its own layout first, then the others, so a
4-photo strip can become a 4-photo big sheet and back. Each strip's photos are kept
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
- The booth's WiFi ignores routers' "band steering" (being told to move to 5 GHz): the printer hotspot
  shares its radio and channel (`snapbox-wifi-nosteer`). If the WiFi chip still gets stuck (every scan
  fails), `snapbox-wifi-watchdog.timer` restarts the WiFi driver, then reboots if that didn't help (at
  most 3 times in a row). Log: `journalctl -t snapbox-wifi-nosteer -u snapbox-wifi-watchdog`.
- Settings and strips are written with fsync + rename, so a power cut can't leave them empty.
- An unexpected error in the main loop is logged and the booth carries on; 5 within a minute restarts the app.
- If the camera isn't detected the screen says "CAMERA NOT FOUND - check the cable" and keeps retrying.
- A damaged frame file is skipped instead of crashing; only the 4 most recent frames are kept in memory.
- Raw captures left by an interrupted strip are cleared at startup.
- Logs survive reboots (capped at 50 MB): `journalctl -u photobooth -b -1` shows the previous boot.

## Printer (Canon SELPHY CP1500)

The printer connects over WiFi to a network the booth makes itself, so it works anywhere, with or
without other WiFi. Once per booth, with internet:

    sudo sh ~/photobooth/system/setup-printer.sh

It installs the print system (CUPS; printing uses AirPrint, no driver), makes the booth's printer
network and prints its name and password at the end. They're kept in `/etc/snapbox/printer-wifi`
(edit it and run `sudo systemctl restart photobooth-hotspot` to change them) and shown in the app's
WIFI tab. Then, once per printer, on the SELPHY: Wi-Fi settings > Connection Settings > Other > Via
Wireless Router > Find wireless routers, pick the booth's network and type the password (the Menu
button opens the keyboard). The printer remembers it.

- The app finds the printer and adds it by itself. Top right of the main screen: a printer with a dot.
  Green: ready. Amber with a number: printing, and how many prints are waiting. Red: not connected, or
  it needs paper or ink (the screen says which along the bottom).
- "PRINT SENT" means the print is on its way; "PRINT FINISHED" shows when it has come out. The same
  print can't be sent again until it's out (a sheet takes about a minute), and at most 3 wait at once.
  If the printer goes away, waiting prints are cancelled so they don't come out later by surprise.
- The printer only does 2.4 GHz WiFi, and the Pi's WiFi chip runs both networks on one channel. So
  the booth keeps its own WiFi on 2.4 GHz; on a WiFi that is 5 GHz only it can't print, and says so.
  TURN WIFI OFF switches the printer network off too.
- Prints are fitted to where this printer really cuts (`PRINT_TRIM_MM`, `PRINT_SLANT`,
  `PRINT_BLEED_MM` in `photobooth.py`), measured with `system/print_calibration.py` (prints a ruler
  sheet) and `system/measure_calibration.py` (reads a photo of it); `system/print_fit_sim.py` checks
  every design shape against them.

### Photos from a phone

Tap the printer in the top right corner of the main screen (or WIFI tab > PRINT FROM A PHONE: HOW?)
for the three steps on screen: join the booth's printer network on the phone, open
`http://10.42.0.1:8080`. Pick a design (big pictures with their names; the arrows above a design
flip to the next one at full size, keeping the photos), tap each box to add a photo, drag to move
it and pinch to zoom, then SAVE (it appears in REVIEW like any strip, and CHANGE FRAME works on it)
or SAVE & PRINT. The Effects row above the buttons puts the booth's own effects on the photos:
colour look, date stamp, light leaks, red spots, dust and streaks. The booth draws them and sends
each photo back as it will look (`/api/preview`), so the phone shows what gets saved.
The booth builds and prints it exactly like its own strips. The page is `web/index.html`; it's only
reachable from the booth's own network.

## Command line on the booth's screen

For when there's no WiFi to reach the booth over SSH: BOOTH tab, last row, COMMAND LINE. It explains
and asks first, then stops the app and shows a text login on the booth's own screen, turned the way
the screen is mounted and in big letters (`system/snapbox-console.sh`; plug in a USB keyboard). Nothing
about it lasts: `sudo reboot`, or switching the booth off and on, brings the app back, and so does
5 minutes with nobody logged in. Needs `system/install.sh` run once since this was added.

## Boot splash

Shows the Snapshot name plate, with a shine sweeping across the chrome, instead of Linux's start-up
text. Once per booth, with internet, then restart:

    sudo sh ~/photobooth/system/setup-splash.sh

It installs Plymouth, makes the pictures for this booth's screen and its SCREEN setting
(`system/make_splash.py`; run the setup again after turning the screen round), quietens the start-up
(`/boot/firmware/cmdline.txt`, a copy is kept as `cmdline.txt.before-splash`) and keeps the splash up
until the app draws. `--undo` puts everything back. With it on, the booth's screen has no login
prompt (a keyboard's Alt+F2 still gives one; SSH is unaffected).

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
