"""Pi platform health; no unique host or network identifiers recorded."""
import os
from pathlib import Path
import platform
import re
import subprocess

def read(path):
    try:
        return Path(path).read_text(encoding="ascii").strip()
    except (OSError, UnicodeError):
        return None

def temperature():
    try:
        return round(int(read("/sys/class/thermal/thermal_zone0/temp")) / 1000, 2)
    except (TypeError, ValueError):
        return None

def undervoltage():
    exe = "/usr/bin/vcgencmd"
    if not os.path.isfile(exe):
        return None
    try:
        proc = subprocess.run([exe, "get_throttled"], timeout=2, check=True,
                              capture_output=True, text=True)
        m = re.fullmatch(r"throttled=0x([0-9a-fA-F]+)", proc.stdout.strip())
        return bool(int(m.group(1), 16) & 1) if m else None
    except (OSError, subprocess.SubprocessError):
        return None

def host_health(cfg):
    uptime = None
    memory = None
    free_disk = None
    try:
        uptime = round(float((read("/proc/uptime") or "").split()[0]), 1)
    except (ValueError, IndexError):
        pass
    m = re.search(r"^MemAvailable:\s+(\d+)\s+kB",
                  read("/proc/meminfo") or "", re.MULTILINE)
    if m:
        memory = int(m.group(1))
    db_dir = Path(cfg.get("DB_PATH", "/var/lib/amp-scan/telemetry.db")).parent
    try:
        stat = os.statvfs(db_dir)
        free_disk = round(stat.f_bavail * stat.f_frsize / (1024 ** 2), 1)
    except OSError:
        pass
    try:
        load = [round(v, 2) for v in os.getloadavg()]
    except OSError:
        load = None
    return {"os": platform.system(), "machine": platform.machine(),
            "temperature_c": temperature(), "uptime_seconds": uptime,
            "mem_available_kib": memory, "disk_free_mib": free_disk,
            "load_1_5_15": load, "undervoltage_now": undervoltage()}
