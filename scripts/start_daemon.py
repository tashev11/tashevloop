from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOME = ROOT / ".tashevloop"
STATUS = HOME / "daemon-status.json"
PIDFILE = HOME / "daemon.pid"
LOG = HOME / "daemon.log"


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


HOME.mkdir(parents=True, exist_ok=True)
if PIDFILE.exists():
    try:
        current = int(PIDFILE.read_text().strip())
    except ValueError:
        current = 0
    if current and alive(current):
        print(f"TashevLoop daemon already running: pid {current}")
        raise SystemExit(0)

log = LOG.open("a", encoding="utf-8")
proc = subprocess.Popen(
    [sys.executable, str(ROOT / "scripts" / "daemon_runner.py")],
    cwd=ROOT,
    stdout=log,
    stderr=subprocess.STDOUT,
    stdin=subprocess.DEVNULL,
    start_new_session=True,
)
PIDFILE.write_text(str(proc.pid) + "\n", encoding="utf-8")
print(f"TashevLoop daemon started: pid {proc.pid}")
print(f"log: {LOG}")
