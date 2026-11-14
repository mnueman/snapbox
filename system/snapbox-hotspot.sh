#!/bin/sh
# The booth's own WiFi network for the printer, on a second interface (uap0) next to the booth's
# normal WiFi (wlan0), so the booth keeps its internet. The SELPHY joins it once and remembers it.
# The Pi's WiFi chip can only run both on the same channel, so the hotspot follows wlan0's channel
# (channel 6 when wlan0 isn't connected). The SELPHY only does 2.4 GHz.
# Runs as root: at boot (photobooth-hotspot.service) and when wlan0 connects (NetworkManager
# dispatcher). Installed as /usr/local/sbin/snapbox-hotspot by system/setup-printer.sh.
set -u
STA=wlan0
AP=uap0
CON="SnapBox printer WiFi"
CONF=/etc/snapbox/printer-wifi  # SSID= and PASSWORD=, made once per booth by setup-printer.sh

[ -r "$CONF" ] || exit 0
SSID=$(sed -n 's/^SSID=//p' "$CONF")
PASSWORD=$(sed -n 's/^PASSWORD=//p' "$CONF")
[ -n "$SSID" ] && [ -n "$PASSWORD" ] || exit 0

# The boot service and the dispatcher can run at the same moment.
exec 9>/run/snapbox-hotspot.lock
flock -w 60 9 || exit 1

if ! iw dev "$AP" info >/dev/null 2>&1; then
    if ! iw dev "$STA" interface add "$AP" type __ap; then
        echo "snapbox-hotspot: could not add $AP" >&2
        exit 1
    fi
    # Its own MAC address: wlan0's with the "locally administered" bit flipped.
    mac=$(cat /sys/class/net/$STA/address)
    first=$(printf '%02x' $(( 0x${mac%%:*} ^ 2 )))
    ip link set "$AP" address "$first:${mac#*:}"
    # Give NetworkManager a moment to notice the new interface.
    sleep 2
fi

chan=6
freq=$(iw dev "$STA" link 2>/dev/null | awk '/freq:/ {print int($2)}')
if [ -n "$freq" ] && [ "$freq" -ge 2412 ] && [ "$freq" -le 2472 ]; then
    chan=$(( (freq - 2407) / 5 ))
elif [ -n "$freq" ]; then
    # wlan0 on 5 GHz: the hotspot would have to be on 5 GHz too, which the SELPHY can't see.
    # If the same network also has 2.4 GHz, keep this booth on 2.4 GHz for it from now on.
    con=$(nmcli -g GENERAL.CONNECTION device show "$STA")
    ssid=$(nmcli -g 802-11-wireless.ssid connection show "$con" 2>/dev/null)
    esc=$(printf '%s' "$ssid" | sed 's/[\\:]/\\&/g')
    if [ -n "$con" ] && nmcli -t -f SSID,CHAN device wifi list ifname "$STA" --rescan no \
            | grep -qxE "$(printf '%s' "$esc" | sed 's/[][\.*^$+?(){}|]/\\&/g'):([1-9]|1[0-3])"; then
        echo "snapbox-hotspot: moving $STA ($ssid) from $freq MHz to 2.4 GHz so the printer hotspot can run"
        nmcli connection modify "$con" 802-11-wireless.band bg
        # Reconnecting makes NetworkManager run this again (dispatcher), on the new channel.
        nmcli --wait 45 connection up "$con" >/dev/null 2>&1
        exit 0
    fi
    echo "snapbox-hotspot: $STA is on $freq MHz and $ssid has no 2.4 GHz; no printer hotspot on this network" >&2
    exit 0
fi

if ! nmcli -t -f NAME connection show | grep -qxF "$CON"; then
    nmcli connection add type wifi ifname "$AP" con-name "$CON" autoconnect yes ssid "$SSID" \
        802-11-wireless.mode ap 802-11-wireless.band bg 802-11-wireless.channel "$chan" \
        802-11-wireless.powersave 2 \
        wifi-sec.key-mgmt wpa-psk wifi-sec.proto rsn wifi-sec.pairwise ccmp wifi-sec.group ccmp \
        wifi-sec.psk "$PASSWORD" \
        ipv4.method shared ipv4.addresses 10.42.0.1/24 ipv6.method disabled >/dev/null || exit 1
fi

now=$(nmcli -g 802-11-wireless.channel connection show "$CON")
state=$(nmcli -g GENERAL.STATE connection show "$CON" 2>/dev/null)
if [ "$now" != "$chan" ]; then
    echo "snapbox-hotspot: moving to channel $chan (was $now)"
    nmcli connection modify "$CON" 802-11-wireless.channel "$chan"
    state=""
fi
if [ "$state" != "activated" ]; then
    nmcli --wait 30 connection up "$CON" >/dev/null || { echo "snapbox-hotspot: could not start" >&2; exit 1; }
fi
echo "snapbox-hotspot: $SSID up on channel $chan"
