#!/bin/sh
set -eu
[ "$(id -u)" -eq 0 ] || { echo "run as root" >&2; exit 1; }
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
id amp-scan >/dev/null 2>&1 || useradd --system --home /var/lib/amp-scan --shell /usr/sbin/nologin amp-scan
install -d -o amp-scan -g amp-scan -m 0750 /opt/amp-scan /var/lib/amp-scan
install -d -o root -g amp-scan -m 0750 /etc/amp-scan
cp -R "$ROOT/amp_scan" /opt/amp-scan/
chown -R root:root /opt/amp-scan/amp_scan
find /opt/amp-scan/amp_scan -type d -exec chmod 0755 {} \;
find /opt/amp-scan/amp_scan -type f -exec chmod 0644 {} \;
if [ ! -e /etc/amp-scan/amp-scan.env ]; then
  install -o root -g amp-scan -m 0640 "$ROOT/deploy/amp-scan.env.example" /etc/amp-scan/amp-scan.env
fi
for f in amp-scan.service amp-scan.timer amp-scan-report.service amp-scan-report.timer; do
  install -o root -g root -m 0644 "$ROOT/deploy/systemd/$f" "/etc/systemd/system/$f"
done
systemctl daemon-reload
echo "Installed. Edit /etc/amp-scan/amp-scan.env; then enable amp-scan.timer."
