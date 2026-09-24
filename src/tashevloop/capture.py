from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from .models import Event
from .store import Store
from .text import strip_trailers


# Whole words only: "debug", "prefix" and "fixtures" are not fixes, and
# "неисправность" (a malfunction) is not a repair.
FIX_PATTERN = re.compile(
    r"\b(?:fix(?:e[sd]|ing)?|bug|bug-?fix(?:es)?|hotfix(?:es)?|repair(?:s|ed|ing)?)\b"
    r"|\bисправ\w*|\bпочин\w*",
    re.IGNORECASE,
)
REVERT_PATTERN = re.compile(
    r"\b(?:revert(?:s|ed|ing)?|roll[- ]?back)\b|\bоткат\w*",
    re.IGNORECASE,
)


def _classify_commit(subject: str) -> str:
    if REVERT_PATTERN.search(subject):
        return "warning"
    if FIX_PATTERN.search(subject):
        return "fix"
    return "success"


def ingest_git(project: Path, limit: int = 50) -> dict:
    project = project.resolve()
    store = Store(project)
    proc = subprocess.run(
        [
            "git",
            "log",
            f"-{max(1, limit)}",
            "--format=%H%x1f%s%x1f%b%x1e",
        ],
        cwd=project,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "git log failed")

    imported = 0
    skipped = 0
    for raw in proc.stdout.split("\x1e"):
        raw = raw.strip()
        if not raw:
            continue
        parts = raw.split("\x1f")
        if len(parts) < 2:
            continue
        sha = parts[0].strip()
        subject = parts[1].strip()
        body = strip_trailers(parts[2]) if len(parts) > 2 else ""
        source = f"git:{sha}"
        if store.has_source(source):
            skipped += 1
            continue

        kind = _classify_commit(subject)
        solution = ""
        if kind == "fix":
            solution = body or f"Preserve the verified fix represented by commit {sha[:12]}: {subject}"
        elif kind == "success":
            solution = body or f"This change reached Git history successfully: {subject}"

        store.add_event(
            Event(
                kind=kind,
                title=subject or sha[:12],
                description=body,
                solution=solution,
                tags=["git", "commit"],
                source=source,
            )
        )
        imported += 1

    return {"imported": imported, "skipped": skipped}


def run_test_command(project: Path, command: list[str]) -> dict:
    if not command:
        raise ValueError("test command is required")

    project = project.resolve()
    proc = subprocess.run(
        command,
        cwd=project,
        text=True,
        capture_output=True,
        check=False,
    )
    output = ((proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")).strip()
    output = output[-4000:]
    rendered = " ".join(command)
    passed = proc.returncode == 0

    event = Event(
        kind="success" if passed else "mistake",
        title=f"Test command: {rendered}",
        description=output,
        solution=(
            f"Use '{rendered}' as a verified project check before similar changes."
            if passed
            else ""
        ),
        tags=["tests", "verification"],
        source="test-run",
    )
    event_id = Store(project).add_event(event)
    return {
        "passed": passed,
        "returncode": proc.returncode,
        "event_id": event_id,
        "output": output,
    }


def ingest_jsonl(project: Path, source_file: Path) -> dict:
    project = project.resolve()
    source_file = source_file.expanduser().resolve()
    store = Store(project)
    imported = 0
    skipped = 0

    with source_file.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            data = json.loads(line)
            source = f"jsonl:{source_file.name}:{line_no}"
            if store.has_source(source):
                skipped += 1
                continue
            store.add_event(
                Event(
                    kind=data["kind"],
                    title=data["title"],
                    description=data.get("description", ""),
                    solution=data.get("solution", ""),
                    tags=list(data.get("tags", [])),
                    source=source,
                )
            )
            imported += 1

    return {"imported": imported, "skipped": skipped}
