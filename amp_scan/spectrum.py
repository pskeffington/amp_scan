"""Aggregate passive numerical RF power without retaining identifiers or content."""
import csv
import io
import math
import os
import re
import shlex
import subprocess

MAX_BYTES = 4_000_000
RANGE = re.compile(r"^[0-9]+(?:\.[0-9]+)?[kKmMgG]?:[0-9]+(?:\.[0-9]+)?[kKmMgG]?:[0-9]+(?:\.[0-9]+)?[kKmMgG]?$")

def bounded_int(cfg, key, default, lo, hi):
    return max(lo, min(hi, int(cfg.get(key, default))))

def _hz(value):
    scales = {"k": 1e3, "m": 1e6, "g": 1e9}
    return float(value[:-1]) * scales[value[-1].lower()] if value[-1].lower() in scales else float(value)

def checked_ranges(value):
    ranges = [v.strip() for v in value.split(";")]
    if not 1 <= len(ranges) <= 8:
        raise ValueError("expect one to eight rtl_power ranges")
    for item in ranges:
        if not RANGE.fullmatch(item):
            raise ValueError("invalid rtl_power range")
        low, high, step = [_hz(v) for v in item.split(":")]
        if not (24e6 <= low < high <= 2e9 and 1000 <= step <= 2.8e6):
            raise ValueError("rtl_power range out of bounds")
    return ranges

def observations(payload, backend):
    """Read rtl_power native CSV (six metadata columns) or two-column numeric CSV."""
    for row in csv.reader(io.StringIO(payload.decode("utf-8", "strict"))):
        if backend == "rtl_power":
            if len(row) < 7:
                continue
            try:
                low, high, step = (float(v.strip()) for v in row[2:5])
                sample_count = int(row[5].strip())
            except (ValueError, TypeError):
                continue
            if not (math.isfinite(low) and math.isfinite(high) and
                    math.isfinite(step) and 24e6 <= low < high <= 2e9 and
                    1 <= step <= 2.8e6 and sample_count >= 0):
                continue
            pairs = ((low + (i + 0.5) * step, val)
                     for i, val in enumerate(row[6:])
                     if low + (i + 0.5) * step <= high + step / 2)
        else:
            if len(row) != 2:
                continue
            pairs = [(row[0], row[1])]
        for hz_text, db_text in pairs:
            try:
                hz, power = float(hz_text), float(db_text)
            except (ValueError, TypeError):
                continue
            if (math.isfinite(hz) and math.isfinite(power) and
                    1e4 <= hz <= 6e10 and -200 <= power <= 100):
                yield hz, power

def summarize(pairs, cfg, backend):
    width = bounded_int(cfg, "SPECTRUM_BIN_HZ", 1_000_000, 100_000, 10_000_000)
    max_samples = bounded_int(cfg, "MAX_SAMPLES_PER_RUN", 10000, 1, 100000)
    max_bins = bounded_int(cfg, "MAX_REPORT_BINS", 256, 8, 512)
    data = {}
    count = 0
    for hz, power in pairs:
        key = int(hz // width)
        record = data.setdefault(key, [0, 0., -200.])
        record[0] += 1
        record[1] += power
        record[2] = max(record[2], power)
        count += 1
        if count >= max_samples:
            break
    ordered = sorted(data.items())
    stride = max(1, math.ceil(len(ordered) / max_bins))
    results = []
    for start in range(0, len(ordered), stride):
        segment = ordered[start:start+stride]
        n = sum(row[1][0] for row in segment)
        results.append({
            "frequency_start_hz": segment[0][0] * width,
            "frequency_end_hz": (segment[-1][0] + 1) * width,
            "count": n,
            "mean_dbm": round(sum(row[1][1] for row in segment) / n, 2),
            "peak_dbm": round(max(row[1][2] for row in segment), 2)})
    return {"enabled": True, "backend": backend, "sample_count": count,
            "base_bin_hz": width, "reported_bins": len(results),
            "coarsened": stride > 1, "bins": results}

def spectrum(cfg, runner=subprocess.run):
    mode = cfg.get("SPECTRUM_MODE", "").lower().strip()
    if not mode:
        mode = "custom" if cfg.get("SPECTRUM_COMMAND", "").strip() else "off"
    if mode == "off":
        return {"enabled": False}
    if mode == "rtl_power":
        exe = cfg.get("RTL_POWER_PATH", "/usr/bin/rtl_power")
        if not os.path.isabs(exe):
            raise ValueError("RTL_POWER_PATH must be absolute")
        command = [exe]
        for item in checked_ranges(cfg.get("RTL_POWER_RANGES", "88M:108M:125k")):
            command += ["-f", item]
        interval = bounded_int(cfg, "RTL_POWER_INTERVAL_SECONDS", 10, 1, 30)
        command += ["-i", str(interval), "-1"]
        backend = "rtl_power"
    elif mode == "custom":
        command = shlex.split(cfg.get("SPECTRUM_COMMAND", ""))
        if not command or not os.path.isabs(command[0]):
            raise ValueError("SPECTRUM_COMMAND must start with an absolute executable")
        backend = "numeric"
    else:
        raise ValueError("SPECTRUM_MODE must be off, rtl_power or custom")
    timeout = bounded_int(cfg, "SWEEP_TIMEOUT_SECONDS", 40, 2, 180)
    result = runner(command, timeout=timeout, capture_output=True, check=True)
    if len(result.stdout) > MAX_BYTES:
        raise ValueError("spectrum output exceeds 4MB")
    return summarize(observations(result.stdout, backend), cfg, mode)
