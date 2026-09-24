import tempfile
import unittest
from pathlib import Path

from tashevloop.engine import context_markdown, learn, suggest
from tashevloop.models import Event
from tashevloop.store import Store
from tashevloop.text import strip_trailers


class EngineTests(unittest.TestCase):
    def test_mistake_and_fix_become_reusable_lesson(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            store = Store(project)
            store.add_event(Event(
                kind="mistake",
                title="Forgot to include cities.js in Electron build",
                description="Packaged desktop app crashed after release",
                tags=["electron", "release", "build"],
            ))
            store.add_event(Event(
                kind="fix",
                title="Forgot to include cities.js in Electron build",
                description="Added the missing file to build.files and rebuilt",
                solution="Before Electron release, verify every runtime data file is included in build.files.",
                tags=["electron", "release", "build"],
            ))

            lessons = learn(project)
            self.assertEqual(len(lessons), 1)
            self.assertEqual(lessons[0].success_count, 1)
            self.assertIn("build.files", lessons[0].guidance)

            tips = suggest(project, "release electron build package", limit=3)
            self.assertTrue(tips)
            self.assertGreater(tips[0]["confidence"], 0.3)

    def test_context_is_compact_and_human_readable(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            store = Store(project)
            store.add_event(Event(
                kind="decision",
                title="Read project state before editing",
                description="Always read STATE.md and project guardrails before changing code.",
                tags=["context", "agents"],
            ))
            learn(project)
            text = context_markdown(project, "agent context before coding")
            self.assertIn("# TashevLoop Context", text)
            self.assertIn("STATE.md", text)

    def test_trailers_never_become_guidance(self):
        # Events imported before trailers were stripped keep their raw text;
        # the lessons built from them must not.
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            store = Store(project)
            store.add_event(Event(
                kind="success",
                title="Continuous crawl without daily pause",
                solution="Co-Authored-By: Claude <noreply@anthropic.com>",
                tags=["git"],
            ))
            store.add_event(Event(
                kind="fix",
                title="Disk-full stop instead of sqlite crash",
                description="Stop the crawl cleanly when the disk is full.\n\nCo-Authored-By: Claude <noreply@anthropic.com>",
                tags=["crawl"],
            ))
            guidance = {lesson.title: lesson.guidance for lesson in learn(project)}
            self.assertEqual(
                guidance["Continuous crawl without daily pause"],
                "Repeat the successful approach: Continuous crawl without daily pause",
            )
            self.assertEqual(
                guidance["Disk-full stop instead of sqlite crash"],
                "Stop the crawl cleanly when the disk is full.",
            )

    def test_strip_trailers_keeps_ordinary_key_value_lines(self):
        text = "Note: keep the cache warm.\nFix: retry once.\n\nCo-authored-by: Someone <s@example.com>"
        self.assertEqual(strip_trailers(text), "Note: keep the cache warm.\nFix: retry once.")


if __name__ == "__main__":
    unittest.main()
