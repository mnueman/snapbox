#!/bin/sh
# Installs the photobooth start-on-boot service, its guard timer and the shutdown permission.
# Run with sudo.
set -e
cd "$(dirname "$0")"
visudo -cf photobooth-shutdown.sudoers
install -m 0440 photobooth-shutdown.sudoers /etc/sudoers.d/photobooth-shutdown
# Lets the app scan for and join WiFi networks from the touchscreen menu.
install -m 0644 photobooth-wifi.rules /etc/polkit-1/rules.d/50-photobooth-wifi.rules
# Lets the app start the updater (and nothing else) from the touchscreen.
install -m 0644 photobooth-update.rules /etc/polkit-1/rules.d/50-photobooth-update.rules
install -m 0644 photobooth.service photobooth-guard.service photobooth-guard.timer \
    photobooth-update.service photobooth-update-recover.service /etc/systemd/system/
# Restarts the WiFi chip if it gets stuck (see snapbox-wifi-watchdog.sh).
install -m 0755 snapbox-wifi-watchdog.sh /usr/local/sbin/snapbox-wifi-watchdog
install -m 0644 snapbox-wifi-watchdog.service snapbox-wifi-watchdog.timer /etc/systemd/system/
# Makes the booth's WiFi ignore routers' band steering (see snapbox-wifi-nosteer.sh).
install -m 0755 snapbox-wifi-nosteer.sh /usr/local/sbin/snapbox-wifi-nosteer
install -m 0644 snapbox-wifi-nosteer.service /etc/systemd/system/
install -m 0755 snapbox-wifi-nosteer.dispatcher /etc/NetworkManager/dispatcher.d/40-snapbox-wifi-nosteer
# Booths with a printer (set up once with setup-printer.sh): keep the printer network's scripts
# up to date too. They take effect the next time the network starts; it isn't restarted here.
if [ -e /etc/snapbox/printer-wifi ]; then
    install -m 0755 snapbox-hotspot.sh /usr/local/sbin/snapbox-hotspot
    install -m 0755 snapbox-hotspot.dispatcher /etc/NetworkManager/dispatcher.d/50-snapbox-hotspot
    install -m 0644 photobooth-hotspot.service /etc/systemd/system/
fi
install -d /etc/systemd/journald.conf.d
install -m 0644 photobooth-journald.conf /etc/systemd/journald.conf.d/50-photobooth.conf
systemctl restart systemd-journald
# Start writing to disk now; otherwise logs stay in memory until the next boot.
journalctl --flush
systemctl daemon-reload
systemctl enable photobooth.service photobooth-guard.timer photobooth-update-recover.service
systemctl enable --now snapbox-wifi-watchdog.timer
systemctl enable snapbox-wifi-nosteer.service
# Right away too (only reconnects WiFi if it isn't set yet).
/usr/local/sbin/snapbox-wifi-nosteer up || true
# Automatic package-list updates write to the SD card at random times; not needed on a booth.
systemctl disable --now apt-daily.timer apt-daily-upgrade.timer || true
# Flush to the SD card now: if power is cut before this, the new files can end up empty.
sync
echo "Installed. It will start on next boot, or now with: sudo systemctl start photobooth.service photobooth-guard.timer"
