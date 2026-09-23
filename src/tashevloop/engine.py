from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from .models import Lesson, utc_now
from .store import Store
from .text import overlap_score, signature


def learn(project: Path) -> list[Lesson]:
    store = Store(project)
    groups: dict[str, list[dict]] = defaultdict(list)

    for event in store.events():
        sig = signature(event["title"], "", event["tags"])
        groups[sig].append(event)

    lessons: list[Lesson] = []
    for sig, items in groups.items():
        failures = [x for x in items if x["kind"] in {"mistake", "warning"}]
        successes = [x for x in items if x["kind"] in {"fix", "success"}]
        decisions = [x for x in items if x["kind"] == "decision"]

        if not (failures or successes or decisions):
            continue

        evidence = len(items)
        failure_count = len(failures)
        success_count = len(successes)
        solved = [x for x in items if x["solution"].strip()]
        best = solved[-1] if solved else (successes[-1] if successes else items[-1])

        guidance = best["solution"].strip()
        if not guidance:
            if best["kind"] == "success":
                guidance = best["description"].strip() or f"Repeat the successful approach: {best['title']}"
            elif best["kind"] == "decision":
                guidance = best["description"].strip() or best["title"]
            else:
                guidance = f"Avoid repeating this pattern until a verified fix is recorded: {best['title']}"

        tags: list[str] = []
        for item in items:
            for tag in item["tags"]:
                if tag not in tags:
                    tags.append(tag)

        verified_bonus = min(0.35, success_count * 0.12)
        evidence_bonus = min(0.35, max(0, evidence - 1) * 0.08)
        base = 0.25 if failure_count else 0.35
        confidence = round(min(0.95, base + verified_bonus + evidence_bonus), 2)

        lessons.append(
            Lesson(
                signature=sig,
                title=best["title"],
                guidance=guidance,
                tags=tags,
                evidence_count=evidence,
                failure_count=failure_count,
                success_count=success_count,
                confidence=confidence,
                updated_at=utc_now(),
            )
        )

    lessons.sort(key=lambda x: (x.confidence, x.evidence_count), reverse=True)
    store.replace_lessons(lessons)
    return lessons


def suggest(project: Path, query: str, limit: int = 5) -> list[dict]:
    store = Store(project)
    rows = store.lessons()
    if not rows and store.stats()["events"]:
        learn(project)
        rows = store.lessons()

    ranked: list[dict] = []
    for row in rows:
        semantic = overlap_score(query, row["signature"], row["tags"])
        score = semantic * 0.78 + float(row["confidence"]) * 0.22
        if semantic > 0 or row["confidence"] >= 0.75:
            ranked.append({**row, "score": round(score, 4)})

    ranked.sort(key=lambda x: (x["score"], x["confidence"], x["evidence_count"]), reverse=True)
    return ranked[: max(1, limit)]


def context_markdown(project: Path, query: str, limit: int = 5) -> str:
    tips = suggest(project, query, limit=limit)
    lines = [
        "# TashevLoop Context",
        "",
        f"Task: {query}",
        "",
        "Use these project-learned lessons as guidance, not as absolute truth.",
        "",
    ]
    if not tips:
        lines.append("No relevant learned lessons yet.")
        return "\n".join(lines) + "\n"

    for i, item in enumerate(tips, 1):
        lines.extend(
            [
                f"## {i}. {item['title']}",
                f"- Confidence: {item['confidence']:.0%}",
                f"- Evidence: {item['evidence_count']} events",
                f"- Guidance: {item['guidance']}",
                "",
            ]
        )
    return "\n".join(lines)
