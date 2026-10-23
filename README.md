# amp_scan

Raspberry Pi 5 edge node for **authorized passive RF monitoring** with durable local telemetry and RFbeta integration.

## Architecture

- `amp-scan`: independent health, environment, and optional **aggregate-only** spectrum collector.
- `rfbeta-upstream.service`: supervised **official** RFbeta scanner (installed separately after reviewing its source and enrolling the node). No undocumented endpoint is assumed.
- SQLite WAL store with retention and an upload queue. Only aggregate operational telemetry is queued; unrelated Wi-Fi/BLE identities, addresses, packet contents, audio and IQ recordings are neither captured nor stored.
- `amp-scan.timer`: every-minute collection and local housekeeping. `amp-scan-report.timer`: periodic signed/authorized HTTPS reporting to **your own** optional telemetry endpoint; disable until provisioned.

## Quick start (Raspberry Pi OS 64-bit)

```bash
git clone https://github.com/pskeffington/amp_scan.git
cd amp_scan
sudo ./deploy/install.sh
sudoedit /etc/amp-scan/amp-scan.env
sudo systemctl enable --now amp-scan.timer
sudo systemctl enable --now amp-scan-report.timer
systemctl list-timers 'amp-scan*'
sudo journalctl -u amp-scan.service -n 50 --no-pager
```

No RF reception starts until a reviewed and explicitly configured upstream scanner is installed. Spectrum input is optional: set `SPECTRUM_COMMAND` to a vetted local program that writes newline-delimited CSV records in the format `frequency_hz,power_dbm` to stdout. The daemon parses **numeric frequency/power only**; every collection run has a runtime limit. Do not include identifiers or decoded communications in this stream.

## RFbeta integration

RFbeta and telemetry are distinct integrations. Follow the RFbeta site's documented Raspberry Pi enrollment and scanner deployment instructions, audit the downloaded script, configure its supported authentication and run it as `rfbeta-upstream.service` using the example unit. The node never guesses RFbeta URLs or sends experimental payloads to RFbeta. Use your own HTTPS `REPORT_URL` endpoint for the aggregate JSON operational reports if desired; `REPORT_TOKEN_FILE` stores its bearer token, readable only by the service account. RFbeta publication and classifications remain governed by RFbeta, not this collector.

## Configuration

See `deploy/amp-scan.env.example`. Set `NODE_ID` to a random non-identifying ID; `DB_PATH` should live on writable durable storage. Reporting is **off by default**; `REPORT_URL` must be HTTPS and explicitly configured. Each upload uses an event id for idempotent ingestion. For high volume, tune `SPECTRUM_COMMAND`, `MAX_SAMPLES_PER_RUN` and storage retention; never enable unlimited retention. Requests fail closed and remain queued offline.

## Development

```bash
python3 -m unittest discover -s tests -v
python3 -m amp_scan.cli --env deploy/amp-scan.env.example collect
python3 -m amp_scan.cli --env deploy/amp-scan.env.example status
```

## Security and privacy

Operate only within authorization and applicable radio/communications laws. No radio transmission; passive numerical summaries only. Avoid unique radio IDs, MACs, SSIDs, addresses, decrypted frames, message content, audio and precise positions. Local telemetry does not bypass RFbeta filtering or publication policy. The upload client enforces HTTPS, restricts redirects, bounds request size and requires a token. Review the upstream collector before activation. Systemd hardening limits service filesystem access.
