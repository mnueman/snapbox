#!/bin/sh
# WiFi watchdog. The Pi's WiFi chip runs the booth's WiFi (wlan0) and the printer hotspot (uap0) at
# once. If a router tells wlan0 to move to another channel (e.g. "band steering" to 5 GHz) while the
# hotspot is busy, the chip can get stuck: every scan fails with -52 and nothing reconnects until a
# reboot (seen 2026-11-14). This notices that and restarts the WiFi driver; if that doesn't help,
# it reboots.
# It has to be quick: on 2026-11-24 the router moved wlan0 to 5 GHz 20 seconds after boot, the
# booth had no WiFi, and its owner rebooted it by hand after a minute and a half, long before
# the old once-a-minute check (first run at 2 minutes, acting on the second look) got there.
# Runs every 20 seconds (snapbox-wifi-watchdog.timer): stuck WiFi is back in about a minute. While wlan0 is connected it only reads one file.
# Installed as /usr/local/sbin/snapbox-wifi-watchdog by system/install.sh. Log:
# journalctl -u snapbox-wifi-watchdog
set -u
STA=wlan0
RUN=/run/snapbox-wifi-watchdog            # this boot only
REBOOTS=/var/lib/snapbox-wifi-watchdog-reboots  # survives the reboot, so it can't reboot forever
MAX_REBOOTS=3

# The printer network (booths set up with setup-printer.sh): if it should be up and isn't, start
# it again. Nothing else does that when there's no known WiFi around to reconnect to.
if [ -r /etc/snapbox/printer-wifi ] && [ "$(cat /run/snapbox/hotspot-status 2>/dev/null)" != 5ghz ] \
        && [ "$(cut -d. -f1 /proc/uptime)" -gt 90 ] \
        && ! iw dev uap0 info 2>/dev/null | grep -q 'type AP' \
        && [ "$(systemctl show -p SubState --value photobooth-hotspot.service)" != start ]; then
    echo "snapbox-wifi-watchdog: the printer network is down; starting it again"
    systemctl restart --no-block photobooth-hotspot.service
fi

if [ "$(cat /sys/class/net/$STA/operstate 2>/dev/null)" = up ]; then
    # Healthy. Forget earlier trouble (only touches files if there are any).
    [ -e "$RUN" ] && rm -rf "$RUN"
    [ -e "$REBOOTS" ] && rm -f "$REBOOTS"
    exit 0
fi

now=$(cut -d. -f1 /proc/uptime)
# Just restarted the driver: give it 2 minutes to reconnect before judging again.
if [ -r "$RUN/reset" ] && [ $((now - $(cat "$RUN/reset"))) -lt 120 ]; then
    exit 0
fi

# Not connected. That's normal with no known network around; stuck is when scans keep failing.
# A stuck chip fails a scan every second, so 10 in the last 40 seconds is unmistakable.
fails=$(journalctl -q -o cat -u wpa_supplicant --since=-40s 2>/dev/null | grep -c 'SCAN-FAILED ret=-52')
mkdir -p "$RUN"
if [ "$fails" -lt 10 ]; then
    rm -f "$RUN/suspect"
    exit 0
fi
# Never in the middle of a print: restarting the driver drops the printer, and a reboot loses the
# sheet. Look again next time.
if lpstat -o 2>/dev/null | grep -q .; then
    echo "snapbox-wifi-watchdog: WiFi chip looks stuck, but a print is going; waiting"
    exit 0
fi
# Act only when it's still stuck at the next look, 20 seconds later.
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

echo "snapbox-wifi-watchdog: WiFi chip stuck ($fails failed scans in 40 seconds); restarting the WiFi driver"
echo "$now" > "$RUN/reset"
# The printer hotspot (uap0) goes away with the driver; the hotspot service makes it again.
if ! modprobe -r brcmfmac_cyw brcmfmac; then
    echo "snapbox-wifi-watchdog: could not unload the WiFi driver" >&2
    reboot_booth
fi
sleep 2
modprobe brcmfmac
# The new wlan0 must ignore band steering again, before it connects.
systemctl restart --no-block snapbox-wifi-nosteer.service
# wlan0 connecting brings the hotspot back by itself (NetworkManager dispatcher); this covers
# the case where there's no known WiFi around.
sleep 15
systemctl restart --no-block photobooth-hotspot.service
