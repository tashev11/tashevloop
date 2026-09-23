from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import __version__
from .capture import ingest_git, ingest_jsonl, run_test_command
from .engine import context_markdown, learn, suggest
from .models import Event, VALID_KINDS
from .store import Store


BRAND = "TashevLoop — learn from every AI-assisted development cycle"


def project_path(value: str | None) -> Path:
    return Path(value or ".").expanduser().resolve()


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tashevloop", description=BRAND)
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument("--project", help="project directory (default: current directory)")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="initialize local learning memory")

    rec = sub.add_parser("record", help="record an outcome, mistake, fix, success or decision")
    rec.add_argument("--kind", required=True, choices=sorted(VALID_KINDS))
    rec.add_argument("--title", required=True)
    rec.add_argument("--description", default="")
    rec.add_argument("--solution", default="")
    rec.add_argument("--tags", default="", help="comma-separated tags")
    rec.add_argument("--source", default="manual")

    sub.add_parser("learn", help="rebuild reusable lessons from recorded evidence")

    sug = sub.add_parser("suggest", help="suggest relevant learned guidance")
    sug.add_argument("query")
    sug.add_argument("--limit", type=int, default=5)
    sug.add_argument("--json", action="store_true")

    ctx = sub.add_parser("context", help="generate compact AI context from learned lessons")
    ctx.add_argument("query")
    ctx.add_argument("--limit", type=int, default=5)
    ctx.add_argument("--output", default="")

    git_cmd = sub.add_parser("ingest-git", help="learn from recent Git commits")
    git_cmd.add_argument("--limit", type=int, default=50)

    jsonl_cmd = sub.add_parser("ingest-jsonl", help="import external evidence from JSONL")
    jsonl_cmd.add_argument("path")

    test_cmd = sub.add_parser("test-run", help="run a test command and learn from its outcome")
    test_cmd.add_argument("test_command", nargs=argparse.REMAINDER)

    sub.add_parser("stats", help="show local memory statistics")
    sub.add_parser("doctor", help="check TashevLoop project state")
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    project = project_path(args.project)
    store = Store(project)

    if args.command == "init":
        store.init()
        print(f"✓ TashevLoop initialized: {store.home}")
        print("  by Rinat Tashev · github.com/tashev11/tashevloop")
        return 0

    if args.command == "record":
        tags = [x.strip() for x in args.tags.split(",") if x.strip()]
        event = Event(
            kind=args.kind,
            title=args.title,
            description=args.description,
            solution=args.solution,
            tags=tags,
            source=args.source,
        )
        event_id = store.add_event(event)
        print(f"✓ recorded event #{event_id}: {event.kind} · {event.title}")
        return 0

    if args.command == "learn":
        lessons = learn(project)
        print(f"✓ learned {len(lessons)} reusable lesson(s)")
        for item in lessons[:10]:
            print(f"  {item.confidence:.0%} · {item.title}")
        return 0

    if args.command == "suggest":
        tips = suggest(project, args.query, args.limit)
        if args.json:
            print(json.dumps(tips, ensure_ascii=False, indent=2))
        elif not tips:
            print("No relevant lessons yet. Record outcomes, then run tashevloop learn.")
        else:
            for i, item in enumerate(tips, 1):
                print(f"{i}. {item['title']} [{item['confidence']:.0%}]")
                print(f"   {item['guidance']}")
        return 0

    if args.command == "context":
        text = context_markdown(project, args.query, args.limit)
        if args.output:
            out = Path(args.output).expanduser()
            if not out.is_absolute():
                out = project / out
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(text, encoding="utf-8")
            print(f"✓ context written: {out}")
        else:
            print(text, end="")
        return 0

    if args.command == "ingest-git":
        result = ingest_git(project, args.limit)
        lessons = learn(project)
        print(
            f"✓ git evidence: {result['imported']} imported, "
            f"{result['skipped']} already known · {len(lessons)} lessons"
        )
        return 0

    if args.command == "ingest-jsonl":
        result = ingest_jsonl(project, Path(args.path))
        lessons = learn(project)
        print(
            f"✓ JSONL evidence: {result['imported']} imported, "
            f"{result['skipped']} already known · {len(lessons)} lessons"
        )
        return 0

    if args.command == "test-run":
        command = list(args.test_command)
        if command and command[0] == "--":
            command = command[1:]
        if not command:
            raise SystemExit("test-run requires a command after --")
        result = run_test_command(project, command)
        learn(project)
        state = "PASS" if result["passed"] else "FAIL"
        print(f"{state} · exit {result['returncode']} · event #{result['event_id']}")
        if result["output"]:
            print(result["output"])
        return 0 if result["passed"] else result["returncode"] or 1

    if args.command == "stats":
        print(json.dumps(store.stats(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "doctor":
        store.init()
        stats = store.stats()
        print(BRAND)
        print(f"project: {project}")
        print(f"database: {store.db_path}")
        print(f"events: {stats['events']} · lessons: {stats['lessons']}")
        print("status: OK")
        return 0

    return 2
