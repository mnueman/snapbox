#!/bin/sh
# One-time printer setup for the Canon SELPHY CP1500 over WiFi. Run with sudo, with internet.
# The booth gets its own WiFi network (SnapBox-<hostname>) for the printer, next to its normal WiFi;
# the printer joins it once from its own menu and remembers it. Printing uses AirPrint: no driver.
set -e
cd "$(dirname "$0")"
apt-get update
# No "recommends": they pull in cups-browsed (see below), ipp-usb and colour-management extras.
# avahi-utils finds the printer on the network.
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    cups cups-client avahi-utils iw dnsmasq-base
# cups-browsed adds every printer on whatever WiFi the booth joins as a print queue.
apt-get purge -y cups-browsed || true
# Lets the app add the printer by itself (no sudo needed then).
usermod -aG lpadmin "${SUDO_USER:-admin}"
systemctl enable --now cups

# This booth's printer network: made once, kept forever (the printer remembers it).
# Letters and numbers that are easy to tell apart on the printer's screen keyboard.
install -d -m 0755 /etc/snapbox
if [ ! -s /etc/snapbox/printer-wifi ]; then
    pw=$(tr -dc 'abcdefghjkmnpqrstuvwxyz23456789' </dev/urandom | head -c 8)
    printf 'SSID=SnapBox-%s\nPASSWORD=%s\n' "$(hostname)" "$pw" > /etc/snapbox/printer-wifi
fi
# The app shows it on screen, so it must be readable.
chmod 0644 /etc/snapbox/printer-wifi
install -m 0755 snapbox-hotspot.sh /usr/local/sbin/snapbox-hotspot
install -m 0755 snapbox-hotspot.dispatcher /etc/NetworkManager/dispatcher.d/50-snapbox-hotspot
install -m 0644 photobooth-hotspot.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable photobooth-hotspot.service
/usr/local/sbin/snapbox-hotspot || true
sync
# The app only learns it may add printers, and that it has a printer network, when it starts.
systemctl try-restart photobooth.service || true

echo
iw dev | grep -E "Interface|channel|type"
nmcli -f DEVICE,STATE,CONNECTION device status
echo
echo "Printer WiFi for this booth:"
cat /etc/snapbox/printer-wifi
