#!/bin/sh
# BOOTH tab > COMMAND LINE: stops the photo booth app and puts a text login on the booth's own
# screen, for when there's no WiFi to reach the booth over (SSH). Needs a USB keyboard.
# Restarting the booth brings the app back: nothing here survives a restart. And if nobody has
# logged in after 5 minutes, the app is started again (someone tapped it by mistake, or there's
# no keyboard).
#   snapbox-console          switch to the command line (started by snapbox-console.service)
#   snapbox-console return   back to the app, unless someone is logged in at the screen
# Installed as /usr/local/sbin/snapbox-console by system/install.sh.
set -u
APP=/home/admin/photobooth

if [ "${1:-}" = "return" ]; then
    if who | grep -q ' tty1 '; then
        exit 0  # someone is using it: leave them to it
    fi
    echo "snapbox-console: nobody logged in; back to the photo booth"
    systemctl stop getty@tty1.service 2>/dev/null
    systemctl start photobooth.service photobooth-guard.timer
    exit 0
fi

echo "snapbox-console: switching the screen to the command line"
systemctl stop photobooth-guard.timer   # it would start the app again within a minute
systemctl stop photobooth.service
plymouth quit 2>/dev/null

# Turn the text the way the screen is mounted (the app turns its own pictures the same way).
size=$(cat /sys/class/graphics/fb0/virtual_size 2>/dev/null || echo 480,640)
rot=$(cat "$APP/screen_rotation.txt" 2>/dev/null || echo 0)
turn=0
if [ "${size#*,}" -gt "${size%,*}" ]; then   # a panel that is upright by nature, used on its side
    case "$rot" in 0) turn=1 ;; 180) turn=3 ;; -90) turn=2 ;; *) turn=0 ;; esac
else
    case "$rot" in 180) turn=2 ;; 90) turn=3 ;; -90) turn=1 ;; *) turn=0 ;; esac
fi
echo "$turn" > /sys/class/graphics/fbcon/rotate_all 2>/dev/null

chvt 1
# Big letters: the screen is 2.8 inches.
font=$(ls /usr/share/consolefonts/Lat15-TerminusBold32x16.psf.gz /usr/share/consolefonts/*TerminusBold32x16.psf.gz 2>/dev/null | head -n 1)
[ -n "$font" ] && setfont -C /dev/tty1 "$font" 2>/dev/null
{
    printf '\033[?25h\033[2J\033[H'   # cursor on, clear
    printf 'SNAPSHOT COMMAND LINE\n\n'
    printf 'Log in as: admin\n'
    printf 'Back to the photo booth:\n  sudo reboot\n'
    printf '(or switch it off and on)\n\n'
} > /dev/tty1
systemctl start getty@tty1.service
# The safety net.
systemctl stop snapbox-console-return.timer 2>/dev/null
systemd-run --quiet --unit=snapbox-console-return --on-active=300 /usr/local/sbin/snapbox-console return
exit 0
