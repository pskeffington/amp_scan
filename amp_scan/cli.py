"""Periodic aggregate-only local collector and store-forward reporter."""
from __future__ import annotations
import argparse
import csv
import hashlib
import hmac
import io
import json
import os
from pathlib import Path
import platform
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit
import uuid

MAX_PAYLOAD = 64 * 1024

def config(path):
    values = {}
    p = Path(path)
    if p.is_file():
        for line in p.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    values.update({k: v for k, v in os.environ.items() if k in {
        "NODE_ID", "DB_PATH", "REPORT_URL", "REPORT_TOKEN_FILE",
        "SPECTRUM_COMMAND", "MAX_SAMPLES_PER_RUN", "RETENTION_DAYS",
        "MAX_PENDING", "REPORT_BATCH_SIZE"}})
    return values

def integer(cfg, key, default, minimum, maximum):
    return max(minimum, min(maximum, int(cfg.get(key, default))))

def connect(cfg):
    db = Path(cfg.get("DB_PATH", "/var/lib/amp-scan/telemetry.db"))
    db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db, timeout=15)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=15000")
    con.executescript("""
    CREATE TABLE IF NOT EXISTS reports (
      id TEXT PRIMARY KEY, created_at INTEGER NOT NULL,
      payload TEXT NOT NULL, delivered_at INTEGER);
    CREATE INDEX IF NOT EXISTS reports_pending ON reports(delivered_at, created_at);
    """)
    return con

def read_temperature():
    p = Path("/sys/class/thermal/thermal_zone0/temp")
    try:
        return round(int(p.read_text().strip()) / 1000, 2)
    except (OSError, ValueError):
        return None

def spectrum(cfg):
    """Accept numeric-only spectrum observations from an operator-reviewed command."""
    cmd = cfg.get("SPECTRUM_COMMAND", "")
    if not cmd:
        return {"enabled": False}
    # No shell expansion. Operators must specify an executable with simple arguments.
    import shlex
    parts = shlex.split(cmd)
    if not parts or not Path(parts[0]).is_absolute():
        raise ValueError("SPECTRUM_COMMAND must start with an absolute executable path")
    max_samples = integer(cfg, "MAX_SAMPLES_PER_RUN", 10000, 1, 100000)
    proc = subprocess.run(parts, capture_output=True, timeout=35, check=True)
    if len(proc.stdout) > 4_000_000:
        raise ValueError("spectrum output exceeds 4MB cap")
    bins = {}
    count = 0
    for row in csv.reader(io.StringIO(proc.stdout.decode("utf-8", "strict"))):
        if len(row) != 2:
            continue
        try:
            hz, dbm = float(row[0]), float(row[1])
        except ValueError:
            continue
        if not (1e4 <= hz <= 6e10 and -200 <= dbm <= 100):
            continue
        band = int(hz // 1e6)
        item = bins.setdefault(band, [0, 0.0, -200.0])
        item[0] += 1
        item[1] += dbm
        item[2] = max(item[2], dbm)
        count += 1
        if count >= max_samples:
            break
    result = [
        {"mhz_bin": k, "count": v[0], "mean_dbm": round(v[1] / v[0], 2),
         "peak_dbm": round(v[2], 2)}
        for k, v in sorted(bins.items())
    ]
    return {"enabled": True, "sample_count": count, "bins": result[:1024],
            "truncated_bins": len(result) > 1024}

def collect(cfg):
    now = int(time.time())
    report = {"schema": "amp-scan.v1", "event_id": str(uuid.uuid4()),
              "node_id": cfg.get("NODE_ID", "unconfigured"),
              "timestamp": now, "host": {
                  "os": platform.system(), "machine": platform.machine(),
                  "temperature_c": read_temperature(), "uptime_seconds": None},
              "spectrum": spectrum(cfg)}
    try:
        report["host"]["uptime_seconds"] = round(float(
            Path("/proc/uptime").read_text().split()[0]), 1)
    except (OSError, ValueError, IndexError):
        pass
    payload = json.dumps(report, separators=(",", ":"), allow_nan=False)
    if len(payload.encode("utf-8")) > MAX_PAYLOAD:
        raise ValueError("report exceeds payload cap")
    with connect(cfg) as con:
        con.execute("INSERT INTO reports(id,created_at,payload) VALUES(?,?,?)",
                    (report["event_id"], now, payload))
        purge(con, cfg, now)
    return report

def purge(con, cfg, now=None):
    now = now or int(time.time())
    age = integer(cfg, "RETENTION_DAYS", 14, 1, 365) * 86400
    con.execute("DELETE FROM reports WHERE created_at < ?", (now - age,))
    # Bounded store even during prolonged outages. Preserve most recent records.
    limit = integer(cfg, "MAX_PENDING", 50000, 100, 1000000)
    con.execute("""DELETE FROM reports WHERE delivered_at IS NULL AND id IN (
      SELECT id FROM reports WHERE delivered_at IS NULL
      ORDER BY created_at DESC, id DESC LIMIT -1 OFFSET ?)""", (limit,))

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise urllib.error.HTTPError(args[0].full_url, 400,
                                     "redirect refused", {}, None)

def report(cfg):
    url = cfg.get("REPORT_URL", "").strip()
    if not url:
        return {"sent": 0, "disabled": True}
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("REPORT_URL must be HTTPS without embedded credentials")
    token_path = cfg.get("REPORT_TOKEN_FILE", "")
    if not token_path:
        raise ValueError("REPORT_TOKEN_FILE required when reporting")
    token = Path(token_path).read_text(encoding="utf-8").strip()
    if not token or "\n" in token or "\r" in token:
        raise ValueError("invalid report token")
    count = 0
    with connect(cfg) as con:
        rows = con.execute("SELECT id,payload FROM reports WHERE delivered_at IS NULL ORDER BY created_at,id LIMIT ?",
                           (integer(cfg, "REPORT_BATCH_SIZE", 50, 1, 200),)).fetchall()
        opener = urllib.request.build_opener(NoRedirect())
        for event_id, payload in rows:
            req = urllib.request.Request(url, data=payload.encode("utf-8"),
                headers={"Content-Type": "application/json",
                         "Authorization": "Bearer " + token,
                         "Idempotency-Key": event_id,
                         "User-Agent": "amp-scan/0.1"}, method="POST")
            try:
                with opener.open(req, timeout=12) as response:
                    if not (200 <= response.status < 300):
                        break
            except (urllib.error.URLError, TimeoutError, OSError):
                break
            con.execute("UPDATE reports SET delivered_at=? WHERE id=?",
                        (int(time.time()), event_id))
            con.commit()
            count += 1
        purge(con, cfg)
    return {"sent": count, "disabled": False}

def status(cfg):
    with connect(cfg) as con:
        pending, delivered = con.execute(
            "SELECT SUM(CASE WHEN delivered_at IS NULL THEN 1 ELSE 0 END),"
            "SUM(CASE WHEN delivered_at IS NOT NULL THEN 1 ELSE 0 END) FROM reports"
        ).fetchone()
    return {"pending": pending or 0, "delivered_retained": delivered or 0}

def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--env", default="/etc/amp-scan/amp-scan.env")
    p.add_argument("action", choices=("collect", "report", "status", "purge"))
    args = p.parse_args(argv)
    cfg = config(args.env)
    try:
        if args.action == "collect": out = collect(cfg)
        elif args.action == "report": out = report(cfg)
        elif args.action == "status": out = status(cfg)
        else:
            with connect(cfg) as con: purge(con, cfg)
            out = status(cfg)
        print(json.dumps(out, sort_keys=True))
        return 0
    except (OSError, ValueError, subprocess.SubprocessError, sqlite3.Error) as exc:
        print(json.dumps({"error": str(exc), "action": args.action}), file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
