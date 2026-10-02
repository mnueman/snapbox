#!/bin/sh
# Installs the photobooth start-on-boot service, its guard timer and the shutdown permission.
# Run with sudo.
set -e
cd "$(dirname "$0")"
visudo -cf photobooth-shutdown.sudoers
install -m 0440 photobooth-shutdown.sudoers /etc/sudoers.d/photobooth-shutdown
# Lets the app scan for and join WiFi networks from the touchscreen menu.
install -m 0644 photobooth-wifi.rules /etc/polkit-1/rules.d/50-photobooth-wifi.rules
install -m 0644 photobooth.service photobooth-guard.service photobooth-guard.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable photobooth.service photobooth-guard.timer
# Automatic package-list updates write to the SD card at random times; not needed on a booth.
systemctl disable --now apt-daily.timer apt-daily-upgrade.timer || true
# Flush to the SD card now: if power is cut before this, the new files can end up empty.
sync
echo "Installed. It will start on next boot, or now with: sudo systemctl start photobooth.service photobooth-guard.timer"
