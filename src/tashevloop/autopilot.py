from __future__ import annotations

import json
import re
import shlex
import subprocess
import time
from pathlib import Path
from typing import Callable

from .engine import context_markdown, learn
from .evolution import build_improvement_plan
from .models import Event, utc_now
from .store import Store


AgentRunner = Callable[[Path, str, float], dict]

# The agent may only read and edit files inside its worktree. Shell access
# would hand it the network and the whole machine, and the outer gate runs
# verification anyway, so Bash is disabled together with the web tools.
AGENT_ALLOWED_TOOLS = "Read,Edit,Write,Glob,Grep"
AGENT_DISALLOWED_TOOLS = "Bash,WebFetch,WebSearch"

# A candidate that touches these could weaken the gate that judges it.
PROTECTED_FILES = frozenset({
    "LICENSE",
    "NOTICE",
    "scripts/run_tests.py",
    "scripts/daemon_runner.py",
    "scripts/start_daemon.py",
    "scripts/stop_daemon.py",
})
PROTECTED_PREFIXES = (".github/",)
TESTS_DIR = "tests/"
# New test modules are welcome; these two change how discovery runs the suite.
TEST_HOOK_NAMES = frozenset({"__init__.py", "conftest.py"})

# Outcomes that leave a verified commit on its branch for the developer.
KEEP_BRANCH = frozenset({"verified-branch", "main-moved", "main-dirty", "merge-failed"})


def _git(project: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=project,
        text=True,
        capture_output=True,
        check=check,
    )


def _head(project: Path) -> str:
    return _git(project, "rev-parse", "HEAD").stdout.strip()


def _slug(text: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return value[:42] or "improvement"


def _state_path(project: Path) -> Path:
    return Store(project).home / "autopilot-state.json"


def _read_state(project: Path) -> dict:
    path = _state_path(project)
    if not path.exists():
        return {"attempts": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"attempts": {}}
    if not isinstance(data, dict):
        return {"attempts": {}}
    data.setdefault("attempts", {})
    return data


def _write_state(project: Path, state: dict) -> None:
    path = _state_path(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def select_candidate(project: Path) -> dict | None:
    proposals = build_improvement_plan(project)
    state = _read_state(project)
    attempts = state.get("attempts", {})
    for proposal in proposals:
        if proposal.get("priority") != "high":
            continue
        signature = str(proposal.get("signature", ""))
        evidence_count = int(proposal.get("evidence_count", 0))
        previous = attempts.get(signature)
        if previous and int(previous.get("evidence_count", -1)) >= evidence_count:
            continue
        return proposal
    return None


def default_claude_runner(worktree: Path, prompt: str, max_budget_usd: float) -> dict:
    command = [
        "npm", "exec", "--global", "--", "claude",
        "-p", prompt,
        "--permission-mode", "acceptEdits",
        "--permission-prompts", "none",
        "--allowedTools", AGENT_ALLOWED_TOOLS,
        "--disallowedTools", AGENT_DISALLOWED_TOOLS,
        "--max-budget-usd", str(max(0.05, max_budget_usd)),
        "--output-format", "json",
        "--no-session-persistence",
    ]
    proc = subprocess.run(
        command,
        cwd=worktree,
        text=True,
        capture_output=True,
        check=False,
        timeout=1800,
    )
    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout[-12000:],
        "stderr": proc.stderr[-12000:],
    }


def _verification(project: Path, test_command: str) -> dict:
    if not test_command.strip():
        return {"passed": False, "returncode": None, "output": "No verification command configured."}
    proc = subprocess.run(
        shlex.split(test_command),
        cwd=project,
        text=True,
        capture_output=True,
        check=False,
    )
    output = ((proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")).strip()
    return {
        "passed": proc.returncode == 0,
        "returncode": proc.returncode,
        "output": output[-6000:],
    }


def _staged_changes(worktree: Path, base: str) -> list[tuple[str, str]]:
    """Return (kind, path) for every staged change against base.

    kind is "A", "M" or "D". A rename reports its old path as deleted and its
    new path as added, so renaming an existing test counts as removing it.
    """
    raw = _git(worktree, "diff", "--cached", "--name-status", "-z", "-M", base).stdout
    fields = raw.split("\0")
    changes: list[tuple[str, str]] = []
    i = 0
    while i < len(fields) and fields[i]:
        code = fields[i][0]
        if code in "RC":
            old, new = fields[i + 1], fields[i + 2]
            if code == "R":
                changes.append(("D", old))
            changes.append(("A", new))
            i += 3
        else:
            changes.append((code if code in "AD" else "M", fields[i + 1]))
            i += 2
    return changes


def _protected_violations(changes: list[tuple[str, str]]) -> list[str]:
    bad: set[str] = set()
    for kind, path in changes:
        guarded = path in PROTECTED_FILES or path.startswith(PROTECTED_PREFIXES)
        weakens_tests = path.startswith(TESTS_DIR) and (kind != "A" or Path(path).name in TEST_HOOK_NAMES)
        if guarded or weakens_tests:
            bad.add(path)
    return sorted(bad)


def _fast_forward(project: Path, base_head: str, candidate_head: str, title: str) -> tuple[str, str]:
    """Advance the developer's checkout to a merge commit built outside any working tree.

    The merge commit reuses the verified candidate tree, so nothing is
    verified or reverted in the checkout. It only receives a fast-forward,
    and only while it is clean and still at the commit the attempt started from.
    """
    if _head(project) != base_head:
        return "main-moved", "main moved while the candidate was being built"
    if _git(project, "status", "--porcelain").stdout.strip():
        return "main-dirty", "the checkout has uncommitted changes"
    tree = _git(project, "rev-parse", f"{candidate_head}^{{tree}}").stdout.strip()
    merge = _git(
        project,
        "commit-tree", tree,
        "-p", base_head,
        "-p", candidate_head,
        "-m", f"merge autopilot: {title[:65]}",
    ).stdout.strip()
    forward = _git(project, "merge", "--ff-only", merge, check=False)
    if forward.returncode != 0:
        return "merge-failed", forward.stderr[-3000:]
    return "merged", merge


def _record_attempt(project: Path, proposal: dict, outcome: str, detail: str = "") -> None:
    state = _read_state(project)
    attempts = state.setdefault("attempts", {})
    signature = str(proposal["signature"])
    evidence_count = int(proposal.get("evidence_count", 0))
    for lesson in Store(project).lessons():
        if lesson["signature"] == signature:
            evidence_count = max(evidence_count, int(lesson["evidence_count"]))
            break
    attempts[signature] = {
        "evidence_count": evidence_count,
        "outcome": outcome,
        "title": proposal.get("title", ""),
        "updated_at": utc_now(),
        "detail": detail[-2000:],
    }
    _write_state(project, state)


def _record_mistake(project: Path, proposal: dict, description: str, source: str) -> None:
    Store(project).add_event(Event(
        kind="mistake",
        title=str(proposal["title"]),
        description=description,
        tags=list(proposal.get("tags", [])) + ["autopilot"],
        source=source,
    ))
    learn(project)


def _finish(project: Path, proposal: dict, result: dict, status: str, detail: str = "") -> dict:
    result["status"] = status
    if detail and status not in {"merged", "verified-branch"}:
        result["detail"] = detail[-3000:]
    _record_attempt(project, proposal, status, detail)
    return result


def _cleanup(project: Path, worktree: Path, branch: str, status: str) -> None:
    _git(project, "worktree", "remove", "--force", str(worktree), check=False)
    if status not in KEEP_BRANCH:
        _git(project, "branch", "-D", branch, check=False)


def run_once(
    project: Path,
    test_command: str,
    max_budget_usd: float = 0.75,
    agent_runner: AgentRunner | None = None,
    merge_verified: bool = True,
) -> dict:
    project = project.resolve()
    if not test_command.strip():
        return {"status": "blocked", "reason": "a verification command is required"}

    store = Store(project)
    proposal = select_candidate(project)
    if proposal is None:
        return {"status": "idle", "reason": "no unattempted high-priority proposal"}

    if _git(project, "status", "--porcelain").stdout.strip():
        return {"status": "blocked", "reason": "main worktree is not clean", "proposal": proposal}

    base_head = _head(project)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    branch = f"tashevloop/auto/{stamp}-{_slug(str(proposal['title']))}"
    worktrees_root = project.parent / ".worktrees"
    worktrees_root.mkdir(parents=True, exist_ok=True)
    worktree = worktrees_root / f"{project.name}-auto-{stamp}"

    _git(project, "worktree", "add", "-b", branch, str(worktree), base_head)
    result: dict = {
        "status": "started",
        "proposal": proposal,
        "branch": branch,
        "worktree": str(worktree),
        "base_head": base_head,
    }
    signature = proposal["signature"]

    try:
        context = context_markdown(project, str(proposal["title"]), limit=7)
        prompt = f"""You are implementing one bounded self-improvement task for TashevLoop.

Read AGENTS.md and any .tashevos PROJECT/STATE/GUARDRAILS files before editing.

Task title: {proposal['title']}
Why: {proposal['reason']}
Required action: {proposal['action']}

Project-learned context:
{context}

Rules:
- Work only inside this isolated git worktree. You can read, edit and create files; you cannot run commands.
- The outer TashevLoop gate runs the verification command and commits the result.
- Make the smallest safe change that addresses this task.
- Cover behavioral changes with new test files under tests/. Do not modify or delete existing tests.
- Do not change LICENSE, NOTICE, .github/ or the runner scripts in scripts/; such candidates are rejected automatically.
- Do not deploy, publish, push, access secrets, or use the web.
- If the task cannot be safely solved from repository evidence, make no changes and explain why.
"""
        runner = agent_runner or default_claude_runner
        try:
            agent_result = runner(worktree, prompt, max_budget_usd)
        except Exception as exc:
            # A timeout or a missing CLI still counts as an attempt; otherwise
            # the same proposal would start another paid run on every cycle.
            return _finish(project, proposal, result, "agent-error", f"{type(exc).__name__}: {exc}")
        result["agent"] = agent_result

        if not _git(worktree, "status", "--porcelain").stdout.strip():
            return _finish(project, proposal, result, "no-change", agent_result.get("stdout", ""))

        _git(worktree, "add", "-A")
        violations = _protected_violations(_staged_changes(worktree, base_head))
        if violations:
            detail = "Candidate changed protected paths: " + ", ".join(violations)
            _record_mistake(project, proposal, detail, f"autopilot-protected:{base_head}:{signature}")
            return _finish(project, proposal, result, "protected-change", detail)

        verification = _verification(worktree, test_command)
        result["verification"] = verification
        if not verification["passed"]:
            _record_mistake(
                project,
                proposal,
                f"Autopilot candidate failed verification.\n{verification['output']}",
                f"autopilot:{base_head}:{signature}",
            )
            return _finish(project, proposal, result, "verification-failed", verification["output"])

        commit = _git(
            worktree,
            "commit",
            "-m",
            f"autopilot: {str(proposal['title'])[:70]}",
            check=False,
        )
        if commit.returncode != 0:
            return _finish(project, proposal, result, "commit-failed", commit.stderr[-3000:])

        candidate_head = _head(worktree)
        result["candidate_head"] = candidate_head

        if not merge_verified:
            return _finish(project, proposal, result, "verified-branch", branch)

        status, detail = _fast_forward(project, base_head, candidate_head, str(proposal["title"]))
        if status != "merged":
            return _finish(project, proposal, result, status, detail)

        store.add_event(Event(
            kind="fix",
            title=str(proposal["title"]),
            description="Autopilot implemented the improvement in an isolated worktree and all configured checks passed.",
            solution=str(proposal["action"]),
            tags=list(proposal.get("tags", [])) + ["autopilot"],
            source=f"autopilot-success:{candidate_head}:{signature}",
        ))
        learn(project)
        build_improvement_plan(project)
        result["head"] = _head(project)
        return _finish(project, proposal, result, "merged", candidate_head)
    except Exception as exc:
        if result["status"] == "started":
            result["status"] = "error"
            _record_attempt(project, proposal, "error", f"{type(exc).__name__}: {exc}")
        raise
    finally:
        _cleanup(project, worktree, branch, result["status"])
