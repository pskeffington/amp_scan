# amp_scan

Raspberry Pi 5 edge node for **authorized passive RF monitoring** with bounded, durable local aggregate telemetry. Integrates alongside the **official** RFbeta scanner; it does not invent an RFbeta endpoint.

## Components

- `amp_scan.cli`: periodic Pi health, numerical spectrum aggregates and SQLite WAL queue.
- `amp_scan.spectrum`: native `rtl_power` CSV adapter and optional numeric `frequency_hz,power_dbm` program adapter. No SSIDs, MACs, audio, IQ data, decoded traffic or user IDs are ingested.
- `amp_scan.health`: uptime, thermal, memory, storage, load and Pi undervoltage indicators.
- Separate RFbeta upstream scanner is documented, but not installed or enabled automatically.
- Optional operator-owned HTTPS telemetry endpoint receives idempotent event JSON. This is **not** the RFbeta upload API.

## Raspberry Pi 5 installation (Raspberry Pi OS 64-bit)

```bash
sudo apt update
sudo apt install -y python3 rtl-sdr
git clone https://github.com/pskeffington/amp_scan.git
cd amp_scan
# Until PR #1 is merged: git switch feature/pi5-rfbeta-node
python3 -m unittest discover -s tests -v
sudo ./deploy/install.sh
sudoedit /etc/amp-scan/amp-scan.env
sudo systemctl enable --now amp-scan.timer
sudo systemctl enable --now amp-scan-report.timer
systemctl list-timers 'amp-scan*'
sudo journalctl -u amp-scan.service -n 40 --no-pager
```

Edit the environment file: choose a random `NODE_ID`, set `SPECTRUM_MODE=rtl_power` after a supported receive-only dongle is available, and configure `RTL_POWER_RANGES`. `RTL_POWER_RANGES` accepts up to eight semicolon-separated ranges (e.g. `88M:108M:125k`). Start with a narrow, known broadcast allocation; tune ranges for the licensed/relevant signals and actual tuner. `rtl_power` only acquires FFT power estimates, not content.

Confirm hardware access locally with `rtl_test -t` while the collector is stopped. If USB access is denied, review your dongle vendor/product IDs from `lsusb` and install a **device-specific** udev permission rule mapping only that receiver to group `amp-scan`; do not run the collector as root.

The sample timer starts 30 seconds after boot and runs after the previous collection finishes. The report timer runs every 2 minutes. No uploads occur until `REPORT_URL` is set to your separate HTTPS receiver and a service-readable `REPORT_TOKEN_FILE` exists.

## RFbeta official uploader

RFbeta's published Raspberry Pi instructions are at https://map.sparrowmap.com/rfbeta. They provide a scanner from `https://map.sparrowmap.com/rf/rf_scan.py`, node enrollment at `/api/enroll`, and a `--post --node --token` workflow for Wi-Fi surveillance-device filtering and reviewed submissions.

**Do not run third-party scripts automatically without reviewing the source.** The upstream published CLI takes a token argument; process command lines can be visible to other local users. Keep the RFbeta uploader separate until an approved credential handling and upgrade process is established. Our numerical spectrum data is not an RFbeta sighting and must never be posted to its endpoint using an invented payload.

## Developer validation

```bash
python3 -m unittest discover -s tests -v
DB_PATH=/tmp/amp_scan_dev.db python3 -m amp_scan.cli --env deploy/amp-scan.env.example collect
DB_PATH=/tmp/amp_scan_dev.db python3 -m amp_scan.cli --env deploy/amp-scan.env.example status
```

Continuous integration covers Python 3.11/3.12 without SDR hardware. Field gates require a physical Pi 5, SDR permissions, throughput/thermals, offline queue behavior, and RFbeta acceptance confirmation.

## Data discipline

The collector stores **numbers and hardware health only**, with storage retention and per-upload size limits. No unknown Wi-Fi/BLE device identities or decoded communications are collected. Receivers are passive and transmit no RF signal. Run only with proper authorization and follow local spectrum monitoring laws.
