#!/bin/sh
# Boot splash: shows the Snapshot name plate (with a moving shine) instead of Linux's start-up text.
# Run with sudo, with internet (it installs Plymouth, the boot-splash program). Needs a reboot.
#
#   sudo sh ~/photobooth/system/setup-splash.sh           install it (safe to run again)
#   sudo sh ~/photobooth/system/setup-splash.sh --flip    the logo was upside down: turn it over
#   sudo sh ~/photobooth/system/setup-splash.sh --undo    back to the normal text start-up
#
# What it changes, all undone by --undo:
#   /boot/firmware/cmdline.txt   quiet start-up, messages off the screen (a copy is kept beside it)
#   /boot/firmware/config.txt    no rainbow square at power-on
#   Plymouth theme "snapbox"     made for this screen by system/make_splash.py
#   plymouth-quit                switched off: the app ends the splash itself, the moment it is
#                                ready to draw (snapbox-splash-quit.service; after 90 s regardless)
#   getty@tty1                   no login prompt on the booth's screen (Alt+F2 on a keyboard still
#                                gives one; SSH is unaffected)
set -e
cd "$(dirname "$0")"
CMDLINE=/boot/firmware/cmdline.txt
CONFIG=/boot/firmware/config.txt
THEME=/usr/share/plymouth/themes/snapbox
QUIT_D=/etc/systemd/system/plymouth-quit.service.d
OWNER="${SUDO_USER:-admin}"

if [ "$1" = "--undo" ]; then
    [ -f "$CMDLINE.before-splash" ] && cp "$CMDLINE.before-splash" "$CMDLINE"
    sed -i '/^disable_splash=1  # snapbox$/d' "$CONFIG"
    rm -rf "$QUIT_D"
    systemctl unmask plymouth-quit.service plymouth-quit-wait.service 2>/dev/null || true
    systemctl disable snapbox-splash-quit.timer 2>/dev/null || true
    rm -f /etc/systemd/system/snapbox-splash-quit.service /etc/systemd/system/snapbox-splash-quit.timer \
        /etc/polkit-1/rules.d/50-photobooth-splash.rules
    systemctl daemon-reload
    systemctl enable getty@tty1.service 2>/dev/null || true
    if command -v plymouth-set-default-theme >/dev/null; then
        plymouth-set-default-theme -R details 2>/dev/null || true
    fi
    rm -rf "$THEME"
    sync
    echo "Boot splash removed. Restart the booth to see the normal start-up again."
    exit 0
fi

if ! command -v plymouth-set-default-theme >/dev/null || [ ! -e /usr/share/plymouth/themes/script ]; then
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends plymouth plymouth-themes
fi

# Which way up: Plymouth and the app don't agree on this panel, so the splash gets a half turn
# more than the app's screens. --flip changes that for a booth where it comes out upside down.
install -d -m 0755 /etc/snapbox
[ -s /etc/snapbox/splash-turn ] || echo 180 > /etc/snapbox/splash-turn
if [ "$1" = "--flip" ]; then
    if [ "$(cat /etc/snapbox/splash-turn)" = 180 ]; then echo 0 > /etc/snapbox/splash-turn; else echo 180 > /etc/snapbox/splash-turn; fi
fi
extra=$(cat /etc/snapbox/splash-turn)

# The pictures, turned for this booth's screen.
size=$(cat /sys/class/graphics/fb0/virtual_size 2>/dev/null || echo 480,640)
pw=${size%,*}
ph=${size#*,}
rot=$(cat ../screen_rotation.txt 2>/dev/null || echo 0)
tmp=$(mktemp -d)
chown "$OWNER" "$tmp"
sudo -u "$OWNER" python3 make_splash.py "$tmp" "$pw" "$ph" "$rot" "$extra"
install -d "$THEME"
install -m 0644 "$tmp"/bg.png "$tmp"/mask.png "$tmp"/shine.png "$tmp"/glow.png \
    "$tmp"/snapbox.plymouth "$tmp"/snapbox.script "$THEME"/
rm -rf "$tmp"

# Quiet start-up: no text, no cursor, no logos; kernel messages go to a screen nobody sees (tty3).
[ -f "$CMDLINE.before-splash" ] || cp "$CMDLINE" "$CMDLINE.before-splash"
line=$(head -n 1 "$CMDLINE" | sed 's/console=tty1/console=tty3/')
for word in quiet splash loglevel=3 vt.global_cursor_default=0 logo.nologo plymouth.ignore-serial-consoles; do
    case " $line " in
        *" $word "*) ;;
        *) line="$line $word" ;;
    esac
done
printf '%s\n' "$line" > "$CMDLINE.new"
# One line, still naming the root disk: otherwise leave the old file alone.
if [ "$(wc -l < "$CMDLINE.new")" = 1 ] && grep -q 'root=' "$CMDLINE.new"; then
    mv "$CMDLINE.new" "$CMDLINE"
else
    rm -f "$CMDLINE.new"
    echo "Could not update $CMDLINE safely; left it as it was." >&2
    exit 1
fi
grep -q '^disable_splash=1' "$CONFIG" || echo 'disable_splash=1  # snapbox' >> "$CONFIG"

# Keep the splash up until the app is ready to draw: the system no longer ends it part-way
# through start-up (that left some seconds of black); the app asks for it (photobooth.py:
# end_boot_splash), and a timer does after 90 s if the app never gets there. No login prompt over it.
rm -rf "$QUIT_D"
install -m 0644 snapbox-splash-quit.service snapbox-splash-quit.timer /etc/systemd/system/
install -m 0644 photobooth-splash.rules /etc/polkit-1/rules.d/50-photobooth-splash.rules
systemctl daemon-reload
systemctl mask plymouth-quit.service plymouth-quit-wait.service
systemctl enable snapbox-splash-quit.timer
systemctl disable getty@tty1.service 2>/dev/null || true

# Use the theme, and put it in the start-up image so it shows as early as possible.
plymouth-set-default-theme -R snapbox
sync
echo
echo "Boot splash installed. Restart the booth to see it:  sudo reboot"
echo "To go back:  sudo sh ~/photobooth/system/setup-splash.sh --undo"
