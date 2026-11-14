#!/bin/sh
# WiFi watchdog. The Pi's WiFi chip runs the booth's WiFi (wlan0) and the printer hotspot (uap0) at
# once. If a router tells wlan0 to move to another channel (e.g. "band steering" to 5 GHz) while the
# hotspot is busy, the chip can get stuck: every scan fails with -52 and nothing reconnects until a
# reboot (seen 2026-11-14). This notices that and restarts the WiFi driver; if that doesn't help,
# it reboots.
# Runs every minute (snapbox-wifi-watchdog.timer). While wlan0 is connected it only reads one file.
# Installed as /usr/local/sbin/snapbox-wifi-watchdog by system/install.sh. Log:
# journalctl -u snapbox-wifi-watchdog
set -u
STA=wlan0
RUN=/run/snapbox-wifi-watchdog            # this boot only
REBOOTS=/var/lib/snapbox-wifi-watchdog-reboots  # survives the reboot, so it can't reboot forever
MAX_REBOOTS=3

if [ "$(cat /sys/class/net/$STA/operstate 2>/dev/null)" = up ]; then
    # Healthy. Forget earlier trouble (only touches files if there are any).
    [ -e "$RUN" ] && rm -rf "$RUN"
    [ -e "$REBOOTS" ] && rm -f "$REBOOTS"
    exit 0
fi

now=$(cut -d. -f1 /proc/uptime)
# Just restarted the driver: give it 5 minutes to reconnect before judging again.
if [ -r "$RUN/reset" ] && [ $((now - $(cat "$RUN/reset"))) -lt 300 ]; then
    exit 0
fi

# Not connected. That's normal with no known network around; stuck is when scans keep failing.
fails=$(journalctl -q -o cat -u wpa_supplicant --since=-2min 2>/dev/null | grep -c 'SCAN-FAILED ret=-52')
mkdir -p "$RUN"
if [ "$fails" -lt 10 ]; then
    rm -f "$RUN/suspect"
    exit 0
fi
# Act only when it's still stuck a minute later.
if [ ! -e "$RUN/suspect" ]; then
    : > "$RUN/suspect"
    exit 0
fi
rm -f "$RUN/suspect"

reboot_booth() {
    n=$(cat "$REBOOTS" 2>/dev/null || echo 0)
    if [ "$n" -ge "$MAX_REBOOTS" ]; then
        echo "snapbox-wifi-watchdog: still stuck after $n reboots; only restarting the driver from now on"
        return 1
    fi
    echo $((n + 1)) > "$REBOOTS"
    sync
    echo "snapbox-wifi-watchdog: restarting the WiFi driver didn't help; rebooting"
    systemctl reboot
    exit 0
}

# Already restarted the driver and it never reconnected since: reboot (that's what fixed it before).
if [ -e "$RUN/reset" ] && [ "$now" -gt 600 ]; then
    reboot_booth
fi

echo "snapbox-wifi-watchdog: WiFi chip stuck ($fails failed scans in 2 minutes); restarting the WiFi driver"
echo "$now" > "$RUN/reset"
# The printer hotspot (uap0) goes away with the driver; the hotspot service makes it again.
if ! modprobe -r brcmfmac_cyw brcmfmac; then
    echo "snapbox-wifi-watchdog: could not unload the WiFi driver" >&2
    reboot_booth
fi
sleep 2
modprobe brcmfmac
# wlan0 connecting brings the hotspot back by itself (NetworkManager dispatcher); this covers
# the case where there's no known WiFi around.
sleep 15
systemctl restart --no-block photobooth-hotspot.service
