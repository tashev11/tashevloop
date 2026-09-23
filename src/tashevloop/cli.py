from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from . import __version__
from .autopilot import run_once as run_autopilot_once
from .capture import ingest_git, ingest_jsonl, run_test_command
from .daemon import cycle, watch
from .engine import context_markdown, learn, suggest
from .evolution import build_improvement_plan
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

    sub.add_parser("evolve", help="analyze accumulated evidence and propose next improvements")

    watch_cmd = sub.add_parser("watch", help="continuously learn when the repository changes")
    watch_cmd.add_argument("--interval", type=int, default=60, help="poll interval in seconds")
    watch_cmd.add_argument("--test-command", default="", help="test command to run after changes (required with --autopilot)")
    watch_cmd.add_argument("--autopilot", action="store_true", help="allow gated Claude Code self-improvement for high-priority proposals")
    watch_cmd.add_argument("--max-budget-usd", type=float, default=0.75, help="per-attempt Claude budget cap")
    watch_cmd.add_argument("--once", action="store_true", help="run one learning cycle and exit")

    auto_cmd = sub.add_parser("autopilot", help="attempt one gated high-priority self-improvement")
    auto_cmd.add_argument("--test-command", required=True, help="verification command required before merge")
    auto_cmd.add_argument("--max-budget-usd", type=float, default=0.75)
    auto_cmd.add_argument("--no-merge", action="store_true", help="leave a verified branch instead of merging")

    sub.add_parser("stats", help="show local memory statistics")
    sub.add_parser("doctor", help="check TashevLoop project state")
    return p


def _doctor_checks(project: Path, store: Store) -> list[tuple[bool, str]]:
    inside = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=project,
        text=True,
        capture_output=True,
        check=False,
    )
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        return [(False, "not a Git repository: ingest-git, watch and autopilot need one")]
    checks = [(True, "Git repository")]
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", str(store.db_path)],
        cwd=project,
        check=False,
    ).returncode == 0
    checks.append((
        ignored,
        ".tashevloop/ is ignored by Git" if ignored
        else ".tashevloop/ is not ignored by Git: memory.db could be committed",
    ))
    return checks


def main(argv: list[str] | None = None) -> int:
    cli = parser()
    args = cli.parse_args(argv)
    if args.command == "watch" and args.autopilot and not args.test_command.strip():
        cli.error("watch --autopilot requires --test-command: autopilot merges only verified changes")
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

    if args.command == "evolve":
        proposals = build_improvement_plan(project)
        if not proposals:
            print("✓ no high-signal improvement proposals yet")
        else:
            print(f"✓ generated {len(proposals)} improvement proposal(s)")
            for item in proposals[:10]:
                print(f"  [{item['priority']}] {item['title']}: {item['action']}")
        print(f"  report: {store.home / 'IMPROVEMENTS.md'}")
        return 0

    if args.command == "watch":
        if args.once:
            result = cycle(
                project,
                test_command=args.test_command,
                force=True,
                autopilot=args.autopilot,
                max_budget_usd=args.max_budget_usd,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        print(f"✓ TashevLoop watch started · interval {max(5, args.interval)}s")
        if args.test_command:
            print(f"  verification: {args.test_command}")
        if args.autopilot:
            print(f"  gated autopilot: ON · budget cap ${args.max_budget_usd:.2f}/attempt")
        watch(
            project,
            interval=args.interval,
            test_command=args.test_command,
            autopilot=args.autopilot,
            max_budget_usd=args.max_budget_usd,
        )
        return 0

    if args.command == "autopilot":
        result = run_autopilot_once(
            project,
            test_command=args.test_command,
            max_budget_usd=args.max_budget_usd,
            merge_verified=not args.no_merge,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("status") not in {"verification-failed", "merge-failed", "reverted"} else 1

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
        checks = _doctor_checks(project, store)
        for ok, message in checks:
            print(f"{'✓' if ok else '!'} {message}")
        warnings = sum(1 for ok, _ in checks if not ok)
        print("status: OK" if not warnings else f"status: {warnings} warning(s)")
        return 0

    return 2
