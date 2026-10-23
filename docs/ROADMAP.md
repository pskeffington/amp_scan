# Phased delivery gates

## G0 - Repository bootstrap
- [x] Python package, configuration, bounded SQLite WAL, installation and tests.
- [x] Separate official RFbeta scanner service template from custom telemetry service.

## G1 - Pi 5 lab validation
- [ ] Verify Raspberry Pi OS 64-bit image and service user.
- [ ] Execute unit tests on device, boot and reboot tests.
- [ ] Verify USB SDR power draw and under-voltage recovery.

## G2 - RFbeta enrollment
- [ ] Review official RFbeta documentation and scanner source.
- [ ] Provision credentials from the RFbeta operator; configure official uploader exactly as documented.
- [ ] End-to-end test against RFbeta's supported onboarding flow and confirm acceptance.

## G3 - High-volume numeric spectrum sampling
- [ ] Select compatible receive-only SDR and reviewed spectrum command.
- [ ] Confirm usable frequencies, calibration, antennas, and duty cycle.
- [ ] 24-hour throughput and thermal testing, tuned frequency-bin aggregation.
- [ ] Verify no identifiers/content entered local spectrum streams.

## G4 - Reporting and resilience
- [ ] Provision private HTTPS telemetry collector with per-node token and idempotency.
- [ ] Test network outage, storage saturation, retry behavior and recovery.
- [ ] Establish loss/latency/error budgets, dashboard and alert thresholds.

## G5 - Security and release
- [ ] Configure secure boot/device provisioning as supported.
- [ ] Sign/review releases, rotate credentials, add updates and dependency audits.
- [ ] Validate legal and RFbeta privacy constraints.

**Status**: initial software scaffold delivered. Not RFbeta-enrolled, not field-tested; no claim of active auto-upload.
