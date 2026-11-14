#!/bin/sh
# Stops routers from moving the booth's WiFi (wlan0) to another band or access point ("band
# steering": 802.11v BSS Transition Management). The printer hotspot shares wlan0's radio and
# channel, and the printer only does 2.4 GHz; on 2026-11-14 a router moved wlan0 to 5 GHz while the
# hotspot was restarting and the WiFi chip got stuck until a reboot (see snapbox-wifi-watchdog.sh).
# With disable_btm the Pi tells the router it doesn't take such requests. The router reads that when
# the Pi connects, so it has to be set before wlan0 connects:
#   snapbox-wifi-nosteer wait  - at boot and after a driver restart: set it as soon as wpa_supplicant
#                                has wlan0, which is a few seconds before NetworkManager connects it
#   snapbox-wifi-nosteer up    - NetworkManager dispatcher, wlan0 connected: if that was missed,
#                                set it and reconnect once (about 2 s)
# Installed as /usr/local/sbin/snapbox-wifi-nosteer by system/install.sh.
set -u
W="wpa_cli -p /run/wpa_supplicant -i wlan0"
say() { logger -t snapbox-wifi-nosteer "$*"; }

case "${1:-}" in
wait)
    i=0
    v=$($W get disable_btm 2>/dev/null)
    while [ "$v" != 0 ] && [ "$v" != 1 ] && [ $i -lt 300 ]; do  # up to 60 s
        sleep 0.2
        i=$((i + 1))
        v=$($W get disable_btm 2>/dev/null)
    done
    [ "$v" = 0 ] && $W set disable_btm 1 >/dev/null && say "wlan0 set to ignore band steering"
    ;;
up)
    [ "$($W get disable_btm 2>/dev/null)" = 0 ] || exit 0
    $W set disable_btm 1 >/dev/null || exit 0
    say "wlan0 connected before it was set to ignore band steering; reconnecting it once"
    $W reassociate >/dev/null
    # Back on the network before the hotspot dispatcher (50-snapbox-hotspot) runs.
    sleep 1
    i=0
    until $W status 2>/dev/null | grep -qx 'wpa_state=COMPLETED' || [ $i -ge 50 ]; do
        sleep 0.2
        i=$((i + 1))
    done
    ;;
esac
exit 0
