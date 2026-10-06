# photobooth

## Hardware (Raspberry Pi 5 build)

- Camera: IMX708 on CAM/DISP 0
- Screen: 800x480 DSI touchscreen on CAM/DISP 1, mounted portrait
- Shutter button: GPIO 26 to GND (GPIO 16 is reserved for the X1200)
- Optional Geekworm X1200 UPS: MAX17040 fuel gauge at I2C 0x36, power-loss detect on GPIO 6.
  Battery % shows top-right; warns at 20%, saves and shuts down at 5% / 3.20 V while on battery.
  If the X1200 isn't detected, the battery display is hidden.

## Setup

`/boot/firmware/config.txt`:

```
camera_auto_detect=0
dtparam=i2c_arm=on
dtoverlay=imx708,cam0
```

Load `i2c-dev` at boot (`echo i2c-dev | sudo tee /etc/modules-load.d/i2c-dev.conf`), then:

`sudo apt install --no-install-recommends python3-picamera2 python3-pygame python3-pil python3-numpy python3-gpiozero python3-lgpio python3-smbus2 libegl-mesa0 libegl1 libgles2 i2c-tools`

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

## Settings menu

Tap the gear in the top-left corner of the screen. Use the ◀ ▶ arrows to change a setting; changes save
automatically (`settings.json`) and the camera and effects tabs show a live preview, cropped like the next
photo. Tap the preview (or FULL SCREEN PREVIEW) to make it as big as the screen allows, with one setting
underneath: tap a setting's name (or swipe) to pick which. Tap DONE or press the button to close.

- Camera tab: brightness, colour look, movement (sharper vs brighter), focus, lighting type, zoom, mirror preview.
  Each lighting type locks the white balance to one colour temperature (warm bulbs 2900 K, indoor 3600 K,
  office 4300 K, sunny 5600 K, cloudy/shade 7000 K); AUTO lets the camera decide.
  Colour looks: normal, vivid, warm, cool, soft & dreamy, black & white, noir, sepia, film (warm), film (B&W),
  film: portrait, film: golden, film: cool green, instant photo, 70s faded, cross-processed. The live preview
  shows the look; film looks add grain and a vignette.
- Effects tab: vintage add-ons that go on every photo with any frame, and stack: DATE STAMP (today's date in
  orange seven-segment digits, like a 90s film camera), LIGHT LEAKS (warm glow from an edge), RED LIGHT SPOTS
  (red orbs and a strobe ring) and LIGHT STREAKS & DUST. Each strip gets its own random leaks and spots.
- Booth tab: screen orientation, screen-off time, countdown before each photo (off / 3 / 5 / 10 s), review auto-keep
  time, auto shut down when idle (off / 15 / 30 min / 1 / 2 / 4 h), UPDATES, Shut down (tap twice), and a reminder
  of the button presses.
- Auto shut down works on battery and on mains or a power bank. A minute before, the screen wakes and counts down;
  any tap or press keeps the booth on. A half-finished strip is saved first.
- WiFi tab: shows the connected network and IP, scans for nearby networks (one entry per name, strongest
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
swipe to another and tap PRINT THESE 2. DELETE asks for a second tap within 4 seconds before it
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

Booths install the `stable` branch from the private GitHub repo (mnueman/snapbox). Day-to-day work goes on
`pi5-photobooth`; booths only see a change once `stable` moves.

Publish an update (after trying it on your own booth):

`git push origin pi5-photobooth:stable`

Each booth checks 90 s after starting and every 6 hours. When it finds something new and is idle it shows
"Your creator has gifted you with an update!"; BOOTH tab > UPDATES > INSTALL UPDATE installs it. The
updater (`system/photobooth-update.py`, runs as root) refuses if the code was edited on the booth, checks
the new version compiles, switches to it, reinstalls the system files, and requires the app to start and
stay up for 20 s; otherwise it switches back to the old version. If power is cut mid-update, the next boot
restores the old version. Photos and settings aren't touched.

Set up a new booth for updates (once per booth, as admin):

1. `~/photobooth/system/setup-updates.sh` (makes the booth's own read-only key and prints it)
2. On GitHub: repo Settings > Deploy keys > Add deploy key, paste it, leave "Allow write access" unticked.

To cut a booth off, delete its key there. The updater runs as root, so whoever controls the GitHub repo
controls the booths: keep two-factor authentication on the GitHub account.

## Useful commands

shutdown Pi safely:

`sudo shutdown -h now`

copy photobooth.py to Pi:

`scp photobooth.py username@photobooth.local:~/photobooth/`

copy frames and jsons to Pi:

`scp frames/* username@photobooth.local:~/photobooth/frames/`

debug photobooth service (it runs on boot):

`journalctl -u photobooth.service -f`

stop the photobooth service (stop the guard timer too, or it restarts the app within a minute):

`sudo systemctl stop photobooth-guard.timer photobooth.service`

start it again:

`sudo systemctl start photobooth.service photobooth-guard.timer`

restart the photobooth service:

`sudo systemctl restart photobooth.service`
