"""Periodic aggregate-only local collector and store-forward reporter."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit
import uuid
from .spectrum import spectrum
from .health import host_health

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

def collect(cfg):
    now = int(time.time())
    try:
        reading = spectrum(cfg)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        # Health reports continue if the SDR is disconnected; stderr is never stored.
        reading = {"enabled": True, "error": type(exc).__name__}
    report = {"schema": "amp-scan.v1", "event_id": str(uuid.uuid4()),
              "node_id": cfg.get("NODE_ID", "unconfigured"),
              "timestamp": now, "host": host_health(cfg),
              "spectrum": reading}
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
