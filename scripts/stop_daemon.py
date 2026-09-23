from __future__ import annotations

import json
import os
import signal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOME = ROOT / ".tashevloop"
STATUS = HOME / "daemon-status.json"
PIDFILE = HOME / "daemon.pid"

if not PIDFILE.exists():
    print("TashevLoop daemon is not running")
    raise SystemExit(0)

try:
    pid = int(PIDFILE.read_text().strip())
except ValueError:
    PIDFILE.unlink(missing_ok=True)
    print("Removed invalid daemon pid file")
    raise SystemExit(0)

try:
    os.kill(pid, signal.SIGTERM)
    print(f"Stopped TashevLoop daemon: pid {pid}")
except ProcessLookupError:
    print(f"Daemon process {pid} was already stopped")

PIDFILE.unlink(missing_ok=True)
if STATUS.exists():
    try:
        data = json.loads(STATUS.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    data["running"] = False
    STATUS.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
