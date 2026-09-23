from __future__ import annotations

import json
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from .models import Event, Lesson, utc_now


SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    solution TEXT NOT NULL DEFAULT '',
    tags TEXT NOT NULL DEFAULT '[]',
    source TEXT NOT NULL DEFAULT 'manual',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_kind ON events(kind);
CREATE INDEX IF NOT EXISTS idx_events_created ON events(created_at);

CREATE TABLE IF NOT EXISTS lessons (
    signature TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    guidance TEXT NOT NULL,
    tags TEXT NOT NULL DEFAULT '[]',
    evidence_count INTEGER NOT NULL,
    failure_count INTEGER NOT NULL,
    success_count INTEGER NOT NULL,
    confidence REAL NOT NULL,
    updated_at TEXT NOT NULL
);
"""


class Store:
    def __init__(self, project: Path):
        self.project = project.resolve()
        self.home = self.project / ".tashevloop"
        self.db_path = self.home / "memory.db"

    def init(self) -> None:
        self.home.mkdir(parents=True, exist_ok=True)
        ignore = self.home / ".gitignore"
        if not ignore.exists():
            # Keep the store out of the host project's Git history even when
            # that project does not list .tashevloop/ in its own .gitignore.
            ignore.write_text("*\n", encoding="utf-8")
        with self.session() as db:
            db.executescript(SCHEMA)

    def connect(self) -> sqlite3.Connection:
        self.home.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row
        return db

    @contextmanager
    def session(self) -> Generator[sqlite3.Connection, None, None]:
        """Open a connection, commit on success, and always close it."""
        db = self.connect()
        try:
            with db:
                yield db
        finally:
            db.close()

    def add_event(self, event: Event) -> int:
        event.validate()
        self.init()
        with self.session() as db:
            cur = db.execute(
                """INSERT INTO events(kind,title,description,solution,tags,source,created_at)
                   VALUES(?,?,?,?,?,?,?)""",
                (
                    event.kind,
                    event.title.strip(),
                    event.description.strip(),
                    event.solution.strip(),
                    json.dumps(event.tags, ensure_ascii=False),
                    event.source.strip() or "manual",
                    event.created_at,
                ),
            )
            return int(cur.lastrowid)

    def events(self) -> list[dict]:
        self.init()
        with self.session() as db:
            rows = db.execute("SELECT * FROM events ORDER BY id ASC").fetchall()
        return [self._event_row(r) for r in rows]

    def has_source(self, source: str) -> bool:
        self.init()
        with self.session() as db:
            row = db.execute(
                "SELECT 1 FROM events WHERE source = ? LIMIT 1",
                (source,),
            ).fetchone()
        return row is not None

    def replace_lessons(self, lessons: list[Lesson]) -> None:
        self.init()
        with self.session() as db:
            db.execute("DELETE FROM lessons")
            db.executemany(
                """INSERT INTO lessons(signature,title,guidance,tags,evidence_count,
                   failure_count,success_count,confidence,updated_at)
                   VALUES(?,?,?,?,?,?,?,?,?)""",
                [
                    (
                        x.signature,
                        x.title,
                        x.guidance,
                        json.dumps(x.tags, ensure_ascii=False),
                        x.evidence_count,
                        x.failure_count,
                        x.success_count,
                        x.confidence,
                        x.updated_at,
                    )
                    for x in lessons
                ],
            )

    def lessons(self) -> list[dict]:
        self.init()
        with self.session() as db:
            rows = db.execute(
                "SELECT * FROM lessons ORDER BY confidence DESC, evidence_count DESC"
            ).fetchall()
        return [self._lesson_row(r) for r in rows]

    def stats(self) -> dict:
        self.init()
        with self.session() as db:
            event_count = db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            lesson_count = db.execute("SELECT COUNT(*) FROM lessons").fetchone()[0]
            failures = db.execute("SELECT COUNT(*) FROM events WHERE kind='mistake'").fetchone()[0]
            warnings = db.execute("SELECT COUNT(*) FROM events WHERE kind='warning'").fetchone()[0]
            fixes = db.execute("SELECT COUNT(*) FROM events WHERE kind='fix'").fetchone()[0]
            successes = db.execute("SELECT COUNT(*) FROM events WHERE kind='success'").fetchone()[0]
        return {
            "events": event_count,
            "lessons": lesson_count,
            "mistakes": failures,
            "warnings": warnings,
            "fixes": fixes,
            "successes": successes,
            "updated_at": utc_now(),
        }

    def tag_reliability(self) -> dict[str, float]:
        """Return smoothed success ratio for every observed tag."""
        totals: dict[str, list[int]] = {}
        for event in self.events():
            positive = event["kind"] in {"fix", "success"}
            negative = event["kind"] in {"mistake", "warning"}
            if not (positive or negative):
                continue
            for tag in event["tags"]:
                pair = totals.setdefault(tag, [0, 0])
                if positive:
                    pair[0] += 1
                if negative:
                    pair[1] += 1

        result: dict[str, float] = {}
        for tag, (good, bad) in totals.items():
            result[tag] = round((good + 1) / (good + bad + 2), 4)
        return result

    @staticmethod
    def _event_row(row: sqlite3.Row) -> dict:
        item = dict(row)
        item["tags"] = json.loads(item["tags"])
        return item

    @staticmethod
    def _lesson_row(row: sqlite3.Row) -> dict:
        item = dict(row)
        item["tags"] = json.loads(item["tags"])
        return item
