# Phased delivery gates

## G0 - Initial foundation
- [x] Python package, systemd deployment, SQLite WAL queue, retention, HTTPS reporting.
- [x] Separate third-party RFbeta upstream from private numerical telemetry.

## G1 - Pi 5 field readiness
- [x] Native `rtl_power` CSV power FFT input with configurable frequency ranges.
- [x] Numeric-only privacy boundary, non-finite input handling, bounded report spectrum bins.
- [x] Host temperature, uptime, memory, disk, CPU load and undervoltage diagnostics.
- [x] Fix installer executable bit, add Python 3.11/3.12 CI and simulated-hardware tests.
- [ ] CI must pass on GitHub.
- [ ] Pi 5 64-bit OS and USB SDR device-permissions validation.
- [ ] 24-hour thermal, throughput and reboot tests.

## G2 - RFbeta enrollment
- [ ] Review publisher-provided `rf_scan.py` source and its credential handling.
- [ ] Provision official node ID/token and launch supported upstream scanner under a restricted account.
- [ ] Verify RFbeta submission delivery and review-queue acceptance.

## G3 - High-throughput data pipeline
- [ ] Tune FFT sweep schedules for connected receiver models, filters and front-end limits.
- [ ] Introduce local longer-duration aggregate summaries and audit metrics.
- [ ] Confirm there are no stored MACs, SSIDs, audio, IQ or decoded traffic.

## G4 - Resilient reporting
- [ ] Provision operator-owned HTTPS ingestion endpoint with per-node auth and idempotency.
- [ ] Test offline backlog, backoff/rate-limits, storage saturation, sustained writes and replay.
- [ ] Measure packet loss, delivery latency, and health alarms.

## G5 - Release
- [ ] Pin and verify upstream dependencies; rotate and protect secrets.
- [ ] Document lifecycle / unattended upgrade policy and rollback.
- [ ] Validate privacy/legal boundary and independent reviewer sign-off.

Status: Software G1 prototype committed; no claim of Pi 5 hardware validation or RFbeta end-to-end integration.
