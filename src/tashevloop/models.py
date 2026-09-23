from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable


VALID_KINDS = {"mistake", "fix", "success", "decision", "warning"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(slots=True)
class Event:
    kind: str
    title: str
    description: str = ""
    solution: str = ""
    tags: list[str] = field(default_factory=list)
    source: str = "manual"
    created_at: str = field(default_factory=utc_now)

    def validate(self) -> None:
        if self.kind not in VALID_KINDS:
            raise ValueError(f"kind must be one of: {', '.join(sorted(VALID_KINDS))}")
        if not self.title.strip():
            raise ValueError("title is required")
        self.tags = clean_tags(self.tags)


@dataclass(slots=True)
class Lesson:
    signature: str
    title: str
    guidance: str
    tags: list[str]
    evidence_count: int
    failure_count: int
    success_count: int
    confidence: float
    updated_at: str


def clean_tags(tags: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in tags:
        tag = raw.strip().lower().replace(" ", "-")
        if tag and tag not in seen:
            seen.add(tag)
            out.append(tag)
    return out
