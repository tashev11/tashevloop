from __future__ import annotations

import json
from pathlib import Path

from .engine import learn
from .store import Store


def _lesson_proposal(
    lesson: dict,
    priority: str,
    kind: str,
    reason: str,
    action: str,
) -> dict:
    return {
        "priority": priority,
        "kind": kind,
        "title": lesson["title"],
        "reason": reason,
        "action": action,
        "signature": lesson["signature"],
        "evidence_count": int(lesson["evidence_count"]),
        "tags": list(lesson["tags"]),
    }


def build_improvement_plan(project: Path) -> list[dict]:
    project = project.resolve()
    store = Store(project)
    lessons = store.lessons()
    if not lessons and store.stats()["events"]:
        learn(project)
        lessons = store.lessons()

    proposals: list[dict] = []
    for lesson in lessons:
        failures = int(lesson["failure_count"])
        successes = int(lesson["success_count"])
        evidence = int(lesson["evidence_count"])
        confidence = float(lesson["confidence"])

        if failures >= 2 and failures >= successes:
            proposals.append(_lesson_proposal(
                lesson,
                "high",
                "repeated-failure",
                f"{failures} failure signals vs {successes} successful signals",
                (
                    "Add a deterministic guard, regression test, or preflight check "
                    "that prevents this failure from recurring."
                ),
            ))
        elif failures > 0 and successes == 0:
            proposals.append(_lesson_proposal(
                lesson,
                "high",
                "unresolved-failure",
                "Failure evidence exists but no verified fix/success is recorded",
                "Reproduce the problem, verify a fix, then record the successful outcome.",
            ))
        elif confidence < 0.45 and evidence >= 2:
            proposals.append(_lesson_proposal(
                lesson,
                "medium",
                "weak-lesson",
                f"{evidence} evidence items but only {confidence:.0%} confidence",
                "Collect a stronger verification signal before relying on this lesson.",
            ))

    reliability = store.tag_reliability()
    for tag, score in sorted(reliability.items(), key=lambda x: x[1]):
        if score < 0.4:
            proposals.append({
                "priority": "medium",
                "kind": "unstable-area",
                "title": f"Stabilize area: {tag}",
                "reason": f"Observed reliability for tag '{tag}' is {score:.0%}",
                "action": "Add focused tests/checks and record verified fixes for this area.",
                "signature": f"tag:{tag}",
                "evidence_count": 0,
                "tags": [tag],
            })

    order = {"high": 0, "medium": 1, "low": 2}
    proposals.sort(key=lambda x: (order.get(x["priority"], 9), x["title"].lower()))

    home = store.home
    home.mkdir(parents=True, exist_ok=True)
    (home / "next_tasks.json").write_text(
        json.dumps(proposals, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# TashevLoop Improvement Plan",
        "",
        "Generated from project evidence. With the autopilot enabled, high-priority items may be attempted automatically in an isolated worktree.",
        "",
    ]
    if not proposals:
        lines.append("No high-signal improvement proposal yet.")
    else:
        for i, item in enumerate(proposals, 1):
            lines.extend([
                f"## {i}. [{item['priority'].upper()}] {item['title']}",
                f"- Type: {item['kind']}",
                f"- Why: {item['reason']}",
                f"- Next action: {item['action']}",
                "",
            ])
    (home / "IMPROVEMENTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return proposals
