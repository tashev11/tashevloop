from __future__ import annotations

import json
import os
import shlex
import subprocess
import time
from pathlib import Path

from .autopilot import run_once as run_autopilot_once
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


def cycle(
    project: Path,
    test_command: str = "",
    force: bool = False,
    autopilot: bool = False,
    max_budget_usd: float = 0.75,
) -> dict:
    project = project.resolve()
    store = Store(project)
    store.init()
    previous = _read_status(store)
    head_before = git_head(project)
    changed = force or head_before != previous.get("head")

    imported = {"imported": 0, "skipped": 0}
    test_result = None
    autopilot_result = None

    if changed:
        imported = ingest_git(project, limit=100)
        if test_command.strip():
            test_result = run_test_command(project, shlex.split(test_command))
        lessons = learn(project)
        proposals = build_improvement_plan(project)

        if autopilot and proposals:
            autopilot_result = run_autopilot_once(
                project,
                test_command=test_command,
                max_budget_usd=max_budget_usd,
                merge_verified=True,
            )
            lessons = store.lessons()
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

    head_after = git_head(project)
    payload = {
        "running": True,
        "pid": os.getpid(),
        "last_cycle_at": utc_now(),
        "head": head_after,
        "changed": changed,
        "git_imported": imported["imported"],
        "git_skipped": imported["skipped"],
        "lessons": len(lessons),
        "proposals": len(proposals),
        "test_passed": None if test_result is None else bool(test_result["passed"]),
        "autopilot": autopilot,
        "autopilot_status": None if autopilot_result is None else autopilot_result.get("status"),
    }
    if not changed and previous.get("error"):
        # Nothing ran since the failed cycle; keep its error visible.
        payload["error"] = previous["error"]
    _write_status(store, payload)
    return payload


def watch(
    project: Path,
    interval: int = 60,
    test_command: str = "",
    autopilot: bool = False,
    max_budget_usd: float = 0.75,
) -> None:
    interval = max(5, int(interval))
    while True:
        try:
            cycle(
                project,
                test_command=test_command,
                autopilot=autopilot,
                max_budget_usd=max_budget_usd,
            )
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            store = Store(project)
            _write_status(store, {
                "running": True,
                "pid": os.getpid(),
                "last_cycle_at": utc_now(),
                # Remember the HEAD this cycle saw. Without it the next cycle
                # counts as a change and repeats the failing work every interval.
                "head": git_head(project),
                "error": str(exc),
                "autopilot": autopilot,
            })
        time.sleep(interval)
