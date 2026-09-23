from __future__ import annotations

import json
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable

from .engine import context_markdown, learn
from .evolution import build_improvement_plan
from .models import Event, utc_now
from .store import Store


AgentRunner = Callable[[Path, str, float], dict]


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
        "--allowedTools", "Read,Edit,Write,Bash(git *),Bash(python3 *)",
        "--disallowedTools", "WebFetch,WebSearch",
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
        return {"passed": True, "returncode": 0, "output": "No verification command configured."}
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


def run_once(
    project: Path,
    test_command: str,
    max_budget_usd: float = 0.75,
    agent_runner: AgentRunner | None = None,
    merge_verified: bool = True,
) -> dict:
    project = project.resolve()
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
- Work only inside this isolated git worktree.
- Make the smallest safe change that addresses this task.
- Do not deploy, publish, push, access secrets, or use the web.
- Do not change LICENSE or weaken project guardrails.
- Add or update tests for behavioral changes.
- Do not commit; the outer TashevLoop gate will verify and commit.
- If the task cannot be safely solved from repository evidence, make no changes and explain why.
"""
        runner = agent_runner or default_claude_runner
        agent_result = runner(worktree, prompt, max_budget_usd)
        result["agent"] = agent_result

        diff = _git(worktree, "status", "--porcelain").stdout.strip()
        if not diff:
            _record_attempt(project, proposal, "no-change", agent_result.get("stdout", ""))
            result["status"] = "no-change"
            return result

        verification = _verification(worktree, test_command)
        result["verification"] = verification
        if not verification["passed"]:
            store.add_event(Event(
                kind="mistake",
                title=str(proposal["title"]),
                description=f"Autopilot candidate failed verification.\n{verification['output']}",
                tags=list(proposal.get("tags", [])) + ["autopilot"],
                source=f"autopilot:{base_head}:{proposal['signature']}",
            ))
            learn(project)
            _record_attempt(project, proposal, "verification-failed", verification["output"])
            result["status"] = "verification-failed"
            return result

        _git(worktree, "add", ".")
        commit = _git(
            worktree,
            "commit",
            "-m",
            f"autopilot: {str(proposal['title'])[:70]}",
            check=False,
        )
        if commit.returncode != 0:
            result["status"] = "commit-failed"
            result["detail"] = commit.stderr[-3000:]
            _record_attempt(project, proposal, "commit-failed", result["detail"])
            return result

        candidate_head = _head(worktree)
        result["candidate_head"] = candidate_head

        if not merge_verified:
            _record_attempt(project, proposal, "verified-branch", branch)
            result["status"] = "verified-branch"
            return result

        if _head(project) != base_head:
            _record_attempt(project, proposal, "main-moved", branch)
            result["status"] = "main-moved"
            return result

        merge = _git(
            project,
            "merge",
            "--no-ff",
            branch,
            "-m",
            f"merge autopilot: {str(proposal['title'])[:65]}",
            check=False,
        )
        if merge.returncode != 0:
            result["status"] = "merge-failed"
            result["detail"] = merge.stderr[-3000:]
            _git(project, "merge", "--abort", check=False)
            _record_attempt(project, proposal, "merge-failed", result["detail"])
            return result

        post = _verification(project, test_command)
        result["post_merge_verification"] = post
        if not post["passed"]:
            merge_head = _head(project)
            revert = _git(project, "revert", "-m", "1", "--no-edit", merge_head, check=False)
            result["status"] = "reverted"
            result["revert_returncode"] = revert.returncode
            store.add_event(Event(
                kind="mistake",
                title=str(proposal["title"]),
                description=f"Autopilot merge failed post-merge verification and was reverted.\n{post['output']}",
                tags=list(proposal.get("tags", [])) + ["autopilot"],
                source=f"autopilot-post:{merge_head}:{proposal['signature']}",
            ))
            learn(project)
            _record_attempt(project, proposal, "reverted", post["output"])
            return result

        store.add_event(Event(
            kind="fix",
            title=str(proposal["title"]),
            description="Autopilot implemented the improvement in an isolated worktree and all configured checks passed.",
            solution=str(proposal["action"]),
            tags=list(proposal.get("tags", [])) + ["autopilot"],
            source=f"autopilot-success:{candidate_head}:{proposal['signature']}",
        ))
        learn(project)
        build_improvement_plan(project)
        _record_attempt(project, proposal, "merged", candidate_head)
        result["status"] = "merged"
        result["head"] = _head(project)
        return result
    finally:
        status = result.get("status")
        if status in {"merged", "verification-failed", "no-change", "commit-failed", "reverted"}:
            _git(project, "worktree", "remove", "--force", str(worktree), check=False)
            if status == "merged":
                _git(project, "branch", "-D", branch, check=False)
