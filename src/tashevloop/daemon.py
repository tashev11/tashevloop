from __future__ import annotations

import json
import os
import shlex
import subprocess
import time
from pathlib import Path

from .capture import ingest_git, run_test_command
from .engine import learn
from .evolution import build_improvement_plan
from .models import utc_now
from .store import Store


def git_head(project: Path) -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=project,
        text=True,
        capture_output=True,
        check=False,
    )
    return proc.stdout.strip() if proc.returncode == 0 else ""


def _read_status(store: Store) -> dict:
    path = store.home / "daemon-status.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_status(store: Store, payload: dict) -> None:
    store.home.mkdir(parents=True, exist_ok=True)
    (store.home / "daemon-status.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def cycle(project: Path, test_command: str = "", force: bool = False) -> dict:
    project = project.resolve()
    store = Store(project)
    store.init()
    previous = _read_status(store)
    head = git_head(project)
    changed = force or head != previous.get("head")

    imported = {"imported": 0, "skipped": 0}
    test_result = None
    if changed:
        imported = ingest_git(project, limit=100)
        if test_command.strip():
            test_result = run_test_command(project, shlex.split(test_command))
        lessons = learn(project)
        proposals = build_improvement_plan(project)
    else:
        lessons = store.lessons()
        proposals = []
        improvement_path = store.home / "next_tasks.json"
        if improvement_path.exists():
            try:
                proposals = json.loads(improvement_path.read_text(encoding="utf-8"))
            except Exception:
                proposals = []

    payload = {
        "running": True,
        "pid": os.getpid(),
        "last_cycle_at": utc_now(),
        "head": head,
        "changed": changed,
        "git_imported": imported["imported"],
        "git_skipped": imported["skipped"],
        "lessons": len(lessons),
        "proposals": len(proposals),
        "test_passed": None if test_result is None else bool(test_result["passed"]),
    }
    _write_status(store, payload)
    return payload


def watch(project: Path, interval: int = 60, test_command: str = "") -> None:
    interval = max(5, int(interval))
    while True:
        try:
            cycle(project, test_command=test_command)
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            store = Store(project)
            _write_status(store, {
                "running": True,
                "last_cycle_at": utc_now(),
                "error": str(exc),
            })
        time.sleep(interval)
