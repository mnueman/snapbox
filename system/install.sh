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
install -d /etc/systemd/journald.conf.d
install -m 0644 photobooth-journald.conf /etc/systemd/journald.conf.d/50-photobooth.conf
systemctl restart systemd-journald
# Start writing to disk now; otherwise logs stay in memory until the next boot.
journalctl --flush
systemctl daemon-reload
systemctl enable photobooth.service photobooth-guard.timer photobooth-update-recover.service
# Automatic package-list updates write to the SD card at random times; not needed on a booth.
systemctl disable --now apt-daily.timer apt-daily-upgrade.timer || true
# Flush to the SD card now: if power is cut before this, the new files can end up empty.
sync
echo "Installed. It will start on next boot, or now with: sudo systemctl start photobooth.service photobooth-guard.timer"
